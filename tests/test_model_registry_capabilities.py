from orchestrator.model_registry import ModelRegistry


def test_registry_exposes_attachment_capabilities():
    registry = ModelRegistry.from_yaml()

    openai_candidate = registry.find_model("openai", "gpt-4o-mini")
    assert openai_candidate is not None
    assert openai_candidate.supports_image_input is True
    assert "application/pdf" in openai_candidate.supported_attachment_mime_types
    assert openai_candidate.max_attachment_bytes == 20971520
    assert openai_candidate.max_attachments_per_request == 5

    deepseek_candidate = registry.find_model("deepseek", "deepseek-chat")
    assert deepseek_candidate is not None
    assert deepseek_candidate.supports_image_input is False
    assert deepseek_candidate.supported_attachment_mime_types == []
    assert deepseek_candidate.max_attachments_per_request == 0
