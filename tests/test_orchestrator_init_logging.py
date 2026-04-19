import logging

import orchestrator.core as core_module


def test_research_init_missing_dependency_logs_error(monkeypatch, caplog):
    def _raise_missing_dependency():
        raise ModuleNotFoundError("Optional dependency 'tavily' is not installed")

    monkeypatch.setattr(core_module, "create_research_service_from_env", _raise_missing_dependency)

    caplog.set_level(logging.ERROR)
    orchestrator = core_module.CortexOrchestrator()

    assert orchestrator.research_service is None
    assert orchestrator.session_store is None

    record = next(
        (
            entry
            for entry in caplog.records
            if getattr(entry, "extra_fields", {}).get("event") == "research.init.failed"
        ),
        None,
    )
    assert record is not None
    assert record.levelname == "ERROR"
    assert getattr(record, "extra_fields", {}).get("error_kind") == "missing_dependency"


def test_research_init_not_configured_logs_warning(monkeypatch, caplog):
    def _raise_not_configured():
        raise ValueError("TAVILY_API_KEY not set in environment")

    monkeypatch.setattr(core_module, "create_research_service_from_env", _raise_not_configured)

    caplog.set_level(logging.WARNING)
    orchestrator = core_module.CortexOrchestrator()

    assert orchestrator.research_service is None
    assert orchestrator.session_store is None

    record = next(
        (
            entry
            for entry in caplog.records
            if getattr(entry, "extra_fields", {}).get("event") == "research.init.unavailable"
        ),
        None,
    )
    assert record is not None
    assert record.levelname == "WARNING"
