# agents/pinecone_agent.py

import json
from helpers import strip_fences
from config import index as pinecone_index  # Rename to avoid conflicts
from config import embedder
from config import bq_client

AGENT_NAME = "pinecone_agent"
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}.
- Receive JSON {{ "symptoms": [ ... ]}} as input.
- Generate an embedding & query Pinecone index for top-3 matches.
- Return JSON: {{ "matches": [{{ "id":..., "score":..., "definition":... }}, ...] }}
"""

def run_agent(user_msg: str, history: list):
    try:
        data = json.loads(user_msg)
        syms = data.get("symptoms", [])
    except json.JSONDecodeError:
        syms = []
    symptom_text = ", ".join(syms)

    embedding = embedder.encode(symptom_text, normalize_embeddings=True).tolist()
    matches = pinecone_index.query(vector=embedding, top_k=3, include_metadata=True).matches

    out = [{
        "id": m.id,
        "score": m.score,
        "definition": m.metadata.get("definition", "")
    } for m in matches]

    return json.dumps({"matches": out}), history
