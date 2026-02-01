"""
Quick Usage Example for Prompt Optimizer

This is a minimal example showing how to use the PromptOptimizer class.
"""

from utils.prompt_optimizer import PromptOptimizer
import json

# Initialize the optimizer
optimizer = PromptOptimizer()

# Example 1: Basic optimization
print("Example 1: Basic Optimization")
print("-" * 50)
result = optimizer.optimize_prompt({
    "prompt": "write code for sorting"
})
print(json.dumps(result, indent=2))

# Example 2: With settings
print("\n\nExample 2: With Settings")
print("-" * 50)
result = optimizer.optimize_prompt({
    "prompt": "explain machine learning",
    "settings": {
        "focus": "clarity",
        "audience": "beginners"
    }
})
print(json.dumps(result, indent=2))

# Example 3: Error handling
print("\n\nExample 3: Error Handling")
print("-" * 50)
result = optimizer.optimize_prompt({
    "prompt": ""  # Empty prompt
})
print(json.dumps(result, indent=2))
