import json
import re

from models.unified_response import UnifiedResponse
from orchestrator.routing_types import PromptFeatures, RoutingConstraints, ValidationResult


class ResponseValidator:
    def __init__(self, thresholds: dict[str, int] | None = None):
        self._thresholds = thresholds or {}

    def validate(
        self,
        features: PromptFeatures,
        constraints: RoutingConstraints | None,
        response: UnifiedResponse,
    ) -> ValidationResult:
        if response.is_error:
            reason = "provider_error"
            if response.error and response.error.code in {"timeout", "rate_limit", "provider_error"}:
                reason = response.error.code
            return ValidationResult(ok=False, reason=reason, severity="high")

        if self._looks_like_refusal(response.text or ""):
            return ValidationResult(ok=False, reason="refusal", severity="medium")

        effective_strict = False
        if constraints and (constraints.strict_format or constraints.json_only):
            effective_strict = True
        if features.strict_format or features.has_strict_constraints:
            effective_strict = True

        if constraints and constraints.json_only:
            if not self._is_valid_json(response.text or ""):
                return ValidationResult(ok=False, reason="format_violation", severity="high")

        if response.finish_reason == "length":
            if features.has_analysis or features.has_code or effective_strict:
                return ValidationResult(ok=False, reason="truncated", severity="medium")

        min_chars = self._thresholds.get("validator_short_simple_chars", 40)
        if features.has_analysis or features.has_code or effective_strict:
            min_chars = self._thresholds.get("validator_short_complex_chars", 120)

        if response.text is not None and len(response.text) < min_chars:
            return ValidationResult(ok=False, reason="too_short", severity="medium")

        return ValidationResult(ok=True, reason="ok", severity="none")

    def _is_valid_json(self, text: str) -> bool:
        try:
            json.loads(text)
            return True
        except Exception:
            return False

    def _looks_like_refusal(self, text: str) -> bool:
        text_lower = text.lower()
        refusal_phrases = [
            "i'm sorry, but i can't assist",
            "i am sorry, but i can't assist",
            "i'm sorry, but i cannot assist",
            "i am sorry, but i cannot assist",
            "i can't assist with",
            "i cannot assist with",
            "i can't help with",
            "i cannot help with",
            "i'm unable to help with",
            "i am unable to help with",
            "modify or override my system instructions",
        ]
        if any(phrase in text_lower for phrase in refusal_phrases):
            return True

        return bool(
            re.search(
                r"\b(can(?:not|'t)|unable to|won't)\b.{0,40}\b(assist|help|comply|support)\b",
                text_lower,
                re.I | re.S,
            )
        )
