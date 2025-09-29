from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import run_chat_flow
import json
import uuid

app = FastAPI()

class ChatInput(BaseModel):
    user_input: str
    session_id: str | None = None  # Optional, generate if missing

@app.post("/chat")
async def chat_endpoint(input_data: ChatInput):
    print(f"\n📥 Received input: {input_data.user_input}")
    session_id = input_data.session_id or str(uuid.uuid4())
    print(f"📌 Using session ID: {session_id}")

    result, _ = run_chat_flow(user_input=input_data.user_input, session_id=session_id)

    if result:
        print("📤 Full result object:", json.dumps(result, indent=2))
        result["session_id"] = session_id  # Echo session_id for frontend
        return result
    else:
        print("⚠️ No result returned from orchestrator.")
        raise HTTPException(status_code=500, detail="No response generated")