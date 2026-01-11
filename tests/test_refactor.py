"""
Quick test to verify the refactored orchestrator works.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext

def test_orchestrator_initialization():
    """Test that orchestrator can be initialized."""
    print("Testing CortexOrchestrator initialization...")
    orchestrator = CortexOrchestrator()
    print("[OK] Orchestrator initialized successfully")
    return orchestrator

def test_user_context():
    """Test UserContext creation and manipulation."""
    print("\nTesting UserContext...")

    # Create a new context
    context = UserContext()
    print(f"[OK] Created UserContext with session_id: {context.session_id}")

    # Add messages
    context = context.add_message("user", "Hello")
    context = context.add_message("assistant", "Hi there!")
    print(f"[OK] Added messages, count: {context.get_message_count()}")

    # Test clear history
    context = context.clear_history(keep_system=True)
    print(f"[OK] Cleared history, count: {context.get_message_count()}")

    return context

def test_token_tracker_creation(orchestrator):
    """Test token tracker creation."""
    print("\nTesting TokenTracker creation...")
    tracker = orchestrator.create_token_tracker("openai")
    print("[OK] Created TokenTracker for openai")
    return tracker

def test_cost_calculator_creation(orchestrator):
    """Test cost calculator creation."""
    print("\nTesting CostCalculator creation...")
    calculator = orchestrator.create_cost_calculator("openai")
    print("[OK] Created CostCalculator for openai")
    return calculator

def main():
    """Run all tests."""
    print("=" * 60)
    print("CortexAI Refactoring Test Suite")
    print("=" * 60)

    try:
        # Test orchestrator initialization
        orchestrator = test_orchestrator_initialization()

        # Test UserContext
        context = test_user_context()

        # Test utility creation
        tracker = test_token_tracker_creation(orchestrator)
        calculator = test_cost_calculator_creation(orchestrator)

        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)
        print("\nRefactoring Summary:")
        print("  - CortexOrchestrator: Initialized successfully")
        print("  - UserContext: Working correctly")
        print("  - TokenTracker: Created successfully")
        print("  - CostCalculator: Created successfully")
        print("\nThe refactored codebase is ready for use!")

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"[FAILED] Test failed with error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)