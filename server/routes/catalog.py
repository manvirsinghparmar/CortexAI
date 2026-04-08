"""Provider and model discovery endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config.provider_catalog import get_provider_catalog, get_provider_ids
from orchestrator.model_registry import ModelRegistry
from server.dependencies import get_auth
from server.schemas.responses import (
    ModelCatalogItemDTO,
    ModelsCatalogResponseDTO,
    ProviderCatalogItemDTO,
    ProvidersCatalogResponseDTO,
)

router = APIRouter(prefix="/v1", tags=["Catalog"])


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_provider(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def _validate_provider_or_400(provider: str | None) -> str | None:
    provider_norm = _normalize_provider(provider)
    if provider_norm is None:
        return None

    allowed = set(get_provider_ids())
    if provider_norm not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported provider '{provider_norm}'. "
                f"Supported providers: {allowed_text}"
            ),
        )
    return provider_norm


def _model_to_dto(candidate) -> ModelCatalogItemDTO:
    return ModelCatalogItemDTO(
        provider=candidate.provider,
        model=candidate.model_name,
        tier=candidate.tier.value,
        input_cost_per_1m=float(candidate.input_cost_per_1m),
        output_cost_per_1m=float(candidate.output_cost_per_1m),
        context_limit=int(candidate.context_limit),
        tags=list(candidate.tags or []),
        enabled=bool(candidate.enabled),
        supports_image_input=bool(getattr(candidate, "supports_image_input", False)),
        supported_attachment_mime_types=list(
            getattr(candidate, "supported_attachment_mime_types", []) or []
        ),
        max_attachment_bytes=getattr(candidate, "max_attachment_bytes", None),
        max_attachments_per_request=getattr(candidate, "max_attachments_per_request", None),
    )


@router.get("/providers", response_model=ProvidersCatalogResponseDTO)
async def list_providers(
    auth=Depends(get_auth),
):
    """List discoverable providers and metadata for API/front-end clients."""
    _ = auth
    catalog = get_provider_catalog()
    registry = ModelRegistry.from_yaml()

    items: list[ProviderCatalogItemDTO] = []
    for spec in catalog.provider_specs():
        all_models = registry.list_models(spec.provider_id, include_disabled=True)
        enabled_models = [model for model in all_models if model.enabled]
        items.append(
            ProviderCatalogItemDTO(
                provider=spec.provider_id,
                label=spec.label,
                api_key_env=spec.api_key_env,
                default_model_env=spec.default_model_env,
                default_model=spec.default_model,
                byok_supported=spec.byok_supported,
                capabilities=list(spec.capabilities),
                ui=dict(spec.ui),
                model_count=len(all_models),
                enabled_model_count=len(enabled_models),
            )
        )

    return ProvidersCatalogResponseDTO(
        providers=items,
        total=len(items),
        timestamp=_utc_now_iso(),
    )


@router.get("/models", response_model=ModelsCatalogResponseDTO)
async def list_models(
    provider: str | None = Query(default=None),
    enabled_only: bool = Query(default=True),
    auth=Depends(get_auth),
):
    """List discoverable models, optionally filtered by provider."""
    _ = auth
    provider_norm = _validate_provider_or_400(provider)
    registry = ModelRegistry.from_yaml()

    candidates = registry.list_models(
        provider=provider_norm,
        include_disabled=not enabled_only,
    )
    items = [_model_to_dto(candidate) for candidate in candidates]
    items.sort(key=lambda item: (item.provider, item.model))

    return ModelsCatalogResponseDTO(
        provider=provider_norm,
        enabled_only=enabled_only,
        models=items,
        total=len(items),
        timestamp=_utc_now_iso(),
    )
