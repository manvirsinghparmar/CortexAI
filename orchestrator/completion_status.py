"""Normalize provider stop outcomes for API, persistence, and UI consumers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from models.unified_response import UnifiedResponse
from orchestrator.generation_policy import GenerationBudgetResolution


def completion_outcome(response: UnifiedResponse) -> tuple[str, str]:
    if response.is_error:
        return "failed", "error"

    finish_reason = str(response.finish_reason or "").strip().lower()
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    provider_reason = str(metadata.get("provider_finish_reason") or "").strip().lower()
    combined_reason = f"{finish_reason} {provider_reason}"

    if "context" in combined_reason and any(
        marker in combined_reason for marker in ("limit", "window", "exceed")
    ):
        return "incomplete", "context_limit"
    if finish_reason == "length" or "max_output" in combined_reason or "max_tokens" in combined_reason:
        return "incomplete", "token_limit"
    if finish_reason == "content_filter":
        return "incomplete", "content_filter"
    if finish_reason == "error":
        return "failed", "error"
    if finish_reason in {"stop", "tool"}:
        return "complete", "natural"
    return "complete", "unknown"


def attach_generation_budget(
    response: UnifiedResponse,
    resolution: GenerationBudgetResolution,
) -> UnifiedResponse:
    metadata: dict[str, Any] = dict(response.metadata or {})
    metadata["generation_budget"] = resolution.to_metadata()
    status, stop_cause = completion_outcome(response)
    metadata["completion_status"] = status
    metadata["stop_cause"] = stop_cause
    if (
        status == "incomplete"
        and stop_cause == "token_limit"
        and not str(response.text or "").strip()
        and int(response.token_usage.reasoning_tokens or 0) > 0
    ):
        metadata["reasoning_budget_exhausted"] = True
    return replace(
        response,
        metadata=metadata,
        reasoning_mode=resolution.effective_reasoning_mode,
    )
