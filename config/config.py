import os
from dotenv import load_dotenv
from pathlib import Path
from enum import Enum

# Compare mode target configurations
# Each entry is treated as unique (same provider with different models allowed)
COMPARE_TARGETS = [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    {"provider": "gemini", "model": "gemini-2.0-flash-exp"},  # Second Gemini model for comparison
]

class ModelType(Enum):
    """Supported model types."""
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"

class Config:
    """Configuration management for the application."""
    
    def __init__(self):
        """Initialize configuration with environment variables."""
        # Load environment variables from .env file if it exists
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        
        # API Configuration
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.GOOGLE_GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
        self.DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

        # Model Configuration
        self.MODEL_TYPE = os.getenv('MODEL_TYPE', ModelType.OPENAI.value)
        self.DEFAULT_OPENAI_MODEL = os.getenv('DEFAULT_OPENAI_MODEL')
        self.DEFAULT_GEMINI_MODEL = os.getenv('DEFAULT_GEMINI_MODEL')
        self.DEFAULT_DEEPSEEK_MODEL = os.getenv('DEFAULT_DEEPSEEK_MODEL')

        if self.MODEL_TYPE == ModelType.OPENAI.value:
            self.DEFAULT_MODEL = self.DEFAULT_OPENAI_MODEL or os.getenv('DEFAULT_MODEL', 'gpt-3.5-turbo')
        elif self.MODEL_TYPE == ModelType.GEMINI.value:
            self.DEFAULT_MODEL = self.DEFAULT_GEMINI_MODEL or os.getenv('DEFAULT_MODEL', 'gemini-1.5-flash')
        elif self.MODEL_TYPE == ModelType.DEEPSEEK.value:
            self.DEFAULT_MODEL = self.DEFAULT_DEEPSEEK_MODEL or os.getenv('DEFAULT_MODEL', 'deepseek-chat')
        else:
            self.DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'gpt-3.5-turbo')
        
    def validate(self) -> bool:
        """
        Validate that all required configuration is present based on the selected model type.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        if self.MODEL_TYPE == ModelType.OPENAI.value:
            if not self.OPENAI_API_KEY:
                print("Error: OPENAI_API_KEY is not set. Please set it in the .env file.")
                return False
        elif self.MODEL_TYPE == ModelType.GEMINI.value:
            if not self.GOOGLE_GEMINI_API_KEY:
                print("Error: GOOGLE_GEMINI_API_KEY is not set. Please set it in the .env file.")
                return False
        elif self.MODEL_TYPE == ModelType.DEEPSEEK.value:
            if not self.DEEPSEEK_API_KEY:
                print("Error: DEEPSEEK_API_KEY is not set. Please set it in the .env file.")
                return False
        else:
            print(f"Error: Unknown MODEL_TYPE '{self.MODEL_TYPE}'. Must be one of: {', '.join([e.value for e in ModelType])}")
            return False
            
        return True
        
    def get_model_info(self) -> str:
        """
        Get information about the currently selected model.
        
        Returns:
            str: Formatted string with model information
        """
        if self.MODEL_TYPE == ModelType.OPENAI.value:
            return f"OpenAI ({self.DEFAULT_MODEL})"
        elif self.MODEL_TYPE == ModelType.GEMINI.value:
            return f"Google Gemini ({self.DEFAULT_MODEL})"
        elif self.MODEL_TYPE == ModelType.DEEPSEEK.value:
            return f"DeepSeek ({self.DEFAULT_MODEL})"
        return "Unknown"
