import requests

BASE_URL = "http://localhost:8000/chat"
session_id = None

def chat(message):
    global session_id
    payload = {"user_input": message}
    if session_id:
        payload["session_id"] = session_id
    
    response = requests.post(BASE_URL, json=payload)
    result = response.json()
    
    if not session_id and "session_id" in result:
        session_id = result["session_id"]
    
    print(f"You: {message}")
    print(f"Bot: {result['console_output']}\n")
    return result

# Test flow
chat("I have a fever and cough")
chat("2 days ago")
chat("yes I was around sick people")
# Continue testing as needed