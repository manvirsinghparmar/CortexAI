"""Prompt Optimizer — enhances user prompts before sending to LLMs."""

import os
from typing import Optional, Tuple

from models.user_context import UserContext
from utils.logger import get_logger

logger = get_logger(__name__)

# System instruction passed as a leading system message so the optimizer LLM
# knows its role without contaminating the user prompt.
_SYSTEM_INSTRUCTION = (
    "You are a prompt optimization expert. "
    "Your task is to rewrite the given prompt to be clearer, more specific, "
    "and more likely to produce a detailed, accurate AI response. "
    "Preserve the original intent completely. "
    "Return ONLY the improved prompt text — no explanations, no preamble, no quotes."
)


class PromptOptimizer:
    """
    Uses a configured AI provider to optimize prompts before they are sent
    to the main chat/compare pipeline.

    Controlled by environment variables:
        ENABLE_PROMPT_OPTIMIZATION  — master on/off flag (default: false)
        PROMPT_OPTIMIZER_PROVIDER   — which provider to use (default: gemini)
        PROMPT_OPTIMIZER_MODEL      — model name (default: provider default)
        PROMPT_OPTIMIZER_MAX_RETRIES— unused placeholder for future retry logic
    """

    def __init__(self):
        self.provider = os.getenv("PROMPT_OPTIMIZER_PROVIDER", "gemini").lower()
        self.model = (
            os.getenv("PROMPT_OPTIMIZER_MODEL")
            or os.getenv("PROMPT_OPTIMIZER_GEMINI_MODEL")
            or None
        )
        self.max_retries = int(os.getenv("PROMPT_OPTIMIZER_MAX_RETRIES", "3"))

    def optimize(self, prompt: str, orchestrator) -> Tuple[str, bool]:
        """
        Optimize a prompt using the configured AI provider.

        Args:
            prompt:       The original user prompt.
            orchestrator: A CortexOrchestrator instance for making the LLM call.

        Returns:
            (optimized_prompt, was_optimized) — on any failure falls back to original.
        """
        if not prompt or not prompt.strip():
            return prompt, False

        # Pass the optimization system instruction as a system message in context
        context = UserContext(
            conversation_history=[
                {"role": "system", "content": _SYSTEM_INSTRUCTION}
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
                    "Prompt optimization failed — using original",
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

        except Exception as e:
            logger.error(
                f"PromptOptimizer error: {e}",
                extra={"extra_fields": {"error_type": type(e).__name__}},
            )
            return prompt, False
