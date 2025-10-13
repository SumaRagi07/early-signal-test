from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph_orchestrator import run_chat_flow
import json
import uuid

app = FastAPI()

# ✅ CORS setup for Flutter Web
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",  # any localhost port
    allow_credentials=True,
    allow_methods=["*"],  # allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],  # allows all headers
)

# ✅ Chat input model
class ChatInput(BaseModel):
    user_input: str
    session_id: str | None = None  # Optional, generate if missing

# ✅ Chat endpoint
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

# ✅ Optional health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend running fine"}