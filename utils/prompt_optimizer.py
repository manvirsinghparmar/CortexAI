"""Prompt optimizer helpers used by orchestrator and API routes."""

import json
import os
import re
import time
from typing import Any, Tuple

from config.provider_catalog import (
    get_provider_api_key_envs,
    get_provider_default_model_envs,
    get_provider_default_models,
)
from models.unified_response import UnifiedResponse
from models.user_context import UserContext
from utils.logger import get_logger

logger = get_logger(__name__)

_PLAIN_SYSTEM_INSTRUCTION = (
    "You are a prompt optimization expert. "
    "Rewrite the given prompt to be clearer and more specific while preserving intent. "
    "Return only the improved prompt text."
)

_JSON_SYSTEM_INSTRUCTION = (
    "You are a prompt optimization expert. "
    "Rewrite the user prompt to be clearer and more specific while preserving intent exactly. "
    "Use any provided conversation context only to resolve references in the latest user prompt. "
    "Do not carry unrelated earlier topics into the rewrite. "
    "If the latest prompt is weak or vague, rewrite it into a clearer, actionable prompt by adding "
    "neutral structure, constraints, audience, output format, or success criteria that follow from "
    "the original intent. "
    "Only return the original prompt unchanged as optimized_prompt when it is already specific enough, "
    "context is insufficient, or a rewrite would be speculative or change intent. "
    "Do not answer the prompt. Do not add factual claims, conclusions, dates, names, or background information "
    "unless they are already present in the original prompt. "
    "Return strictly valid JSON with this schema: "
    '{"optimized_prompt": "string", "steps": ["string"], "explanations": ["string"], "metrics": {"key": number}}. '
    "Do not add markdown fences, commentary, or extra keys."
)

_CONTEXT_HINT_MAX_CHARS = 2000
_REFERENCE_CONTEXT_HINT_MAX_CHARS = 4000
_CONTEXT_MESSAGE_LIMIT = 4
_REFERENCE_CONTEXT_MESSAGE_LIMIT = 10
_CONTEXT_MESSAGE_MAX_CHARS = 500
_DEFAULT_MAX_OUTPUT_TOKENS = 450
_DEFAULT_TEMPERATURE = 0.2
_MIN_REMAINING_SECONDS_FOR_ATTEMPT = 0.75
_REFERENCE_DEPENDENT_PATTERNS = (
    r"\b(what|how|why) about (it|that|this|them|those|the first|the second|the third|the other|the same)\b",
    r"^(and|also|same|do|make|rewrite|improve|fix|compare|explain)\s+(it|that|this|them|those)$",
    r"^(and|also|same|do|make|rewrite|improve|fix|compare|explain)\s+(the first|the second|the other)\b",
    r"\b(the first one|the second one|the third one|the previous|the above|earlier|same one|other one)\b",
    r"^i was talking about\b",
    r"^(who|what|why|how|where|when|how many|how much)\b.{0,120}\b(their|its)\b",
    r"^(give me|provide|show me|create|make)\b.{0,120}\b(the|that|those)\s+(detailed\s+)?(range|breakdown|summary|timeline|list|comparison|estimate|estimates|details)\b",
    r"\b(organization|group|entity|topic|item|subject)\s+in\s+question\b",
)
_WEAK_GENERIC_PHRASES = (
    "write something",
    "make this better",
    "make it better",
    "fix this",
    "improve this",
    "help me with",
    "tell me about",
    "explain",
    "summarize this",
    "compare",
)
_OUTPUT_CUES = (
    "plan",
    "steps",
    "table",
    "json",
    "bullets",
    "summary",
    "checklist",
    "implementation",
    "code",
    "example",
    "format",
    "criteria",
)
_CONSTRAINT_CUES = (
    "for ",
    "with ",
    "without ",
    "including ",
    "exclude ",
    "do not ",
    "don't ",
    "under ",
    "as a ",
    "audience",
    "target",
    "because",
)
_UNRESOLVED_PLACEHOLDER_PATTERNS = (
    r"\[[^\]\n]{0,80}\b(specific|topic|item|subject|organization|group|entity|person|name|date|number|range|context|placeholder|insert|fill in)\b[^\]\n]{0,80}\]",
    r"\{[^\}\n]{0,80}\b(specific|topic|item|subject|organization|group|entity|person|name|date|number|range|context|placeholder|insert|fill in)\b[^\}\n]{0,80}\}",
    r"<[^\>\n]{0,80}\b(specific|topic|item|subject|organization|group|entity|person|name|date|number|range|context|placeholder|insert|fill in)\b[^\>\n]{0,80}>",
    r"\b(specific|given|relevant)\s+(topic|item|subject|organization|group|entity|case|matter|issue)\b",
    r"\b(topic|item|subject|organization|group|entity|case|matter|issue)\s+in\s+question\b",
)

