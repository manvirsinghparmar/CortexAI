"""
Test prompt optimizer with sample: "what is wikipedia?"
"""

from utils.prompt_optimizer import PromptOptimizer
import json

print("=" * 80)
print("Testing Prompt Optimizer")
print("=" * 80)

# Initialize with Gemini (has free tier)
print("\n[*] Initializing optimizer with Gemini...")
optimizer = PromptOptimizer(provider="gemini")
print(f"  Provider: {optimizer.provider}")
print(f"  Model: {optimizer.model}")

# Test the sample prompt
print("\n[*] Optimizing prompt: 'what is wikipedia?'")
print("-" * 80)

result = optimizer.optimize_prompt({
    "prompt": "what is wikipedia?"
})

print("\n" + "=" * 80)
print("RESULT:")
print("=" * 80)
print(json.dumps(result, indent=2))

# Display results
print("\n" + "=" * 80)
if "error" not in result or result.get("error") is None:
    print("[SUCCESS] Optimization complete!")
    print("=" * 80)
    print(f"\nOriginal prompt:")
    print("  'what is wikipedia?'")
    print(f"\nOptimized prompt:")
    print(f"  '{result['optimized_prompt']}'")
    
    if "steps" in result:
        print(f"\nOptimization steps ({len(result['steps'])}):")
        for i, step in enumerate(result['steps'], 1):
            print(f"  {i}. {step}")
    
    if "explanations" in result:
        print(f"\nExplanations ({len(result['explanations'])}):")
        for i, exp in enumerate(result['explanations'], 1):
            print(f"  {i}. {exp}")
    
    if "metrics" in result:
        print(f"\nQuality metrics:")
        for key, value in result['metrics'].items():
            print(f"  {key}: {value}")
else:
    print("[ERROR] Optimization failed")
    print("=" * 80)
    print(f"\nError: {result['error']['message']}")
    if "details" in result['error']:
        print(f"Details: {result['error']['details']}")
    print("\nNote: Make sure you have a valid Gemini API key in .env")
    print("Get one free at: https://aistudio.google.com/app/apikey")
