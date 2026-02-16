import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

# Compare mode target configurations
# Each entry is treated as unique (same provider with different models allowed)
COMPARE_TARGETS = [
    {"provider": "openai", "model": "gpt-4.1-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    {"provider": "deepseek", "model": "deepseek-chat"},
    {"provider": "grok", "model": "grok-4-1-fast-non-reasoning"},
]


class ModelType(Enum):
    """Supported model types."""

    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROK = "grok"


class Config:
    """Configuration management for the application."""

    def __init__(self):
        """Initialize configuration with environment variables."""
        # Load environment variables from .env file if it exists
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        # API Configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

        # Model Configuration
        self.MODEL_TYPE = os.getenv("MODEL_TYPE", ModelType.OPENAI.value)
        self.DEFAULT_OPENAI_MODEL = os.getenv("DEFAULT_OPENAI_MODEL")
        self.DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL")
        self.DEFAULT_DEEPSEEK_MODEL = os.getenv("DEFAULT_DEEPSEEK_MODEL")

        if ModelType.OPENAI.value == self.MODEL_TYPE:
            self.DEFAULT_MODEL = self.DEFAULT_OPENAI_MODEL or os.getenv(
                "DEFAULT_MODEL", "gpt-4o-mini"
            )
        elif ModelType.GEMINI.value == self.MODEL_TYPE:
            self.DEFAULT_MODEL = self.DEFAULT_GEMINI_MODEL or os.getenv(
                "DEFAULT_MODEL", "gemini-2.5-flash-lite"
            )
        elif ModelType.DEEPSEEK.value == self.MODEL_TYPE:
            self.DEFAULT_MODEL = self.DEFAULT_DEEPSEEK_MODEL or os.getenv(
                "DEFAULT_MODEL", "deepseek-chat"
            )
        elif ModelType.GROK.value == self.MODEL_TYPE:
            self.DEFAULT_MODEL = os.getenv("DEFAULT_GROK_MODEL") or os.getenv(
                "DEFAULT_MODEL", "grok-4-1-fast-non-reasoning"
            )
        else:
            self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    def validate(self) -> bool:
        """
        Validate that all required configuration is present based on the selected model type.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        if ModelType.OPENAI.value == self.MODEL_TYPE:
            if not self.OPENAI_API_KEY:
                print("Error: OPENAI_API_KEY is not set. Please set it in the .env file.")
                return False
        elif ModelType.GEMINI.value == self.MODEL_TYPE:
            if not self.GOOGLE_GEMINI_API_KEY:
                print("Error: GOOGLE_GEMINI_API_KEY is not set. Please set it in the .env file.")
                return False
        elif ModelType.DEEPSEEK.value == self.MODEL_TYPE:
            if not self.DEEPSEEK_API_KEY:
                print("Error: DEEPSEEK_API_KEY is not set. Please set it in the .env file.")
                return False
        elif ModelType.GROK.value == self.MODEL_TYPE:
            if not os.getenv("GROK_API_KEY"):
                print("Error: GROK_API_KEY is not set. Please set it in the .env file.")
                return False
        else:
            print(
                f"Error: Unknown MODEL_TYPE '{self.MODEL_TYPE}'. Must be one of: {', '.join([e.value for e in ModelType])}"
            )
            return False

        return True

    def get_model_info(self) -> str:
        """
        Get information about the currently selected model.

        Returns:
            str: Formatted string with model information
        """
        if ModelType.OPENAI.value == self.MODEL_TYPE:
            return f"OpenAI ({self.DEFAULT_MODEL})"
        elif ModelType.GEMINI.value == self.MODEL_TYPE:
            return f"Google Gemini ({self.DEFAULT_MODEL})"
        elif ModelType.DEEPSEEK.value == self.MODEL_TYPE:
            return f"DeepSeek ({self.DEFAULT_MODEL})"
        return "Unknown"
