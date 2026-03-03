from config.provider_catalog import (
    get_byok_supported_providers,
    get_provider_api_key_envs,
    get_provider_catalog,
    get_provider_compare_default_models,
    get_provider_default_model_envs,
    get_provider_default_models,
    get_provider_ids,
    get_provider_labels,
)
from server import byok_service
from server.routes import chat as chat_route
from utils import prompt_optimizer


def test_provider_catalog_has_expected_baseline_providers():
    provider_ids = get_provider_ids()
    assert provider_ids == ["openai", "gemini", "deepseek", "grok", "claude"]


def test_provider_catalog_required_maps_are_present():
    provider_ids = get_provider_ids()
    api_key_envs = get_provider_api_key_envs()
    default_model_envs = get_provider_default_model_envs()
    default_models = get_provider_default_models()
    compare_models = get_provider_compare_default_models()
    labels = get_provider_labels()

    for provider in provider_ids:
        assert api_key_envs.get(provider)
        assert default_model_envs.get(provider)
        assert default_models.get(provider)
        assert compare_models.get(provider)
        assert labels.get(provider)


def test_chat_route_provider_allowlist_and_defaults_come_from_catalog():
    assert chat_route.DEFAULT_MODELS == get_provider_default_models()
    assert chat_route.DEFAULT_MODEL_ENVS == get_provider_default_model_envs()
    assert chat_route.SUPPORTED_PROVIDERS == tuple(get_provider_ids())


def test_byok_allowlist_comes_from_catalog():
    assert byok_service.ALLOWED_PROVIDERS == set(get_byok_supported_providers())


def test_prompt_optimizer_default_maps_come_from_catalog():
    assert prompt_optimizer._DEFAULT_MODELS == get_provider_default_models()
    assert prompt_optimizer._DEFAULT_MODEL_ENVS == get_provider_default_model_envs()
    assert prompt_optimizer._API_KEY_ENVS == get_provider_api_key_envs()


def test_provider_catalog_ui_metadata_exists_for_each_provider():
    catalog = get_provider_catalog()
    ui_metadata = catalog.ui_metadata()
    for provider in get_provider_ids():
        assert provider in ui_metadata
        assert isinstance(ui_metadata[provider], dict)
