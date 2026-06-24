import logging

from models.user_context import UserContext
import orchestrator.core as core_module


def _disable_research_init(monkeypatch):
    def _raise_not_configured():
        raise ValueError("TAVILY_API_KEY not set in environment")

    monkeypatch.setattr(core_module, "create_research_service_from_env", _raise_not_configured)


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


def test_prompt_optimizer_not_auto_initialized_from_route_flag(monkeypatch):
    class FailingPromptOptimizer:
        def __init__(self, *args, **kwargs):
            raise AssertionError("orchestrator prompt optimizer should not initialize by default")

    _disable_research_init(monkeypatch)
    monkeypatch.setenv("ENABLE_PROMPT_OPTIMIZATION", "true")
    monkeypatch.delenv("ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION", raising=False)
    monkeypatch.setattr(core_module, "PromptOptimizer", FailingPromptOptimizer)

    orchestrator = core_module.CortexOrchestrator()

    assert orchestrator._prompt_optimizer is None


def test_prompt_optimizer_auto_initializes_only_with_orchestrator_flag(monkeypatch):
    class FakePromptOptimizer:
        def __init__(self, *, provider):
            self.provider = provider

    _disable_research_init(monkeypatch)
    monkeypatch.setenv("ENABLE_PROMPT_OPTIMIZATION", "false")
    monkeypatch.setenv("ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION", "true")
    monkeypatch.setenv("PROMPT_OPTIMIZER_PROVIDER", "openai")
    monkeypatch.setattr(core_module, "PromptOptimizer", FakePromptOptimizer)

    orchestrator = core_module.CortexOrchestrator()

    assert isinstance(orchestrator._prompt_optimizer, FakePromptOptimizer)
    assert orchestrator._prompt_optimizer.provider == "openai"


def test_orchestrator_prompt_optimizer_receives_conversation_context(monkeypatch):
    seen_payload = {}

    class FakePromptOptimizer:
        def __init__(self, *, provider):
            self.provider = provider

        def optimize_prompt(self, payload):
            seen_payload.update(payload)
            return {
                "optimized_prompt": "Turn the OpenAI and Claude comparison into a table.",
                "steps": ["used conversation context"],
                "metrics": {},
            }

    _disable_research_init(monkeypatch)
    monkeypatch.setenv("ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION", "true")
    monkeypatch.setenv("PROMPT_OPTIMIZER_PROVIDER", "openai")
    monkeypatch.setattr(core_module, "PromptOptimizer", FakePromptOptimizer)

    orchestrator = core_module.CortexOrchestrator()
    context = UserContext(
        session_id="session-1",
        conversation_history=[
            {"role": "user", "content": "Compare OpenAI and Claude."},
            {"role": "assistant", "content": "OpenAI is faster. Claude is more cautious."},
        ],
    )

    prepared = orchestrator.prepare_messages_for_turn(
        prompt="Write it as a table",
        context=context,
        research_mode="off",
    )

    assert seen_payload["prompt"] == "Write it as a table"
    assert seen_payload["context"]["session_id"] == "session-1"
    assert seen_payload["context"]["conversation_history"] == context.conversation_history
    assert prepared["prompt"] == "Turn the OpenAI and Claude comparison into a table."
