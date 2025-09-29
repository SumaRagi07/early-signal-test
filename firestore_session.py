import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import json
import re
from typing import List, Dict, Any

cred = credentials.Certificate("firebase_service_account.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def _extract_content_from_item(item: Any) -> Dict[str, str]:
    """Robust extractor for Gemini-style message artifacts"""
    try:
        # If it's already a dict
        if isinstance(item, dict):
            content = item.get('content', '')
        else:
            content = str(item)

        # Match Gemini-like pattern: parts=[Part(...text='...')] role='user'
        match = re.search(r"text='([^']+)'", content)
        if match:
            content_clean = match.group(1)
        else:
            # Try JSON fallback if it’s raw string
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "content" in parsed:
                    content_clean = parsed["content"]
                else:
                    content_clean = content
            except:
                content_clean = content

        # Guess role
        role = "user"
        if "role='model'" in content or '"role": "model"' in content:
            role = "model"
        elif "role='system'" in content or '"role": "system"' in content:
            role = "system"
        elif "role='error'" in content:
            role = "error"

        return {
            'role': role,
            'content': content_clean.strip()[:1000]
        }

    except Exception as e:
        return {
            'role': 'error',
            'content': f"Extraction error: {str(e)}"
        }
        
def get_session_history(session_id: str) -> dict:
    """Retrieve session document including history and state"""
    try:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists:
            # Return both history and state (add more fields as needed)
            doc_dict = doc.to_dict()
            return {
                "history": doc_dict.get("history", []),
                "state": doc_dict.get("state", {}),
                "last_clarifier_question": doc_dict.get("last_clarifier_question", None),
                "REPORT_COUNTER": doc_dict.get("REPORT_COUNTER", 0)
            }
        return {"history": [], "state": {}}
    except Exception as e:
        print(f"Firestore read error: {e}")
        return {"history": [], "state": {}}

def save_session_history(session_id: str, session_data: dict):
    """
    Save session data (history, state, etc.) with metadata and size limits.
    session_data should be a dict with at least "history" and "state".
    """
    try:
        # Clean and validate history
        history = session_data.get("history", [])
        clean_history = []
        for item in history:
            cleaned = _extract_content_from_item(item)
            if cleaned['content'].strip():
                clean_history.append(cleaned)
        
        # Size management
        MAX_ITEMS = 50
        if len(clean_history) > MAX_ITEMS:
            clean_history = clean_history[-MAX_ITEMS:]
        
        # Prepare data for save
        update_data = {
            'history': clean_history,
            'last_updated': datetime.now(timezone.utc),
            'history_count': len(clean_history),
            # Persist state and any other fields (clarifier, counter, etc)
            'state': session_data.get("state", {}),
            'last_clarifier_question': session_data.get("last_clarifier_question", None),
            'REPORT_COUNTER': session_data.get("REPORT_COUNTER", 0)
        }
        
        # Remove None fields (Firestore cannot store None, only omit)
        update_data = {k: v for k, v in update_data.items() if v is not None}

        # Batch write
        batch = db.batch()
        doc_ref = db.collection("sessions").document(session_id)
        batch.set(doc_ref, update_data, merge=True)
        batch.commit()
        
    except Exception as e:
        print(f"Critical save error: {e}")
        # Emergency save
        db.collection("session_errors").document().set({
            'session_id': session_id,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc)
        })