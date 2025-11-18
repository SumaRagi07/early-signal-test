from firestore_session import save_session_history, get_session_history

test_session = "test_firestore_debug"
test_history = [
    {"role": "user", "content": "I have a fever"},
    {"role": "agent", "content": "How long have you had it?"}
]

save_session_history(test_session, test_history)

restored = get_session_history(test_session)
print("🔥 Loaded from Firestore:", restored)