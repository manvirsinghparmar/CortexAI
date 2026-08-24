from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from server.work.config import WorkConfig
from server.work import service
from server.work.billing import calculate_work_credit_usage
from server.work.provider import ProviderEvent


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
        default_credit_budget=1_000_000,
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
    assert default_budget == 250_000
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


def test_provider_interrupt_and_followup_event_guards():
    assert service._provider_session_is_interruptible("running")
    assert service._provider_session_is_interruptible("rescheduling")
    assert not service._provider_session_is_interruptible("idle")
    assert not service._provider_session_is_interruptible("terminated")

    old = ProviderEvent(
        id="old-budget",
        type="budget_exhausted",
        display_message="Budget reached",
        payload={"provider_type": "session.status_idle"},
        terminal_status="budget_exhausted",
        stop_reason="budget_reached",
    )
    new = ProviderEvent(
        id="new-progress",
        type="progress",
        display_message="Work resumed",
        payload={"provider_type": "session.status_running"},
    )
    assert service._latest_provider_stop_reason([old]) == "budget_reached"
    filtered = service._provider_events_for_run(
        [old, new],
        {"configuration_snapshot": {"provider_event_baseline_ids": [old.id]}},
    )
    assert filtered == [new]

    confirmation = ProviderEvent(
        id="confirmation-1",
        type="progress",
        display_message=None,
        payload={
            "provider_type": "user.tool_confirmation",
            "tool_use_id": "tool-1",
            "result": "allow",
        },
    )
    assert service._provider_confirmed_tool_ids([old, confirmation]) == {"tool-1"}


def test_work_settlement_persists_full_cache_partition_and_provider_floor(monkeypatch):
    usage = calculate_work_credit_usage(
        {
            "list_cost": {"amount": "20", "currency": "USD"},
            "input_tokens": 30,
            "output_tokens": 7_668,
            "active_seconds": 184.073,
            "cache_creation": {"ephemeral_5m_input_tokens": 29_115},
            "cache_read_input_tokens": 244_569,
        },
        {"list_cost": {"amount": "0", "currency": "USD"}},
        model="claude-sonnet-5",
    )
    reservation_id = uuid4()
    work_session_id = uuid4()
    user_id = uuid4()
    transaction: dict[str, object] = {}
    settlement = SimpleNamespace(
        billed_quantity=usage.total_credits,
        reservation=SimpleNamespace(
            id=reservation_id,
            billing_account_id=uuid4(),
            usage_period_id=uuid4(),
        ),
    )
    monkeypatch.setattr(
        service.repository,
        "get_work_session",
        lambda *_: {"user_id": user_id},
    )
    monkeypatch.setattr(
        service,
        "resolve_effective_subscription",
        lambda *_: SimpleNamespace(
            plan=SimpleNamespace(allowances=SimpleNamespace(ai_credits=1_000_000))
        ),
    )
    monkeypatch.setattr(
        service, "settle_usage_with_supplement", lambda *_args, **_kwargs: settlement
    )
    monkeypatch.setattr(
        service.billing_repository,
        "create_credit_transaction",
        lambda _db, **kwargs: transaction.update(kwargs),
    )

    billed = service._settle_work_billing(
        object(),
        {
            "billing_reservation_id": reservation_id,
            "work_session_id": work_session_id,
            "request_id": "work-cache-incident",
            "instruction": "Analyze this repository",
        },
        usage,
    )

    assert billed == 385_636
    assert transaction["input_tokens"] == 273_714
    assert transaction["normal_input_tokens"] == 30
    assert transaction["cached_input_tokens"] == 244_569
    assert transaction["cache_write_tokens"] == 29_115
    assert transaction["input_credits"] == 243_523
    assert transaction["output_credits"] == 138_024
    assert transaction["fixed_credits"] == 4_089
    assert transaction["total_credits"] == 385_636
    assert transaction["provider_cost_usd"] == pytest.approx(0.2025301889)
    metadata = transaction["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["managed_component_credits"] == 385_636
    assert metadata["managed_provider_floor_credits"] == 200_000
    assert metadata["managed_reported_provider_cost_usd"] == pytest.approx(0.20)
