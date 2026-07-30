from pathlib import Path

import pytest
import yaml

from orchestrator.model_registry import ModelRegistry
from server.billing.models import ModelBillingClass


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


def test_registry_exposes_explicit_billing_classes_separate_from_routing_tiers():
    registry = ModelRegistry.from_yaml()

    standard = registry.find_model("openai", "gpt-5.4-mini")
    advanced = registry.find_model("openai", "gpt-5.4")
    premium = registry.find_model("claude", "claude-opus-4-6")

    assert standard is not None
    assert standard.tier.value == "T2"
    assert standard.billing_class is ModelBillingClass.STANDARD
    assert advanced is not None
    assert advanced.billing_class is ModelBillingClass.ADVANCED
    assert premium is not None
    assert premium.billing_class is ModelBillingClass.PREMIUM
    assert premium.input_credit_multiplier == 6
    assert premium.output_credit_multiplier == 30
    assert premium.credit_usage_label == "Premium"
    assert premium.credit_pricing_version


def test_registry_missing_billing_class_fails_closed(tmp_path):
    data = yaml.safe_load(Path("config/model_registry.yaml").read_text(encoding="utf-8"))
    model = data["providers"]["openai"]["models"][0]
    model.pop("billing_class")
    path = tmp_path / "model_registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required fields"):
        ModelRegistry.from_yaml(str(path))


def test_registry_missing_credit_economics_fails_closed(tmp_path):
    data = yaml.safe_load(Path("config/model_registry.yaml").read_text(encoding="utf-8"))
    data["providers"]["openai"]["models"][0].pop("input_credit_multiplier")
    path = tmp_path / "model_registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required fields"):
        ModelRegistry.from_yaml(str(path))


def test_registry_rejects_unknown_billing_class(tmp_path):
    data = yaml.safe_load(Path("config/model_registry.yaml").read_text(encoding="utf-8"))
    data["providers"]["openai"]["models"][0]["billing_class"] = "vip"
    path = tmp_path / "model_registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid billing_class 'vip'"):
        ModelRegistry.from_yaml(str(path))
