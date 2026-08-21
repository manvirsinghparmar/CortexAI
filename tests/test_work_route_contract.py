from __future__ import annotations

from uuid import uuid4

from pydantic import ValidationError
import pytest

from server.app import create_app
from server.routes import tools, work
from server.schemas.work import WorkApprovalDecisionDTO, WorkRunCreateDTO


def test_work_and_tool_routes_are_registered_with_expected_methods():
    app = create_app()
    included = [route.original_router for route in app.routes if hasattr(route, "original_router")]
    assert any(router is work.router for router in included)
    assert any(router is tools.router for router in included)
    methods_by_path: dict[str, set[str]] = {}
    for route in [*work.router.routes, *tools.router.routes]:
        if hasattr(route, "methods"):
            methods_by_path.setdefault(route.path, set()).update(route.methods or set())
    expected = {
        "/v1/work/sessions": {"GET", "POST"},
        "/v1/work/sessions/{work_session_id}/runs": {"POST"},
        "/v1/work/sessions/{work_session_id}/instructions": {"POST"},
        "/v1/work/runs/{run_id}": {"GET"},
        "/v1/work/runs/{run_id}/events": {"GET"},
        "/v1/work/runs/{run_id}/stream": {"GET"},
        "/v1/work/runs/{run_id}/cancel": {"POST"},
        "/v1/work/runs/{run_id}/artifacts": {"GET"},
        "/v1/work/approvals/{approval_id}/approve": {"POST"},
        "/v1/work/approvals/{approval_id}/deny": {"POST"},
        "/v1/tools/catalog": {"GET"},
        "/v1/tools/connections": {"GET", "POST"},
        "/v1/tools/connections/{connection_id}/test": {"POST"},
        "/v1/tools/{connector_key}/oauth/start": {"POST"},
        "/v1/tools/{connector_key}/oauth/callback": {"GET"},
    }
    for path, methods in expected.items():
        assert methods <= methods_by_path[path]


def test_work_request_contract_normalizes_and_rejects_duplicate_resources():
    request = WorkRunCreateDTO(
        instruction="  Prepare the report  ",
        input_file_ids=[],
        enabled_connection_ids=[],
        max_credit_budget=25_000,
    )
    assert request.instruction == "Prepare the report"
    assert WorkApprovalDecisionDTO(remember=True).remember is True
    duplicate = uuid4()
    with pytest.raises(ValidationError, match="duplicate IDs"):
        WorkRunCreateDTO(
            instruction="Prepare the report",
            input_file_ids=[duplicate, duplicate],
        )
