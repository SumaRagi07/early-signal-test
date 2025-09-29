from fastapi import FastAPI, Request
from pydantic import BaseModel
from orchestrator import run_chat_flow

app = FastAPI()

class ChatRequest(BaseModel):
    user_input: str

@app.post("/chat")
async def chat(request: ChatRequest):
    print(f"\n🛬 Received input from API: {request.user_input}")
    try:
        result, _ = run_chat_flow(user_input=request.user_input)
        print(f"\n🧠 Result from orchestrator: {result}")
        return result or {"error": "No response generated"}
    except Exception as e:
        print(f"❌ Exception in orchestrator: {e}")
        return {"error": str(e)}