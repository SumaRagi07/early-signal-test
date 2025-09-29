# agents/bq_submitter_agent.py
import json
from typing import List, Dict, Tuple
from google.cloud import bigquery
from config import bq_client, TABLE_ID

import warnings
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="google.cloud.bigquery._helpers",
    message="Unknown type 'GEOGRAPHY'"
)

AGENT_NAME = "bq_submitter_agent"
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, responsible for inserting de-identified public-health reports into BigQuery.
You will be handed a JSON report; your job is only to return a confirmation JSON.
"""

def insert_into_bigquery(client: bigquery.Client, table_id: str, rows: List[Dict]):
    table = client.get_table(table_id)
    errors = client.insert_rows(table, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    # 1) Parse the final report
    report = json.loads(user_msg)

    # 2) Build a BigQuery row matching table schema
    row = {
        "report_id":                report["report_id"],
        "user_id":                  report["user_id"],
        "report_timestamp":         report["report_timestamp"],

        "symptom_text":             report["symptom_text"],
        "illness_category":         report.get("illness_category"),

        "exposure_location_name":   report.get("exposure_location_name"),
        "exposure_latitude":        report.get("exposure_latitude"),
        "exposure_longitude":       report.get("exposure_longitude"),

        "current_location_name":    report.get("current_location_name"),
        "current_latitude":         report.get("current_latitude"),
        "current_longitude":        report.get("current_longitude"),

        "final_diagnosis":          report.get("final_diagnosis"),

        "days_since_exposure":      report.get("days_since_exposure"),
        "days_since_symptom_onset": report.get("days_since_symptom_onset"),

        "restaurant_visit":         report.get("restaurant_visit"),
        "outdoor_activity":         report.get("outdoor_activity"),
        "water_exposure":           report.get("water_exposure"),
        "location_category":        report.get("location_category"),
        "contagious_flag":          report.get("contagious_flag"),
        "alertable_flag":           report.get("alertable_flag"),
        "reasoning":                report.get("reasoning")
    }

    # 3) Construct GEOGRAPHY fields if possible
    lat, lon = row["exposure_latitude"], row["exposure_longitude"]
    if lat is not None and lon is not None:
        row["exposure_geopoint"] = f"POINT({lon} {lat})"
    else:
        row["exposure_geopoint"] = None

    lat2, lon2 = row["current_latitude"], row["current_longitude"]
    if lat2 is not None and lon2 is not None:
        row["current_geopoint"] = f"POINT({lon2} {lat2})"
    else:
        row["current_geopoint"] = None

    # 4) Insert into BigQuery
    client = bq_client or bigquery.Client()
    try:
        insert_into_bigquery(client, TABLE_ID, [row])
        status = {
            "status": "success",
            "rows_inserted": 1,
            "console_output": "✅ Report submitted successfully."
        }
    except Exception as e:
        status = {
            "status": "error",
            "message": str(e),
            "console_output": f"❌ BigQuery submission failed: {str(e)}"
        }

    # 5) Return a simple JSON confirmation
    return json.dumps(status), history