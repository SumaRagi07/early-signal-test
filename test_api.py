import requests

url = "http://localhost:8000/chat"
payload = {
    "user_input": "I have a sore throat and fever",
    "session_id": "test-session-123"
}
response = requests.post(url, json=payload)
print(response.json())