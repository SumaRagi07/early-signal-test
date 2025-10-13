# agents/cluster_detection_agent.py

import json
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from google.cloud import bigquery
from config import bq_client, CLUSTERS_SPATIAL_VIEW, ALERT_TRACTS_VIEW

AGENT_NAME = 'cluster_detection_agent'

def query_spatial_clusters(disease: str, tract_id: str, days_back: int = 14) -> Dict:
    """
    Query clusters by census tract.
    Uses most_recent_case to determine if cluster is active.
    """
    query = f"""
    WITH cluster_stats AS (
      SELECT 
        COUNT(*) as cluster_size,
        STRING_AGG(DISTINCT symptom_text, '; ' ORDER BY symptom_text) as common_symptoms,
        MIN(report_timestamp) as cluster_start,
        MAX(report_timestamp) as most_recent_case,
        AVG(days_since_symptom_onset) as avg_days_since_onset,
        STRING_AGG(DISTINCT exposure_location_name, ', ' 
                   ORDER BY exposure_location_name LIMIT 3) as exposure_locations,
        COUNTIF(cluster_spatial_id IS NOT NULL) as dbscan_clustered_count
      FROM `{CLUSTERS_SPATIAL_VIEW}`
      WHERE 
        tract_id = @tract_id
        AND disease = @disease
    )
    SELECT 
      *,
      TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), most_recent_case, DAY) as days_since_recent_case
    FROM cluster_stats
    WHERE 
      cluster_size >= 3
      AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), most_recent_case, DAY) <= @days_back
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("tract_id", "STRING", tract_id),
            bigquery.ScalarQueryParameter("disease", "STRING", disease),
            bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            return {}
        
        row = results[0]
        
        cluster_start = row.cluster_start
        most_recent_case = row.most_recent_case
        days_active = (most_recent_case - cluster_start).days
        
        return {
            "cluster_spatial_id": None,
            "cluster_type": "tract_based",
            "cluster_size": row.cluster_size,
            "common_symptoms": row.common_symptoms,
            "cluster_start": cluster_start.isoformat(),
            "most_recent_case": most_recent_case.isoformat(),
            "days_active": days_active,
            "days_since_recent_case": row.days_since_recent_case,
            "avg_days_since_onset": float(row.avg_days_since_onset) if row.avg_days_since_onset else None,
            "exposure_locations": row.exposure_locations,
            "dbscan_clustered_count": row.dbscan_clustered_count
        }
        
    except Exception as e:
        print(f"❌ Error querying spatial clusters: {e}")
        import traceback
        traceback.print_exc()
        return {} 

def query_tract_alerts(disease: str, tract_id: str) -> Dict:
    """
    Query alert_tracts_view for statistical anomaly flags in user's census tract.
    
    Args:
        disease: Diagnosed disease name
        tract_id: Census tract ID
    
    Returns:
        Dict with alert flags or empty dict if no alerts
    """
    query = f"""
    SELECT 
      disease,
      report_date,
      daily_count,
      avg_7d,
      stddev_7d,
      week_over_week_pct_change,
      wo_week_spike_flag,
      outlier_flag
    FROM `{ALERT_TRACTS_VIEW}`
    WHERE 
      tract_id = @tract_id
      AND disease = @disease
      AND report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    ORDER BY report_date DESC
    LIMIT 7  -- Past week of data
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("tract_id", "STRING", tract_id),
            bigquery.ScalarQueryParameter("disease", "STRING", disease),
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            return {}
        
        # Get most recent day's data
        latest = results[0]
        
        # Check if any day in past week had alerts
        has_spike = any(row.wo_week_spike_flag for row in results if row.wo_week_spike_flag is not None)
        has_outlier = any(row.outlier_flag for row in results if row.outlier_flag is not None)
        
        return {
            "disease": latest.disease,
            "report_date": latest.report_date.isoformat(),
            "daily_count": latest.daily_count,
            "avg_7d": float(latest.avg_7d) if latest.avg_7d else None,
            "stddev_7d": float(latest.stddev_7d) if latest.stddev_7d else None,
            "week_over_week_pct_change": float(latest.week_over_week_pct_change) if latest.week_over_week_pct_change else None,
            "wo_week_spike_flag": has_spike,  # TRUE if ANY day this week spiked
            "outlier_flag": has_outlier,       # TRUE if ANY day this week was outlier
            "alert_active": has_spike or has_outlier
        }
        
    except Exception as e:
        print(f"❌ Error querying tract alerts: {e}")
        return {}


