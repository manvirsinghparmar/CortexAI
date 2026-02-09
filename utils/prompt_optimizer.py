"""
Prompt Optimizer Module

This module provides functionality to optimize user-provided text prompts using AI APIs.
Supports multiple providers: OpenAI and Google Gemini.
It accepts structured input and returns detailed JSON output with optimization data.
"""

import json
import os
import time
from typing import Any

from api.google_gemini_client import GeminiClient
from api.openai_client import OpenAIClient
from utils.logger import get_logger

logger = get_logger(__name__)


class PromptOptimizer:
    """
    Optimizes text prompts using AI APIs (OpenAI or Gemini).

    Provides multi-stage validation, self-correction mechanisms, and structured output
    conforming to a strict JSON schema.

    Supports multiple providers with automatic selection and fallback.
    """

    # Output JSON schema definition
    OUTPUT_SCHEMA = {
        "type": "object",
        "required": ["optimized_prompt"],
        "properties": {
            "optimized_prompt": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "explanations": {"type": "array", "items": {"type": "string"}},
            "metrics": {"type": "object"},
            "error": {
                "type": "object",
                "properties": {"message": {"type": "string"}, "details": {}},
                "required": ["message"],
            },
        },
    }

    def __init__(
        self,
        provider: str = "auto",
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
    ):
        """
        Initialize the PromptOptimizer.

        Args:
            provider: AI provider to use ('openai', 'gemini', or 'auto')
                     'auto' will use environment variable or default to openai
            api_key: API key (if None, will use from environment)
            model: Model to use (if None, uses provider default)
            max_retries: Maximum number of retry attempts for API calls
        """
        from config.config import Config

        config = Config()

        # Determine provider
        if provider == "auto":
            provider = os.getenv("PROMPT_OPTIMIZER_PROVIDER", "openai").lower()

        self.provider = provider
        self.max_retries = max_retries

        # Initialize client based on provider
        if provider == "openai":
            if api_key is None:
                api_key = config.OPENAI_API_KEY
            if not api_key:
                raise ValueError(
                    "OpenAI API key is required. Set OPENAI_API_KEY in .env or pass api_key parameter."
                )

            self.model = model or os.getenv("PROMPT_OPTIMIZER_MODEL", "gpt-4o-mini")
            self.client = OpenAIClient(api_key=api_key, model_name=self.model)

        elif provider == "gemini":
            if api_key is None:
                api_key = config.GOOGLE_GEMINI_API_KEY
            if not api_key:
                raise ValueError(
                    "Gemini API key is required. Set GOOGLE_GEMINI_API_KEY in .env or pass api_key parameter."
                )

            self.model = model or os.getenv("PROMPT_OPTIMIZER_GEMINI_MODEL", "gemini-2.0-flash-exp")
            self.client = GeminiClient(api_key=api_key, model_name=self.model)

        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'gemini'.")

        logger.info(
            "PromptOptimizer initialized",
            extra={
                "extra_fields": {
                    "provider": self.provider,
                    "model": self.model,
                    "max_retries": max_retries,
                }
            },
        )

    def optimize_prompt(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Optimize a user-provided text prompt.

        Args:
            input_data: Dictionary with the following structure:
                - prompt (str, required): The initial prompt text to optimize
                - settings (dict, optional): Supplementary settings or metadata

        Returns:
            Dictionary with the following structure:
                - optimized_prompt (str): The optimized prompt text
                - steps (list[str], optional): Intermediate optimization steps
                - explanations (list[str], optional): Explanations for optimizations
                - metrics (dict, optional): Quantitative metrics or scores
                - error (dict, optional): Error information if validation fails
        """
        request_start = time.time()

        # Stage 1: Input validation
        validation_error = self._validate_input(input_data)
        if validation_error:
            logger.warning(
                "Input validation failed", extra={"extra_fields": {"error": validation_error}}
            )
            return validation_error

        prompt = input_data["prompt"]
        settings = input_data.get("settings", {})

        logger.info(
            "Starting prompt optimization",
            extra={"extra_fields": {"prompt_length": len(prompt), "has_settings": bool(settings)}},
        )

        # Stage 2: Optimize with AI API (with retries)
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._call_ai_for_optimization(prompt, settings, attempt)

                # Stage 3: Validate output
                if self._is_valid_output(result):
                    elapsed_ms = int((time.time() - request_start) * 1000)
                    logger.info(
                        "Prompt optimization successful",
                        extra={
                            "extra_fields": {
                                "attempt": attempt,
                                "elapsed_ms": elapsed_ms,
                                "has_steps": "steps" in result,
                                "has_explanations": "explanations" in result,
                                "has_metrics": "metrics" in result,
                            }
                        },
                    )
                    return result
                else:
                    logger.warning(
                        "Output validation failed, retrying with explicit schema",
                        extra={"extra_fields": {"attempt": attempt}},
                    )
                    # Self-correction: retry with explicit schema instructions
                    continue

            except Exception as e:
                logger.error(
                    f"Optimization attempt {attempt} failed",
                    extra={
                        "extra_fields": {
                            "attempt": attempt,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        }
                    },
                )

                if attempt == self.max_retries:
                    # Final attempt failed, return error
                    return {
                        "optimized_prompt": prompt,  # Return original as fallback
                        "error": {
                            "message": f"Failed to optimize prompt after {self.max_retries} attempts",
                            "details": {"last_error": str(e), "error_type": type(e).__name__},
                        },
                    }

                # Wait before retry (exponential backoff)
                wait_time = 2 ** (attempt - 1)
                logger.info(
                    f"Waiting {wait_time}s before retry",
                    extra={"extra_fields": {"wait_seconds": wait_time}},
                )
                time.sleep(wait_time)

        # Should not reach here, but return error as fallback
        return {
            "optimized_prompt": prompt,
            "error": {
                "message": "Optimization failed: maximum retries exceeded",
                "details": {"max_retries": self.max_retries},
            },
        }

    def _validate_input(self, input_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Validate input data structure.

        Args:
            input_data: Input dictionary to validate

        Returns:
            Error dictionary if validation fails, None if valid
        """
        # Check if input is a dictionary
        if not isinstance(input_data, dict):
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: expected dictionary",
                    "details": {"received_type": type(input_data).__name__},
                },
            }

        # Check for required 'prompt' field
        if "prompt" not in input_data:
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: 'prompt' field is required",
                    "details": {"received_keys": list(input_data.keys())},
                },
            }

        # Validate prompt is a non-empty string
        prompt = input_data["prompt"]
        if not isinstance(prompt, str):
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: 'prompt' must be a string",
                    "details": {"received_type": type(prompt).__name__},
                },
            }

        if not prompt.strip():
            return {
                "optimized_prompt": "",
                "error": {"message": "Invalid input: 'prompt' cannot be empty", "details": {}},
            }

        # Validate settings if provided
        if "settings" in input_data:
            settings = input_data["settings"]
            if not isinstance(settings, dict):
                return {
                    "optimized_prompt": prompt,
                    "error": {
                        "message": "Invalid input: 'settings' must be a dictionary",
                        "details": {"received_type": type(settings).__name__},
                    },
                }

        return None  # Valid input

    def _call_ai_for_optimization(
        self, prompt: str, settings: dict[str, Any], attempt: int
    ) -> dict[str, Any]:
        """
        Call AI API to optimize the prompt.

        Args:
            prompt: The prompt to optimize
            settings: Additional settings for optimization
            attempt: Current attempt number (for logging)

        Returns:
            Dictionary with optimization results

        Raises:
            Exception: If AI API call fails
        """
        # Build the system message with instructions
        system_message = self._build_system_message(attempt)

        # Build the user message
        user_message = self._build_user_message(prompt, settings)

        # Call AI API (works for both OpenAI and Gemini via UnifiedResponse)
        response = self.client.get_completion(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        # Check for API errors
        if response.is_error:
            error_msg = f"{self.provider.upper()} API error: {response.error.code} - {response.error.message}"
            logger.error(
                error_msg,
                extra={
                    "extra_fields": {
                        "provider": self.provider,
                        "error_code": response.error.code,
                        "retryable": response.error.retryable,
                    }
                },
            )
            raise Exception(error_msg)

        # Parse the response
        return self._parse_ai_response(response.text, prompt)

    def _build_system_message(self, attempt: int) -> str:
        """
        Build the system message for OpenAI API.

        Args:
            attempt: Current attempt number (affects instructions)

        Returns:
            System message string
        """
        base_instructions = """You are an expert prompt engineer. Your task is to optimize user-provided prompts to make them clearer, more specific, and more effective.

When optimizing a prompt, you should:
1. Identify ambiguities and clarify them
2. Add relevant context where needed
3. Structure the prompt for better results
4. Ensure the prompt is specific and actionable
5. Maintain the original intent

You must respond with a valid JSON object following this exact schema:
{
  "optimized_prompt": "string (required) - The improved version of the prompt",
  "steps": ["string", ...] (optional) - Key steps taken during optimization,
  "explanations": ["string", ...] (optional) - Explanations for why changes were made,
  "metrics": {object} (optional) - Any quality scores or metrics (e.g., {"clarity_score": 8.5, "specificity_score": 9.0})
}

CRITICAL: Your response must be ONLY the JSON object, with no additional text before or after."""

        if attempt > 1:
            # Add stricter instructions for retry attempts
            base_instructions += "\n\nIMPORTANT: Previous attempt failed validation. Ensure your response is STRICTLY valid JSON with no markdown formatting, no code blocks, and no extra text."

        return base_instructions

    def _build_user_message(self, prompt: str, settings: dict[str, Any]) -> str:
        """
        Build the user message for OpenAI API.

        Args:
            prompt: The prompt to optimize
            settings: Additional settings

        Returns:
            User message string
        """
        message = f"Please optimize the following prompt:\n\n{prompt}"

        if settings:
            message += f"\n\nAdditional context/settings: {json.dumps(settings, indent=2)}"

        return message

    def _parse_ai_response(self, response_text: str, original_prompt: str) -> dict[str, Any]:
        """
        Parse AI response into structured output.

        Args:
            response_text: Raw text response from AI
            original_prompt: Original prompt (fallback)

        Returns:
            Parsed dictionary

        Raises:
            Exception: If parsing fails
        """
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            cleaned_text = response_text.strip()

            # Remove markdown code blocks if present
            if cleaned_text.startswith("```"):
                # Find the actual JSON content
                lines = cleaned_text.split("\n")
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines).strip()

            # Parse JSON
            result = json.loads(cleaned_text)

            # Ensure optimized_prompt exists
            if "optimized_prompt" not in result:
                raise ValueError("Missing required field: optimized_prompt")

            return result

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse {self.provider} response as JSON",
                extra={
                    "extra_fields": {
                        "provider": self.provider,
                        "error": str(e),
                        "response_preview": response_text[:200],
                    }
                },
            )
            raise Exception(f"Invalid JSON response from {self.provider}: {e}") from e
        except Exception as e:
            logger.error(
                f"Failed to process {self.provider} response",
                extra={"extra_fields": {"provider": self.provider, "error": str(e)}},
            )
            raise

    def _is_valid_output(self, output: dict[str, Any]) -> bool:
        """
        Validate output against schema.

        Args:
            output: Output dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required field
            if "optimized_prompt" not in output:
                return False

            if not isinstance(output["optimized_prompt"], str):
                return False

            # Check optional fields if present
            if "steps" in output:
                if not isinstance(output["steps"], list):
                    return False
                if not all(isinstance(s, str) for s in output["steps"]):
                    return False

            if "explanations" in output:
                if not isinstance(output["explanations"], list):
                    return False
                if not all(isinstance(e, str) for e in output["explanations"]):
                    return False

            if "metrics" in output:
                if not isinstance(output["metrics"], dict):
                    return False

            if "error" in output:
                if not isinstance(output["error"], dict):
                    return False
                if "message" not in output["error"]:
                    return False
                if not isinstance(output["error"]["message"], str):
                    return False

            return True

        except Exception as e:
            logger.error("Output validation error", extra={"extra_fields": {"error": str(e)}})
            return False
