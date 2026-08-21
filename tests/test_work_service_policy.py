from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from server.work.config import WorkConfig
from server.work import service


def _config(**overrides: object) -> WorkConfig:
    base = WorkConfig(
        enabled=True,
        mcp_enabled=True,
        action_tools_enabled=True,
        artifact_import_enabled=True,
        web_enabled=True,
        provider="fake",
        agent_id="agent-1",
        environment_id="environment-1",
        billing_model="claude-haiku-4-5",
        default_credit_budget=100_000,
        event_sync_interval_seconds=1,
        sse_heartbeat_seconds=15,
        approval_timeout_seconds=3600,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _effective(*, work: bool, active: int = 1, budget: int = 250_000, custom: bool = False):
    plan = SimpleNamespace(
        code="plus" if work else "free",
        display_name="Plus" if work else "Free",
        entitlements=SimpleNamespace(
            work_enabled=work,
            custom_mcp_enabled=custom,
        ),
        limits=SimpleNamespace(
            max_active_work_runs=active,
            max_work_credit_budget=budget,
            max_mcp_servers_per_run=3,
        ),
    )
    return SimpleNamespace(plan=plan)


def test_feature_off_is_not_exposed_as_a_partially_configured_route():
    with pytest.raises(HTTPException) as caught:
        service.require_work_enabled(_config(enabled=False))
    assert caught.value.status_code == 404
    assert caught.value.detail["code"] == "work_disabled"


def test_free_is_denied_and_plus_budget_boundaries_are_enforced(monkeypatch):
    monkeypatch.setattr(service.repository, "count_active_work_runs", lambda *_: 0)
    monkeypatch.setattr(
        service, "resolve_effective_subscription", lambda *_: _effective(work=False)
    )
    with pytest.raises(HTTPException) as denied:
        service._plan_and_budget(object(), uuid4(), 25_000, _config())
    assert denied.value.status_code == 403
    assert denied.value.detail["code"] == "work_not_in_plan"

    monkeypatch.setattr(service, "resolve_effective_subscription", lambda *_: _effective(work=True))
    _, default_budget = service._plan_and_budget(object(), uuid4(), None, _config())
    assert default_budget == 100_000
    with pytest.raises(HTTPException) as too_large:
        service._plan_and_budget(object(), uuid4(), 250_001, _config())
    assert too_large.value.status_code == 422
    assert too_large.value.detail["code"] == "invalid_work_credit_budget"


def test_active_run_limit_and_custom_mcp_entitlement(monkeypatch):
    monkeypatch.setattr(service, "resolve_effective_subscription", lambda *_: _effective(work=True))
    monkeypatch.setattr(service.repository, "count_active_work_runs", lambda *_: 1)
    with pytest.raises(HTTPException) as active_limit:
        service._plan_and_budget(object(), uuid4(), 25_000, _config())
    assert active_limit.value.status_code == 409
    assert active_limit.value.detail["code"] == "active_work_run_limit"

    connection_id = uuid4()
    monkeypatch.setattr(
        service.repository,
        "get_tool_connection_for_user",
        lambda *_: {
            "id": connection_id,
            "status": "connected",
            "connection_type": "mcp_remote",
            "connector_key": "custom_mcp",
        },
    )
    with pytest.raises(HTTPException) as custom_denied:
        service._load_connections(
            object(),
            user_id=uuid4(),
            connection_ids=[connection_id],
            plan=_effective(work=True, custom=False).plan,
            config=_config(),
        )
    assert custom_denied.value.status_code == 403
    allowed = service._load_connections(
        object(),
        user_id=uuid4(),
        connection_ids=[connection_id],
        plan=_effective(work=True, custom=True).plan,
        config=_config(),
    )
    assert allowed[0]["id"] == connection_id


def test_saved_write_policy_is_exactly_scoped_and_sensitive_actions_still_ask():
    connection_id = uuid4()
    session = {
        "default_tool_policy": {
            "allowed_write_tools": [
                {
                    "connection_id": str(connection_id),
                    "tool_name": "open_pull_request",
                }
            ]
        }
    }
    assert service._has_saved_write_grant(
        session,
        connection_id=connection_id,
        tool_name="open_pull_request",
    )
    assert not service._has_saved_write_grant(
        session,
        connection_id=uuid4(),
        tool_name="open_pull_request",
    )
    assert service.classify_action("open_pull_request") == "WRITE"
    assert service.classify_action("merge_pull_request") == "DESTRUCTIVE"
