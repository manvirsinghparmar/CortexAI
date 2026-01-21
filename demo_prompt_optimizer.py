"""
Prompt Optimizer Demo Script

Demonstrates the usage of the PromptOptimizer class with various examples.
Run this script to see how the optimizer works with different inputs.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from utils.prompt_optimizer import PromptOptimizer
from config.config import Config


def print_result(title: str, result: dict):
    """Pretty print optimization result."""
    print(f"\n{'=' * 80}")
    print(f"{title}")
    print('=' * 80)
    print(json.dumps(result, indent=2))
    print()


def main():
    """Run demo examples."""
    print("Prompt Optimizer Demo")
    print("=" * 80)
    
    # Initialize optimizer
    try:
        config = Config()
        if not config.OPENAI_API_KEY:
            print("ERROR: OPENAI_API_KEY not found in .env file")
            print("Please set your OpenAI API key in the .env file to run this demo.")
            return
        
        optimizer = PromptOptimizer()
        print(f"✓ Optimizer initialized with model: {optimizer.model}")
    except Exception as e:
        print(f"ERROR: Failed to initialize optimizer: {e}")
        return
    
    # Example 1: Basic optimization
    print("\n" + "=" * 80)
    print("Example 1: Basic Prompt Optimization")
    print("=" * 80)
    
    result1 = optimizer.optimize_prompt({
        "prompt": "write code for sorting"
    })
    print_result("Result 1: Basic Optimization", result1)
    
    # Example 2: Optimization with settings
    print("\n" + "=" * 80)
    print("Example 2: Optimization with Settings")
    print("=" * 80)
    
    result2 = optimizer.optimize_prompt({
        "prompt": "explain machine learning",
        "settings": {
            "focus": "clarity",
            "audience": "beginners",
            "format": "step-by-step"
        }
    })
    print_result("Result 2: With Settings", result2)
    
    # Example 3: Complex prompt
    print("\n" + "=" * 80)
    print("Example 3: Complex Prompt Optimization")
    print("=" * 80)
    
    result3 = optimizer.optimize_prompt({
        "prompt": "Create API endpoint",
        "settings": {
            "technology": "FastAPI",
            "requirements": ["authentication", "rate limiting", "error handling"]
        }
    })
    print_result("Result 3: Complex Prompt", result3)
    
    # Example 4: Error case - empty prompt
    print("\n" + "=" * 80)
    print("Example 4: Error Handling - Empty Prompt")
    print("=" * 80)
    
    result4 = optimizer.optimize_prompt({
        "prompt": "   "
    })
    print_result("Result 4: Empty Prompt Error", result4)
    
    # Example 5: Error case - missing prompt
    print("\n" + "=" * 80)
    print("Example 5: Error Handling - Missing Prompt")
    print("=" * 80)
    
    result5 = optimizer.optimize_prompt({
        "settings": {"focus": "clarity"}
    })
    print_result("Result 5: Missing Prompt Error", result5)
    
    # Summary
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("✓ Basic prompt optimization")
    print("✓ Optimization with custom settings")
    print("✓ Complex prompts with structured requirements")
    print("✓ Input validation and error handling")
    print("✓ Structured JSON output with explanations and metrics")
    print("\nCheck the results above to see:")
    print("- optimized_prompt: The improved version")
    print("- steps: What changes were made")
    print("- explanations: Why changes were made")
    print("- metrics: Quality scores (if available)")
    print("- error: Error details (for invalid inputs)")


if __name__ == "__main__":
    main()
