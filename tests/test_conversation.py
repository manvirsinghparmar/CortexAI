"""
Quick test script for ConversationManager and multi-turn support.

Tests:
1. ConversationManager basic functionality
2. Message format conversion
3. Auto-trimming
"""

import sys
from context.conversation_manager import ConversationManager


def test_conversation_manager():
    """Test ConversationManager functionality."""
    print("Testing ConversationManager...")

    # Test 1: Basic functionality
    print("\n1. Testing basic add/get messages:")
    conv = ConversationManager(max_messages=5)

    conv.add_user("Hello!")
    conv.add_assistant("Hi there! How can I help you?")
    conv.add_user("What's the weather?")
    conv.add_assistant("I don't have access to weather data.")

    messages = conv.get_messages()
    print(f"   Message count: {len(messages)} (expected: 4)")
    assert len(messages) == 4, "Should have 4 messages"

    print(f"   First message role: {messages[0]['role']} (expected: user)")
    assert messages[0]['role'] == 'user', "First message should be from user"

    print(f"   Second message role: {messages[1]['role']} (expected: assistant)")
    assert messages[1]['role'] == 'assistant', "Second message should be from assistant"

    print("   [PASS] Basic functionality works!")

    # Test 2: Auto-trimming
    print("\n2. Testing auto-trimming (max_messages=5):")
    conv.add_user("Tell me a joke")  # 5th message
    conv.add_assistant("Why did the chicken cross the road?")  # 6th message (should trigger trim)

    messages = conv.get_messages()
    print(f"   Message count after adding 6th message: {len(messages)} (expected: 5)")
    assert len(messages) == 5, "Should have trimmed to 5 messages"

    print(f"   First message content: '{messages[0]['content'][:30]}...'")
    print(f"   (Should NOT contain 'Hello!' anymore)")
    assert "Hello!" not in messages[0]['content'], "First message should have been trimmed"

    print("   [PASS] Auto-trimming works!")

    # Test 3: pop_last_user
    print("\n3. Testing pop_last_user:")
    initial_count = len(conv.get_messages())
    removed = conv.pop_last_user()

    print(f"   Removed message role: {removed['role']} (expected: user)")
    print(f"   Removed message content: '{removed['content']}'")
    assert removed['role'] == 'user', "Should have removed a user message"

    final_count = len(conv.get_messages())
    print(f"   Message count after pop: {final_count} (expected: {initial_count - 1})")
    assert final_count == initial_count - 1, "Should have one fewer message"

    print("   [PASS] pop_last_user works!")

    # Test 4: reset
    print("\n4. Testing reset:")
    conv.reset()
    messages = conv.get_messages()
    print(f"   Message count after reset: {len(messages)} (expected: 0)")
    assert len(messages) == 0, "Should have no messages after reset"

    print("   [PASS] reset works!")

    # Test 5: System prompt preservation
    print("\n5. Testing system prompt preservation:")
    conv_with_system = ConversationManager(max_messages=5, system_prompt="You are a helpful assistant.")

    messages = conv_with_system.get_messages()
    print(f"   Message count with system prompt: {len(messages)} (expected: 1)")
    assert len(messages) == 1, "Should have 1 system message"

    print(f"   System message role: {messages[0]['role']} (expected: system)")
    assert messages[0]['role'] == 'system', "First message should be system"

    conv_with_system.add_user("Test")
    conv_with_system.add_assistant("Response")

    print(f"   Message count after adding user/assistant: {conv_with_system.get_message_count()} (expected: 3)")
    assert conv_with_system.get_message_count() == 3, "Should have 3 messages total"

    conv_with_system.reset(keep_system_prompt=True)
    messages = conv_with_system.get_messages()
    print(f"   Message count after reset (keep_system_prompt=True): {len(messages)} (expected: 1)")
    assert len(messages) == 1, "Should still have system message"
    assert messages[0]['role'] == 'system', "Should still have system message"

    print("   [PASS] System prompt preservation works!")

    print("\n" + "="*50)
    print("[PASS] All ConversationManager tests passed!")
    print("="*50)


def test_message_format():
    """Test that messages are in the correct format."""
    print("\n\nTesting message format...")

    conv = ConversationManager()
    conv.add_user("Test message")
    conv.add_assistant("Test response")

    messages = conv.get_messages()

    print("\n1. Checking message structure:")
    for i, msg in enumerate(messages):
        print(f"   Message {i+1}: {msg}")
        assert 'role' in msg, "Message should have 'role' field"
        assert 'content' in msg, "Message should have 'content' field"
        assert msg['role'] in ['user', 'assistant', 'system'], "Role should be valid"
        assert isinstance(msg['content'], str), "Content should be string"

    print("   [PASS] Message format is correct!")

    print("\n" + "="*50)
    print("[PASS] All message format tests passed!")
    print("="*50)


def test_conversation_summary():
    """Test conversation summary."""
    print("\n\nTesting conversation summary...")

    conv = ConversationManager(max_messages=20)

    # Add some messages
    for i in range(5):
        conv.add_user(f"User message {i+1}")
        conv.add_assistant(f"Assistant response {i+1}")

    summary = conv.get_conversation_summary(last_n=10)
    print(f"\n{summary}")

    assert "10 of 10" in summary or "10 messages" in summary, "Summary should show message count"

    print("\n   [PASS] Conversation summary works!")

    print("\n" + "="*50)
    print("[PASS] All conversation summary tests passed!")
    print("="*50)


if __name__ == "__main__":
    try:
        test_conversation_manager()
        test_message_format()
        test_conversation_summary()

        print("\n" + "="*70)
        print("[SUCCESS] ALL TESTS PASSED! Multi-turn conversation support is working!")
        print("="*70)
        sys.exit(0)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
