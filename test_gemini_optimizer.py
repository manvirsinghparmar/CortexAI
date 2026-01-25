"""
Quick Test - Gemini Provider

Test the prompt optimizer with Gemini provider.
"""

from utils.prompt_optimizer import PromptOptimizer
import json

print("=" * 80)
print("Testing Prompt Optimizer with Gemini")
print("=" * 80)

# Test with Gemini
print("\n[*] Initializing optimizer with Gemini provider...")
optimizer = PromptOptimizer(provider="gemini")
print(f"  Provider: {optimizer.provider}")
print(f"  Model: {optimizer.model}")

# Test optimization
print("\n[*] Testing prompt optimization...")
result = optimizer.optimize_prompt({
    "prompt": "write code for sorting",
    "settings": {"focus": "clarity"}
})

print("\n" + "=" * 80)
print("RESULT:")
print("=" * 80)
print(json.dumps(result, indent=2))

# Check if successful
if "error" not in result or result.get("error") is None:
    print("\n[SUCCESS] Gemini optimization working!")
    print(f"\nOriginal: write code for sorting")
    print(f"Optimized: {result['optimized_prompt']}")
    if "steps" in result:
        print(f"\nSteps taken: {len(result['steps'])}")
    if "explanations" in result:
        print(f"Explanations: {len(result['explanations'])}")
else:
    print("\n[WARNING] Error occurred:")
    print(f"Message: {result['error']['message']}")
    if "details" in result['error']:
        print(f"Details: {result['error']['details']}")
