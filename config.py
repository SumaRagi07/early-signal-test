# config.py

import os
from google.oauth2 import service_account
from google.cloud import bigquery
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# Ensure GOOGLE_APPLICATION_CREDENTIALS is set
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__),
    "adsp_service_account_key.json"
)

# Paths & constants
ROOT = os.path.dirname(__file__)
SA_KEY_PATH = os.path.join(ROOT, "adsp_service_account_key.json")

PROJECT_ID = "adsp-34002-ip07-early-signal"
TABLE_ID = "adsp-34002-ip07-early-signal.illness_tracker.illness_reports_llm"
PINECONE_API_KEY = "pcsk_5f4qYH_TCTYwiQVwGkgkf96UvF7jZcSyFrnCFCaAqCAeqMVwdAcwRvPbsmPqkNFpLK54vK"
PINECONE_INDEX_NAME = "earlysignal"
LOCATION = "us-central1"
MODEL = "gemini-2.0-flash"

# Load service account credentials
credentials = service_account.Credentials.from_service_account_file(SA_KEY_PATH)

# Initialize BigQuery client at import time
bq_client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

# Initialize Pinecone and embedder
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)
embedder = SentenceTransformer("intfloat/e5-large-v2")

def validate_config():
    """Validate configuration settings and external connections."""
    results = {
        "google_auth": False,
        "bigquery":    False,
        "pinecone":    False,
        "embeddings":  False,
    }

    print("\n" + "="*40)
    print("CONFIGURATION VALIDATION REPORT")
    print("="*40)

    # 1) Google Auth
    try:
        _ = credentials  # Already loaded above
        print(f"✅ Google Auth: Service account loaded from {SA_KEY_PATH}")
        results["google_auth"] = True
    except Exception as e:
        print(f"❌ Google Auth Failed: {e}")

    # 2) BigQuery
    try:
        bq_client.get_table(TABLE_ID)
        print(f"✅ BigQuery: Connected to {TABLE_ID}")
        results["bigquery"] = True
    except Exception as e:
        print(f"❌ BigQuery Connection Failed: {e}")

    # 3) Pinecone
    try:
        idxs = pc.list_indexes().names()
        if PINECONE_INDEX_NAME in idxs:
            print(f"✅ Pinecone: Index '{PINECONE_INDEX_NAME}' available")
            results["pinecone"] = True
        else:
            print(f"❌ Pinecone: Index '{PINECONE_INDEX_NAME}' not found")
    except Exception as e:
        print(f"❌ Pinecone Connection Failed: {e}")

    # 4) Embeddings
    try:
        test_emb = embedder.encode("test")
        print(f"✅ Embeddings: Model loaded, test embedding shape: {test_emb.shape}")
        results["embeddings"] = True
    except Exception as e:
        print(f"❌ Embeddings Failed: {e}")

    return results

if __name__ == "__main__":
    summary = validate_config()
    print("\n" + "="*40)
    print("FINAL VALIDATION SUMMARY")
    print("="*40)
    for service, ok in summary.items():
        print(f"{service.upper():<12}: {'✅' if ok else '❌'}")

# Explicit exports
__all__ = [
    "PROJECT_ID", "TABLE_ID", "LOCATION", "MODEL",
    "PINECONE_API_KEY", "PINECONE_INDEX_NAME",
    "credentials", "bq_client",
    "pc", "index", "embedder",
    "validate_config"
]