_DEFAULT_MODELS = get_provider_default_models()
_DEFAULT_MODEL_ENVS = get_provider_default_model_envs()
_API_KEY_ENVS = get_provider_api_key_envs()


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.0, maximum: float = 2.0) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


class PromptOptimizer:
    """
    Optimize prompts before main model execution.

    Supports two modes:
    - optimize(prompt, orchestrator): route-level flow using orchestrator.ask
    - optimize_prompt(payload): direct provider client flow used by orchestrator internals
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        self.provider = (provider or os.getenv("PROMPT_OPTIMIZER_PROVIDER", "gemini")).lower()
        self.model = model or os.getenv("PROMPT_OPTIMIZER_MODEL") or self._default_model_for_provider(
            self.provider
        )
        self.max_retries = max_retries or int(os.getenv("PROMPT_OPTIMIZER_MAX_RETRIES", "3"))
        self.max_output_tokens = _env_int(
            "PROMPT_OPTIMIZER_MAX_OUTPUT_TOKENS", _DEFAULT_MAX_OUTPUT_TOKENS
        )
        self.temperature = _env_float("PROMPT_OPTIMIZER_TEMPERATURE", _DEFAULT_TEMPERATURE)
        self._api_key = api_key
        self._client = client

    def _default_model_for_provider(self, provider: str) -> str:
        env_key = _DEFAULT_MODEL_ENVS.get(provider)
        default_model = _DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        if not env_key:
            return default_model
        return os.getenv(env_key, default_model)

    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key

        env_name = _API_KEY_ENVS.get(self.provider)
        if not env_name:
            raise ValueError(f"Unsupported provider for prompt optimizer: {self.provider}")
        api_key = os.getenv(env_name, "")
        if not api_key:
            raise ValueError(f"{env_name} not set for prompt optimizer provider '{self.provider}'")
        return api_key

    def _create_client(self):
        api_key = self._resolve_api_key()
        model_name = self.model

        if self.provider == "openai":
            from api.openai_client import OpenAIClient

            return OpenAIClient(api_key=api_key, model_name=model_name)
        if self.provider == "gemini":
            from api.google_gemini_client import GeminiClient

            return GeminiClient(api_key=api_key, model_name=model_name)
        if self.provider == "deepseek":
            from api.deepseek_client import DeepSeekClient

            return DeepSeekClient(api_key=api_key, model_name=model_name)
        if self.provider == "grok":
            from api.grok_client import GrokClient

            return GrokClient(api_key=api_key, model_name=model_name)
        if self.provider == "claude":
            from api.claude_client import ClaudeClient

            return ClaudeClient(api_key=api_key, model_name=model_name)

        raise ValueError(f"Unsupported provider for prompt optimizer: {self.provider}")

    def _get_client(self):
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _error_payload(self, message: str, code: str = "bad_request") -> dict[str, Any]:
        return {"error": {"code": code, "message": message}}

    def _validate_input(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return self._error_payload("Input must be a dictionary")

        if "prompt" not in payload:
            return self._error_payload("Missing required field: prompt")

        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return self._error_payload("Prompt must be a string")
        if not prompt.strip():
            return self._error_payload("Prompt cannot be empty")

        settings = payload.get("settings")
        if settings is not None and not isinstance(settings, dict):
            return self._error_payload("settings must be a dictionary")

        context_hint = payload.get("context_hint")
        if context_hint is not None and not isinstance(context_hint, str):
            return self._error_payload("context_hint must be a string")

        context = payload.get("context")
        if context is not None and not isinstance(context, dict):
            return self._error_payload("context must be a dictionary")

        max_retries = payload.get("max_retries")
        if max_retries is not None:
            try:
                if int(max_retries) < 1:
                    return self._error_payload("max_retries must be greater than 0")
            except (TypeError, ValueError):
                return self._error_payload("max_retries must be an integer")

        return None

    def _is_valid_output(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        optimized = payload.get("optimized_prompt")
        if not isinstance(optimized, str) or not optimized.strip():
            return False

        steps = payload.get("steps")
        if steps is not None and (
            not isinstance(steps, list) or any(not isinstance(item, str) for item in steps)
        ):
            return False

        explanations = payload.get("explanations")
        if explanations is not None and (
            not isinstance(explanations, list)
            or any(not isinstance(item, str) for item in explanations)
        ):
            return False

        metrics = payload.get("metrics")
        if metrics is not None and not isinstance(metrics, dict):
            return False

        return True

    def _strip_markdown_fences(self, text: str) -> str:
        raw = text.strip()
        if raw.startswith("```") and raw.endswith("```"):
            lines = raw.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return raw

    def _load_optimizer_json(self, text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except Exception as first_exc:
            try:
                parsed, end_index = json.JSONDecoder().raw_decode(text)
            except Exception as exc:
                raise ValueError("Invalid JSON from optimizer response") from exc

            trailing = text[end_index:].strip()
            if trailing and set(trailing) - {"}"}:
                raise ValueError("Invalid JSON from optimizer response") from first_exc

        if not isinstance(parsed, dict):
            raise ValueError("Invalid optimizer response schema: missing or invalid optimized_prompt")
        return parsed

    def _parse_ai_response(self, response_text: str, original_prompt: str) -> dict[str, Any]:
        cleaned = self._strip_markdown_fences(response_text or "")
        parsed = self._load_optimizer_json(cleaned)

        if not self._is_valid_output(parsed):
            raise ValueError("Invalid optimizer response schema: missing or invalid optimized_prompt")

        optimized_prompt = parsed["optimized_prompt"].strip() or original_prompt
        if self._looks_like_answer_instead_of_prompt(original_prompt, optimized_prompt):
            raise ValueError("Optimizer response appears to answer the prompt instead of rewriting it")
        if self._contains_introduced_placeholder(original_prompt, optimized_prompt):
            raise ValueError("Optimizer response contains unresolved placeholder text")

        result: dict[str, Any] = {
            "optimized_prompt": optimized_prompt,
            "steps": parsed.get("steps", []),
            "explanations": parsed.get("explanations", []),
            "metrics": parsed.get("metrics", {}),
        }
        return result

    @staticmethod
    def _normalized_prompt_text(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _same_prompt(cls, original_prompt: str, optimized_prompt: str) -> bool:
        return cls._normalized_prompt_text(original_prompt) == cls._normalized_prompt_text(
            optimized_prompt
        )

    def classify_prompt_quality(
        self,
        prompt: str,
        *,
        context_hint: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Classify prompt specificity without logging or sending extra model calls."""
        compact = self._normalized_prompt_text(prompt)
        if not compact:
            return "weak"

        if any(re.search(pattern, compact) for pattern in _REFERENCE_DEPENDENT_PATTERNS):
            return "reference_dependent"

        words = re.findall(r"[a-z0-9_/-]+", compact)
        word_count = len(words)
        has_context = bool(context_hint) or bool(self._compact_context(context))
        if has_context and word_count <= 8 and any(term in compact for term in ("this", "that", "it")):
            return "reference_dependent"

        starts_generic = any(compact.startswith(phrase) for phrase in _WEAK_GENERIC_PHRASES)
        has_output_cue = any(cue in compact for cue in _OUTPUT_CUES)
        has_constraint_cue = any(cue in compact for cue in _CONSTRAINT_CUES)
        has_detail_cue = any(token in compact for token in (":", "/", "-", "_")) or any(
            char.isdigit() for char in compact
        )
        specificity_score = sum((has_output_cue, has_constraint_cue, has_detail_cue))

        if word_count <= 8 or starts_generic:
            return "weak"
        if word_count >= 14 and specificity_score >= 2:
            return "strong"
        if word_count >= 10 and specificity_score >= 3:
            return "strong"
        return "weak"

    @staticmethod
    def _looks_like_answer_instead_of_prompt(original_prompt: str, optimized_prompt: str) -> bool:
        original = " ".join(str(original_prompt or "").split())
        optimized = str(optimized_prompt or "").strip()
        if not original or not optimized:
            return False

        original_len = max(len(original), 1)
        optimized_len = len(optimized)
        paragraph_count = len([part for part in optimized.splitlines() if part.strip()])
        has_markdown_structure = any(marker in optimized for marker in ("**", "##", "\n-", "\n*"))
        has_many_sentences = sum(optimized.count(token) for token in (".", "!", "?")) >= 4

        if original_len <= 120 and optimized_len > max(500, original_len * 8):
            return True
        if original_len <= 120 and paragraph_count >= 3:
            return True
        if original_len <= 120 and has_markdown_structure and optimized_len > original_len * 4:
            return True
        if original_len <= 80 and has_many_sentences and optimized_len > original_len * 5:
            return True

        return False

    @classmethod
    def _contains_introduced_placeholder(
        cls,
        original_prompt: str,
        optimized_prompt: str,
    ) -> bool:
        original = cls._normalized_prompt_text(original_prompt)
        optimized = cls._normalized_prompt_text(optimized_prompt)
        if not optimized:
            return False

        for pattern in _UNRESOLVED_PLACEHOLDER_PATTERNS:
            for match in re.finditer(pattern, optimized, flags=re.IGNORECASE):
                placeholder = " ".join(match.group(0).split()).lower()
                if placeholder and placeholder not in original:
                    return True
        return False

    @staticmethod
    def _trim_context_text(text: Any, limit: int = _CONTEXT_MESSAGE_MAX_CHARS) -> str:
        compact = " ".join(str(text or "").split())
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip()

    @staticmethod
    def _context_message_limit(prompt_quality: str | None = None) -> int:
        if prompt_quality == "reference_dependent":
            return _REFERENCE_CONTEXT_MESSAGE_LIMIT
        return _CONTEXT_MESSAGE_LIMIT

    @staticmethod
    def _context_hint_limit(prompt_quality: str | None = None) -> int:
        if prompt_quality == "reference_dependent":
            return _REFERENCE_CONTEXT_HINT_MAX_CHARS
        return _CONTEXT_HINT_MAX_CHARS

    def _compact_context(self, context: Any, *, prompt_quality: str | None = None) -> str:
        if not isinstance(context, dict):
            return ""

        history = context.get("conversation_history")
        if not isinstance(history, list):
            return ""

        messages: list[dict[str, str]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = self._trim_context_text(item.get("content"))
            if content:
                messages.append({"role": role, "content": content})

        if not messages:
            return ""

        selected = messages[-self._context_message_limit(prompt_quality):]
        hint = "\n".join(f"- {item['role']}: {item['content']}" for item in selected)
        return hint[: self._context_hint_limit(prompt_quality)].rstrip()

    def _build_user_message(
        self,
        prompt: str,
        settings: dict[str, Any] | None,
        context_hint: str | None = None,
        context: dict[str, Any] | None = None,
        prompt_quality: str | None = None,
        retry_reason: str | None = None,
    ) -> str:
        parts: list[str] = []
        compact_context_hint = self._trim_context_text(
            context_hint,
            self._context_hint_limit(prompt_quality),
        )
        if not compact_context_hint:
            compact_context_hint = self._compact_context(context, prompt_quality=prompt_quality)

        if compact_context_hint:
            parts.append(
                "Conversation context for reference resolution only:\n"
                f"{compact_context_hint}"
            )

        parts.append(f"Latest user prompt to rewrite:\n{prompt}")

        if prompt_quality:
            parts.append(f"Prompt quality classification: {prompt_quality}")
            if prompt_quality == "weak":
                parts.append(
                    "This prompt is weak or vague. Rewrite it into a clearer prompt with "
                    "neutral specificity while preserving the user's intent."
                )

        if retry_reason == "unchanged_weak_prompt":
            parts.append(
                "Previous optimizer attempt returned the original prompt unchanged. Because this "
                "prompt is weak, provide a meaningful rewrite unless doing so would change intent."
            )

        if settings:
            settings_blob = json.dumps(settings, ensure_ascii=False)
            parts.append(f"Optimization settings:\n{settings_blob}")

        parts.append(
            "Rewrite only the latest prompt. Keep it as the original prompt if context is insufficient."
        )
        return "\n\n".join(parts)

    def _effective_max_retries(self, payload: dict[str, Any]) -> int:
        raw_value = payload.get("max_retries")
        if raw_value is None:
            return max(1, self.max_retries)
        try:
            return max(1, int(raw_value))
        except (TypeError, ValueError):
            return max(1, self.max_retries)

    @staticmethod
    def _coerce_deadline_at(value: Any) -> float | None:
        if value is None:
            return None
        try:
            deadline_at = float(value)
        except (TypeError, ValueError):
            return None
        return deadline_at if deadline_at > 0 else None

    @staticmethod
    def _has_time_for_attempt(deadline_at: float | None) -> bool:
        if deadline_at is None:
            return True
        return (deadline_at - time.monotonic()) >= _MIN_REMAINING_SECONDS_FOR_ATTEMPT

    @staticmethod
    def _attach_metadata(
        result: dict[str, Any],
        *,
        prompt_quality: str,
        attempt_count: int,
        retry_reasons: list[str],
        unchanged_retry_used: bool,
    ) -> dict[str, Any]:
        result["prompt_quality"] = prompt_quality
        result["attempt_count"] = attempt_count
        result["retry_reasons"] = retry_reasons
        result["unchanged_retry_used"] = unchanged_retry_used
        return result

    def optimize_prompt(self, payload: Any) -> dict[str, Any]:
        """
        Optimize prompt using direct provider client path.

        Returns a normalized dict and never raises for runtime/provider failures.
        """
        validation_error = self._validate_input(payload)
        if validation_error:
            return validation_error

        original_prompt = str(payload["prompt"]).strip()
        settings = payload.get("settings") if isinstance(payload, dict) else None
        context_hint = payload.get("context_hint") if isinstance(payload, dict) else None
        context = payload.get("context") if isinstance(payload, dict) else None
        max_retries = self._effective_max_retries(payload)
        deadline_at = self._coerce_deadline_at(payload.get("deadline_at"))
        prompt_quality = self.classify_prompt_quality(
            original_prompt,
            context_hint=context_hint,
            context=context,
        )

        try:
            client = self._get_client()
        except Exception as exc:
            return {
                "optimized_prompt": original_prompt,
                "steps": [],
                "explanations": [],
                "metrics": {},
                "prompt_quality": prompt_quality,
                "attempt_count": 0,
                "retry_reasons": ["client_unavailable"],
                "unchanged_retry_used": False,
                "error": {
                    "code": "optimization_failed",
                    "message": str(exc) or "Prompt optimization client unavailable",
                },
            }

        last_error: str | None = None
        last_error_code = "optimization_failed"
        attempt_count = 0
        retry_reasons: list[str] = []
        unchanged_retry_used = False
        next_retry_reason: str | None = None
        completion_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        if self.provider == "openai":
            completion_kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(1, max_retries + 1):
            if not self._has_time_for_attempt(deadline_at):
                last_error = "Optimizer deadline reached before starting another attempt"
                last_error_code = "optimization_deadline_exceeded"
                break

            attempt_count = attempt
            response: UnifiedResponse = client.get_completion(
                messages=[
                    {"role": "system", "content": _JSON_SYSTEM_INSTRUCTION},
                    {
                        "role": "user",
                        "content": self._build_user_message(
                            original_prompt,
                            settings,
                            context_hint=context_hint,
                            context=context,
                            prompt_quality=prompt_quality,
                            retry_reason=next_retry_reason,
                        ),
                    },
                ],
                **completion_kwargs,
            )
            next_retry_reason = None

            if response.is_error:
                last_error = response.error.message if response.error else "Optimizer request failed"
                last_error_code = "optimization_failed"
                retry_reasons.append("provider_error")
                continue

            try:
                result = self._parse_ai_response(response.text, original_prompt)
            except Exception as exc:
                last_error = str(exc)
                last_error_lower = last_error.lower()
                if (
                    "answer the prompt" in last_error_lower
                    or "unresolved placeholder" in last_error_lower
                ):
                    last_error_code = "optimization_rejected"
                    retry_reasons.append("optimizer_output_rejected")
                else:
                    retry_reasons.append("invalid_optimizer_response")
                continue

            unchanged = self._same_prompt(original_prompt, result["optimized_prompt"])
            if (
                unchanged
                and prompt_quality == "weak"
                and not unchanged_retry_used
                and attempt < max_retries
                and self._has_time_for_attempt(deadline_at)
            ):
                unchanged_retry_used = True
                retry_reasons.append("unchanged_weak_prompt")
                next_retry_reason = "unchanged_weak_prompt"
                last_error = "Optimizer returned original prompt unchanged for weak input"
                last_error_code = "unchanged_after_retry"
                continue

            if unchanged and prompt_quality == "weak" and (unchanged_retry_used or attempt_count > 1):
                result["fallback_reason"] = "unchanged_after_retry"

            return self._attach_metadata(
                result,
                prompt_quality=prompt_quality,
                attempt_count=attempt_count,
                retry_reasons=retry_reasons,
                unchanged_retry_used=unchanged_retry_used,
            )

        return {
            "optimized_prompt": original_prompt,
            "steps": [],
            "explanations": [],
            "metrics": {},
            "prompt_quality": prompt_quality,
            "attempt_count": attempt_count,
            "retry_reasons": retry_reasons,
            "unchanged_retry_used": unchanged_retry_used,
            "error": {
                "code": last_error_code,
                "message": last_error or "Prompt optimization failed",
            },
        }

    def optimize(self, prompt: str, orchestrator) -> Tuple[str, bool]:
        """
        Optimize prompt using orchestrator path (used by /v1/optimize route).
        """
        if not prompt or not prompt.strip():
            return prompt, False

        context = UserContext(
            conversation_history=[
                {"role": "system", "content": _PLAIN_SYSTEM_INSTRUCTION}
            ]
        )

        try:
            response = orchestrator.ask(
                prompt=prompt,
                model_type=self.provider,
                model_name=self.model,
                context=context,
                token_tracker=None,
            )

            if response.is_error or not response.text:
                logger.warning(
                    "Prompt optimization failed - using original",
                    extra={"extra_fields": {
                        "error": str(response.error) if response.error else "empty_response"
                    }},
                )
                return prompt, False

            optimized = response.text.strip()
            if not optimized:
                return prompt, False

            logger.info(
                "Prompt optimized successfully",
                extra={"extra_fields": {
                    "original_len": len(prompt),
                    "optimized_len": len(optimized),
                    "provider": self.provider,
                }},
            )
            return optimized, True

        except Exception as exc:
            logger.error(
                f"PromptOptimizer error: {exc}",
                extra={"extra_fields": {"error_type": type(exc).__name__}},
            )
            return prompt, False
