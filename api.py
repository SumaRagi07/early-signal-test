# api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph_orchestrator import run_chat_flow
import json
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ UPDATED: Add user_id field
class ChatInput(BaseModel):
    user_input: str
    session_id: str | None = None
    user_id: str | None = None          # NEW
    current_latitude: float | None = None
    current_longitude: float | None = None

@app.post("/chat")
async def chat_endpoint(input_data: ChatInput):
    print(f"\n📥 Received input: {input_data.user_input}")
    session_id = input_data.session_id or str(uuid.uuid4())
    print(f"📌 Using session ID: {session_id}")
    
    # NEW: Log user ID (only in backend console, not sent to user)
    if input_data.user_id:
        print(f"👤 [Backend] User ID: {input_data.user_id}")
    else:
        print(f"👤 [Backend] No user_id provided, will use fallback")
    
    if input_data.current_latitude is not None and input_data.current_longitude is not None:
        print(f"📍 Location provided: ({input_data.current_latitude}, {input_data.current_longitude})")

    # Pass everything to orchestrator
    result, _ = run_chat_flow(
        user_input=input_data.user_input, 
        session_id=session_id,
        user_id=input_data.user_id,
        current_latitude=input_data.current_latitude,
        current_longitude=input_data.current_longitude
    )

    if result:
        print("📤 Full result object:", json.dumps(result, indent=2))
        result["session_id"] = session_id
        return result
    else:
        print("⚠️ No result returned from orchestrator.")
        raise HTTPException(status_code=500, detail="No response generated")
    
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend running fine"}