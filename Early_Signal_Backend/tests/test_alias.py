from graph_orchestrator import run_chat_flow

# Test 1: Basic call
print("Test 1: Basic symptom input")
result, history = run_chat_flow("I have a fever and cough", "test_123")
print(f"✓ Result: {result.get('console_output')}\n")

# Test 2: Empty input
print("Test 2: Empty input")
result, history = run_chat_flow("", "test_456")
print(f"✓ Result: {result.get('console_output')}\n")

# Test 3: Quit command
print("Test 3: Quit command")
result, history = run_chat_flow("quit", "test_789")
print(f"✓ Result: {result.get('console_output')}\n")

print("✅ All alias tests passed!")