def adjust_confidence_for_cluster(base_confidence: float, cluster_data: Dict, alert_data: Dict) -> float:
    """
    Boost diagnosis confidence based on cluster strength, capped at 0.99
    
    Args:
        base_confidence: Original LLM diagnosis confidence (0.0-1.0)
        cluster_data: Results from query_spatial_clusters()
        alert_data: Results from query_tract_alerts()
    
    Returns:
        Adjusted confidence score (capped at 0.99)
    """
    if not cluster_data:
        return base_confidence
    
    cluster_size = cluster_data.get("cluster_size", 0)
    has_spike_flag = alert_data.get("wo_week_spike_flag", False)
    has_outlier_flag = alert_data.get("outlier_flag", False)
    
    # Base confidence boost by cluster size
    if cluster_size >= 10:
        boost = 0.25
    elif cluster_size >= 6:
        boost = 0.15
    elif cluster_size >= 3:
        boost = 0.10
    else:
        boost = 0.0
    
    # Additional boost for statistical alerts
    if has_spike_flag:
        boost += 0.05
    if has_outlier_flag:
        boost += 0.05
    
    # Apply boost with cap at 0.99
    adjusted = min(base_confidence + boost, 0.99)
    
    return adjusted


def format_cluster_message(cluster_data: Dict, alert_data: Dict) -> str:
    """
    Generate user-facing message about detected cluster.
    
    Returns:
        Human-readable cluster alert message (or empty string if no cluster)
    """
    if not cluster_data:
        return ""
    
    cluster_size = cluster_data.get("cluster_size", 0)
    days_active = cluster_data.get("days_active", 0)
    disease = alert_data.get("disease", "this illness")
    
    # Determine alert severity
    has_alerts = alert_data.get("alert_active", False)
    
    if cluster_size >= 10 and has_alerts:
        severity = "🚨 OUTBREAK ALERT"
        action = "Public health officials are investigating. Please avoid public gatherings and contact your healthcare provider."
    elif cluster_size >= 6 or has_alerts:
        severity = "⚠️ ALERT"
        action = "Public health has been notified of elevated activity in this region."
    else:
        severity = "ℹ️ Note"
        action = "This increases the likelihood of this diagnosis."
    
    message = (
        f"{severity}: We've detected {cluster_size} cases of {disease} "
        f"in your area in the past {days_active} days. {action}"
    )
    
    return message


def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Main entry point for cluster detection agent.
    
    Input format (JSON):
    {
        "disease": "Norovirus",
        "tract_id": "17031320400",
        "base_confidence": 0.65
    }
    
    Output format (JSON):
    {
        "cluster_detected": true/false,
        "cluster_data": {...},
        "alert_data": {...},
        "adjusted_confidence": 0.85,
        "console_output": "⚠️ ALERT: We've detected 8 cases..."
    }
    """
    try:
        data = json.loads(user_msg)
    except Exception as e:
        return json.dumps({
            "error": f"Invalid input JSON: {e}",
            "cluster_detected": False
        }), history
    
    disease = data.get("disease")
    tract_id = data.get("tract_id")
    base_confidence = data.get("base_confidence", 0.5)
    days_back = data.get("days_back", 90)
    
    if not disease or not tract_id:
        return json.dumps({
            "error": "Missing required fields: disease and tract_id",
            "cluster_detected": False
        }), history
    
    print(f"🔍 Searching for {disease} clusters in tract {tract_id}...")
    
    # Query both data sources
    cluster_data = query_spatial_clusters(disease, tract_id, days_back)
    alert_data = query_tract_alerts(disease, tract_id)
    
    # Check if cluster detected
    cluster_detected = bool(cluster_data)
    
    if cluster_detected:
        print(f"✅ Cluster found: {cluster_data['cluster_size']} cases")
        if alert_data.get("alert_active"):
            print(f"⚠️  Statistical alert active in this tract")
    else:
        print(f"ℹ️  No clusters detected")
    
    # Adjust confidence and generate message
    adjusted_confidence = adjust_confidence_for_cluster(
        base_confidence, cluster_data, alert_data
    )
    
    console_output = format_cluster_message(cluster_data, alert_data)
    
    result = {
        "cluster_detected": cluster_detected,
        "cluster_data": cluster_data,
        "alert_data": alert_data,
        "base_confidence": base_confidence,
        "adjusted_confidence": adjusted_confidence,
        "confidence_boost": adjusted_confidence - base_confidence,
        "console_output": console_output
    }
    
    return json.dumps(result, indent=2), history