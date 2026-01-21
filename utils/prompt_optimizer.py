"""
Prompt Optimizer Module

This module provides functionality to optimize user-provided text prompts using OpenAI APIs.
It accepts structured input and returns detailed JSON output with optimization data.
"""

import json
import time
from typing import Dict, Any, Optional, List
from api.openai_client import OpenAIClient
from utils.logger import get_logger

logger = get_logger(__name__)


class PromptOptimizer:
    """
    Optimizes text prompts using OpenAI APIs.
    
    Provides multi-stage validation, self-correction mechanisms, and structured output
    conforming to a strict JSON schema.
    """
    
    # Output JSON schema definition
    OUTPUT_SCHEMA = {
        "type": "object",
        "required": ["optimized_prompt"],
        "properties": {
            "optimized_prompt": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {"type": "string"}
            },
            "explanations": {
                "type": "array",
                "items": {"type": "string"}
            },
            "metrics": {"type": "object"},
            "error": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "details": {}
                },
                "required": ["message"]
            }
        }
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3
    ):
        """
        Initialize the PromptOptimizer.
        
        Args:
            api_key: OpenAI API key (if None, will use from environment)
            model: OpenAI model to use for optimization (default: gpt-4o-mini)
            max_retries: Maximum number of retry attempts for API calls
        """
        # Import config to get API key if not provided
        if api_key is None:
            from config.config import Config
            config = Config()
            api_key = config.OPENAI_API_KEY
            
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in .env or pass api_key parameter.")
        
        self.client = OpenAIClient(api_key=api_key, model_name=model)
        self.model = model
        self.max_retries = max_retries
        
        logger.info(
            "PromptOptimizer initialized",
            extra={"extra_fields": {"model": model, "max_retries": max_retries}}
        )
    
    def optimize_prompt(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
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
                "Input validation failed",
                extra={"extra_fields": {"error": validation_error}}
            )
            return validation_error
        
        prompt = input_data["prompt"]
        settings = input_data.get("settings", {})
        
        logger.info(
            "Starting prompt optimization",
            extra={"extra_fields": {
                "prompt_length": len(prompt),
                "has_settings": bool(settings)
            }}
        )
        
        # Stage 2: Optimize with OpenAI API (with retries)
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._call_openai_for_optimization(prompt, settings, attempt)
                
                # Stage 3: Validate output
                if self._is_valid_output(result):
                    elapsed_ms = int((time.time() - request_start) * 1000)
                    logger.info(
                        "Prompt optimization successful",
                        extra={"extra_fields": {
                            "attempt": attempt,
                            "elapsed_ms": elapsed_ms,
                            "has_steps": "steps" in result,
                            "has_explanations": "explanations" in result,
                            "has_metrics": "metrics" in result
                        }}
                    )
                    return result
                else:
                    logger.warning(
                        "Output validation failed, retrying with explicit schema",
                        extra={"extra_fields": {"attempt": attempt}}
                    )
                    # Self-correction: retry with explicit schema instructions
                    continue
                    
            except Exception as e:
                logger.error(
                    f"Optimization attempt {attempt} failed",
                    extra={"extra_fields": {
                        "attempt": attempt,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }}
                )
                
                if attempt == self.max_retries:
                    # Final attempt failed, return error
                    return {
                        "optimized_prompt": prompt,  # Return original as fallback
                        "error": {
                            "message": f"Failed to optimize prompt after {self.max_retries} attempts",
                            "details": {
                                "last_error": str(e),
                                "error_type": type(e).__name__
                            }
                        }
                    }
                
                # Wait before retry (exponential backoff)
                wait_time = 2 ** (attempt - 1)
                logger.info(
                    f"Waiting {wait_time}s before retry",
                    extra={"extra_fields": {"wait_seconds": wait_time}}
                )
                time.sleep(wait_time)
        
        # Should not reach here, but return error as fallback
        return {
            "optimized_prompt": prompt,
            "error": {
                "message": "Optimization failed: maximum retries exceeded",
                "details": {"max_retries": self.max_retries}
            }
        }
    
    def _validate_input(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
                    "details": {"received_type": type(input_data).__name__}
                }
            }
        
        # Check for required 'prompt' field
        if "prompt" not in input_data:
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: 'prompt' field is required",
                    "details": {"received_keys": list(input_data.keys())}
                }
            }
        
        # Validate prompt is a non-empty string
        prompt = input_data["prompt"]
        if not isinstance(prompt, str):
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: 'prompt' must be a string",
                    "details": {"received_type": type(prompt).__name__}
                }
            }
        
        if not prompt.strip():
            return {
                "optimized_prompt": "",
                "error": {
                    "message": "Invalid input: 'prompt' cannot be empty",
                    "details": {}
                }
            }
        
        # Validate settings if provided
        if "settings" in input_data:
            settings = input_data["settings"]
            if not isinstance(settings, dict):
                return {
                    "optimized_prompt": prompt,
                    "error": {
                        "message": "Invalid input: 'settings' must be a dictionary",
                        "details": {"received_type": type(settings).__name__}
                    }
                }
        
        return None  # Valid input
    
    def _call_openai_for_optimization(
        self,
        prompt: str,
        settings: Dict[str, Any],
        attempt: int
    ) -> Dict[str, Any]:
        """
        Call OpenAI API to optimize the prompt.
        
        Args:
            prompt: The prompt to optimize
            settings: Additional settings for optimization
            attempt: Current attempt number (for logging)
        
        Returns:
            Dictionary with optimization results
        
        Raises:
            Exception: If OpenAI API call fails
        """
        # Build the system message with instructions
        system_message = self._build_system_message(attempt)
        
        # Build the user message
        user_message = self._build_user_message(prompt, settings)
        
        # Call OpenAI API
        response = self.client.get_completion(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Check for API errors
        if response.is_error:
            error_msg = f"OpenAI API error: {response.error.code} - {response.error.message}"
            logger.error(
                error_msg,
                extra={"extra_fields": {
                    "error_code": response.error.code,
                    "retryable": response.error.retryable
                }}
            )
            raise Exception(error_msg)
        
        # Parse the response
        return self._parse_openai_response(response.text, prompt)
    
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
    
    def _build_user_message(self, prompt: str, settings: Dict[str, Any]) -> str:
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
    
    def _parse_openai_response(self, response_text: str, original_prompt: str) -> Dict[str, Any]:
        """
        Parse OpenAI response into structured output.
        
        Args:
            response_text: Raw text response from OpenAI
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
                "Failed to parse OpenAI response as JSON",
                extra={"extra_fields": {
                    "error": str(e),
                    "response_preview": response_text[:200]
                }}
            )
            raise Exception(f"Invalid JSON response from OpenAI: {e}")
        except Exception as e:
            logger.error(
                "Failed to process OpenAI response",
                extra={"extra_fields": {"error": str(e)}}
            )
            raise
    
    def _is_valid_output(self, output: Dict[str, Any]) -> bool:
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
            logger.error(
                "Output validation error",
                extra={"extra_fields": {"error": str(e)}}
            )
            return False
