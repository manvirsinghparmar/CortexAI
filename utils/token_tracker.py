from typing import Dict, Any, Optional, Union
from datetime import datetime

# Import UnifiedResponse for type hints (import at runtime to avoid circular deps)
try:
    from models.unified_response import UnifiedResponse
except ImportError:
    UnifiedResponse = None

class TokenTracker:
    """
    A class to track token usage across multiple API calls for any model.
    This is model-agnostic and can be used with any API that provides token usage information.
    """

    def __init__(self, model_type: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize a new TokenTracker instance with zeroed counters.

        Args:
            model_type: Optional model type for tracking purposes
            model_name: Optional model name for tracking purposes
        """
        self.model_type = model_type
        self.model_name = model_name
        self.reset()
    
    def reset(self) -> None:
        """Reset all token counters to zero."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.requests = 0
    
    def update(self, usage: Optional[Union[Dict[str, int], 'UnifiedResponse']]) -> None:
        """
        Update token counters with usage from an API call.

        Args:
            usage: Either:
                  - A dictionary containing token usage information with optional keys:
                    * prompt_tokens: Number of tokens in the prompt
                    * completion_tokens: Number of tokens in the completion
                    * total_tokens: Total tokens used (prompt + completion)
                  - A UnifiedResponse object (will extract token_usage automatically)
        """
        if not usage:
            return

        # Handle UnifiedResponse objects
        if UnifiedResponse and isinstance(usage, UnifiedResponse):
            self.requests += 1
            self.total_prompt_tokens += usage.token_usage.prompt_tokens
            self.total_completion_tokens += usage.token_usage.completion_tokens
            self.total_tokens += usage.token_usage.total_tokens
            return

        # Handle dict (backward compatibility)
        self.requests += 1
        self.total_prompt_tokens += usage.get('prompt_tokens', 0)
        self.total_completion_tokens += usage.get('completion_tokens', 0)
        self.total_tokens += usage.get('total_tokens', 0)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of token usage.
        
        Returns:
            A dictionary containing token usage statistics and timestamp.
        """
        return {
            'requests': self.requests,
            'prompt_tokens': self.total_prompt_tokens,
            'completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_tokens,
            'timestamp': datetime.now().isoformat()
        }
    
    def format_summary(self) -> str:
        """
        Format the token usage summary as a human-readable string.
        
        Returns:
            A formatted string with token usage information.
        """
        stats = self.get_summary()
        return (
            f"Requests: {stats['requests']}\n"
            f"Prompt tokens: {stats['prompt_tokens']}\n"
            f"Completion tokens: {stats['completion_tokens']}\n"
            f"Total tokens: {stats['total_tokens']}"
        )
