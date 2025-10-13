import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={"user_input": "I have a fever"}
)

print("Status:", response.status_code)
print("Response:", response.json())