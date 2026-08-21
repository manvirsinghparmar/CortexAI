from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.work.anthropic_provider import (
    AnthropicManagedAgentProvider,
    normalize_anthropic_event,
)
from server.work.billing import calculate_work_credit_usage
from server.work.config import WorkConfig
from server.work.provider import ProviderMcpServer, ProviderResource
from server.work.security import classify_action, redact_mapping, validate_remote_https_url


def _config() -> WorkConfig:
    return WorkConfig(
        enabled=True,
        mcp_enabled=True,
        action_tools_enabled=True,
        artifact_import_enabled=True,
        web_enabled=True,
        provider="fake",
        agent_id="agent_123",
        environment_id="environment_123",
        billing_model="claude-haiku-4-5",
        default_credit_budget=100_000,
        event_sync_interval_seconds=1,
        sse_heartbeat_seconds=15,
        approval_timeout_seconds=3600,
    )


def test_anthropic_event_normalization_redacts_tool_secrets_and_thinking():
    tool = normalize_anthropic_event(
        {
            "id": "tool-1",
            "type": "agent.mcp_tool_use",
            "name": "send_email",
            "input": {"to": "person@example.com", "authorization": "secret"},
        }
    )
    assert tool.type == "tool_started"
    assert tool.payload["input_summary"] == {
        "to": "person@example.com",
        "authorization": "[redacted]",
    }
    thinking = normalize_anthropic_event(
        {
            "id": "thinking-1",
            "type": "agent.thinking",
            "content": [{"type": "text", "text": "private reasoning"}],
        }
    )
    assert thinking.display_message == "Reasoning about the next step"
    assert "private reasoning" not in str(thinking.payload)


def test_anthropic_idle_events_map_approval_budget_and_completion():
    approval = normalize_anthropic_event(
        {
            "id": "idle-approval",
            "type": "session.status_idle",
            "stop_reason": {"type": "requires_action", "event_ids": ["tool-1"]},
        }
    )
    budget = normalize_anthropic_event(
        {
            "id": "idle-budget",
            "type": "session.status_idle",
            "stop_reason": {"type": "budget_reached"},
        }
    )
    complete = normalize_anthropic_event(
        {"id": "idle-complete", "type": "session.status_idle", "stop_reason": {"type": "end_turn"}}
    )
    assert approval.type == "approval_required"
    assert approval.payload["blocking_event_ids"] == ["tool-1"]
    assert budget.terminal_status == "budget_exhausted"
    assert complete.terminal_status == "completed"


def test_usage_delta_prevents_followup_double_charge_and_counts_runtime_web():
    baseline = {
        "input_tokens": 1_000,
        "output_tokens": 200,
        "active_seconds": 30,
        "server_tool_use": {"web_search_requests": 1},
    }
    current = {
        "input_tokens": 1_500,
        "output_tokens": 300,
        "active_seconds": 75,
        "server_tool_use": {"web_search_requests": 3},
    }
    usage = calculate_work_credit_usage(current, baseline, model="claude-haiku-4-5")
    assert usage.prompt_tokens == 500
    assert usage.output_tokens == 100
    assert usage.active_seconds == 45
    assert usage.web_searches == 2
    assert usage.runtime_credits == 1_000
    assert usage.web_credits == 20_000
    assert usage.total_credits == usage.model_credits + 21_000
    assert usage.provider_cost_usd > 0.02


def test_remote_mcp_ssrf_and_action_classification(monkeypatch):
    monkeypatch.setattr(
        "server.work.security.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    assert validate_remote_https_url("https://mcp.example.com/mcp") == "https://mcp.example.com/mcp"
    monkeypatch.setattr(
        "server.work.security.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="private or reserved"):
        validate_remote_https_url("https://mcp.example.com/mcp")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_remote_https_url("http://mcp.example.com/mcp")
    assert classify_action("list_issues") == "READ"
    assert classify_action("send_email") == "EXTERNAL_COMMUNICATION"
    assert classify_action("delete_repository") == "DESTRUCTIVE"
    assert redact_mapping({"api_key": "secret", "value": "safe"}) == {
        "api_key": "[redacted]",
        "value": "safe",
    }


def test_provider_create_session_uses_beta_budget_permissions_resources_and_mcp():
    calls: dict[str, object] = {}

    class Events:
        def send(self, session_id, **kwargs):
            calls["send"] = (session_id, kwargs)

        def list(self, session_id, **kwargs):
            calls["list"] = (session_id, kwargs)
            return []

    class Resources:
        def add(self, session_id, **kwargs):
            calls["resource"] = (session_id, kwargs)

    class Sessions:
        events = Events()
        resources = Resources()

        def create(self, **kwargs):
            calls["create"] = kwargs
            return {"id": "session-1", "status": "idle", "usage": {}}

        def retrieve(self, session_id, **kwargs):
            return {"id": session_id, "status": "running", "usage": {}}

    client = SimpleNamespace(
        beta=SimpleNamespace(sessions=Sessions(), files=SimpleNamespace(list=lambda **_kwargs: [])),
        files=SimpleNamespace(
            upload=lambda **_kwargs: {"id": "file-1"}, download=lambda _id: b"data"
        ),
    )
    provider = AnthropicManagedAgentProvider(_config(), client=client)
    created = provider.create_session(
        title="Prepare report",
        resources=[ProviderResource("file-1", "/report.csv")],
        mcp_servers=[ProviderMcpServer("github", "https://mcp.example.com", ("list_issues",))],
        vault_ids=["vault-1"],
        web_enabled=False,
        max_credit_budget=100_000,
    )
    assert created.id == "session-1"
    request = calls["create"]
    assert isinstance(request, dict)
    assert request["betas"] == ["managed-agents-2026-04-01"]
    assert request["budget"] == {
        "type": "limit",
        "max_list_cost": {"amount": "10", "currency": "USD"},
    }
    assert request["resources"] == [
        {"type": "file", "file_id": "file-1", "mount_path": "/report.csv"}
    ]
    agent = request["agent"]
    assert isinstance(agent, dict)
    assert agent["type"] == "agent_with_overrides"
    assert agent["mcp_servers"] == [
        {"type": "url", "name": "github", "url": "https://mcp.example.com"}
    ]
    builtins = agent["tools"][0]
    assert builtins["default_config"]["permission_policy"] == {"type": "always_ask"}
    assert all(config["enabled"] is False for config in builtins["configs"])
    provider.confirm_tool("session-1", "tool-1", allow=False, deny_message="No")
    sent = calls["send"]
    assert sent[1]["events"][0]["type"] == "user.tool_confirmation"
