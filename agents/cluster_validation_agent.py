# agents/cluster_validation_agent.py

import json
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from google.cloud import bigquery
from config import bq_client, PROJECT_ID

AGENT_NAME = 'cluster_validation_agent'

# Reference to the new alert clusters view
CLUSTERS_ALERT_VIEW = f"{PROJECT_ID}.alerts.test_clusters_alert_view"
TRACTS_TABLE = f"{PROJECT_ID}.tracts.all_tracts"

def geopoint_to_tract_id(latitude: float, longitude: float) -> str:
    """
    Convert a lat/lon coordinate to its census tract ID.
    Uses spatial join with tracts.all_tracts table.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        Full GEOID tract identifier (11 digits) or None if not found
    """
    query = f"""
    SELECT 
        CONCAT(state_fips_code, county_fips_code, tract_ce) as full_tract_id
    FROM `{TRACTS_TABLE}`
    WHERE ST_WITHIN(
        ST_GEOGPOINT(@longitude, @latitude),
        tract_geom
    )
    LIMIT 1
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("latitude", "FLOAT64", latitude),
            bigquery.ScalarQueryParameter("longitude", "FLOAT64", longitude),
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if results:
            return results[0].full_tract_id
        else:
            print(f"âš ï¸  No tract found for coordinates ({latitude}, {longitude})")
            return None
            
    except Exception as e:
        print(f"âŒ Error converting geopoint to tract: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_adjacent_tracts(user_tract_id: str) -> List[str]:
    """
    Get all census tracts adjacent to or near the user's tract.
    
    Returns tracts that either:
    1. Share a boundary with user's tract (ST_INTERSECTS)
    2. Are within 500 meters of user's tract (ST_DISTANCE)
    
    Args:
        user_tract_id: Full 11-digit GEOID of user's tract
    
    Returns:
        List of adjacent tract IDs (includes the original tract)
    """
    query = f"""
    WITH user_tract AS (
      SELECT tract_geom 
      FROM `{TRACTS_TABLE}`
      WHERE CONCAT(state_fips_code, county_fips_code, tract_ce) = @user_tract_id
    )
    SELECT CONCAT(a.state_fips_code, a.county_fips_code, a.tract_ce) as tract_id
    FROM `{TRACTS_TABLE}` a, user_tract u
    WHERE 
      -- Include tracts that share a boundary
      ST_INTERSECTS(a.tract_geom, u.tract_geom)
      -- OR are within 500 meters (catches near-misses from geocoding)
      OR ST_DISTANCE(a.tract_geom, u.tract_geom) < 500
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_tract_id", "STRING", user_tract_id),
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        adjacent_tracts = [row.tract_id for row in results]
        print(f"   ðŸ—ºï¸  Found {len(adjacent_tracts)} adjacent/nearby tracts")
        
        return adjacent_tracts
        
    except Exception as e:
        print(f"âŒ Error getting adjacent tracts: {e}")
        # Fallback: return just the original tract
        return [user_tract_id]

def query_matching_cluster(
    exposure_lat: float,
    exposure_lon: float,
    days_since_exposure: int,
    user_disease: str,
    illness_category: str = None
) -> Dict:
    """
    Query clusters_alert_view to find active alert clusters matching user's exposure.
    
    UPDATED: Now uses adjacent tract matching for better geocoding tolerance.
    FIXED: Improved temporal logic to handle exposure before/during/after cluster activity.
    
    Matching criteria:
    1. Spatial: User's exposure tract OR adjacent tracts are in cluster's distinct_tract_ids
    2. Temporal: User's exposure timing overlaps with cluster activity window (EXPANDED)
    3. Alert threshold: clusters with alert_flag = TRUE or FALSE
    
    Args:
        exposure_lat: User's exposure location latitude
        exposure_lon: User's exposure location longitude
        days_since_exposure: How many days ago exposure occurred
        user_disease: User's diagnosed disease from diagnostic agent
        illness_category: Optional category filter (foodborne, airborne, etc.)
    
    Returns:
        Dict with cluster data or empty dict if no match
    """
    # Step 1: Convert user's exposure location to tract_id
    user_tract_id = geopoint_to_tract_id(exposure_lat, exposure_lon)
    
    if not user_tract_id:
        return {}
    
    print(f"   ðŸ“ User tract: {user_tract_id}")
    
    # Step 2: Get adjacent tracts for fuzzy matching
    adjacent_tracts = get_adjacent_tracts(user_tract_id)
    
    if not adjacent_tracts:
        print(f"   âš ï¸  Could not determine adjacent tracts, using exact match only")
        adjacent_tracts = [user_tract_id]
    
    # Step 3: Calculate user's exposure date
    user_exposure_date = datetime.now() - timedelta(days=days_since_exposure)
    
    # CRITICAL DEBUG: Print temporal calculations
    print(f"   ðŸ• User exposure date: {user_exposure_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ðŸ• Days since exposure: {days_since_exposure}")
    print(f"   ðŸ• Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 4: Build dynamic WHERE clause for tract matching
    # Check if ANY of the user's adjacent tracts appear in the cluster's tract list
    tract_conditions = []
    for i, tract in enumerate(adjacent_tracts):
        tract_conditions.append(f"CONTAINS_SUBSTR(distinct_tract_ids, @tract_{i})")
    
    tract_where_clause = " OR ".join(tract_conditions)
    
    # Step 5: Query for matching alert clusters
    # FIXED TEMPORAL LOGIC: Much more permissive to catch active clusters
    query = f"""
    SELECT 
    exposure_cluster_id,
    cluster_spatial_id,
    temporal_group,
    sample_exposure_tag,
    cluster_size,
    first_report_ts,
    last_report_ts,
    span_hours,
    distinct_tract_ids,
    distinct_tract_count,
    predominant_disease,
    predominant_disease_count,
    disease_count,
    consensus_ratio,
    predominant_category,
    size_flag,
    consensus_flag,
    alert_flag,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_report_ts, DAY) as days_since_last_report,
    TIMESTAMP_DIFF(@user_exposure_date, first_report_ts, DAY) as days_exposure_vs_first_report,
    TIMESTAMP_DIFF(@user_exposure_date, last_report_ts, DAY) as days_exposure_vs_last_report
    FROM `{CLUSTERS_ALERT_VIEW}`
    WHERE 
    -- Only sizeable alert clusters
    size_flag = TRUE
    
    -- Only clusters with meaningful consensus
    AND consensus_ratio >= 0.30

    -- Spatial match: user's tract OR adjacent tracts are in the cluster
    AND ({tract_where_clause})
    
    -- FIXED TEMPORAL LOGIC: Much broader window to catch all relevant cases
    -- Cluster must be "recent" (last activity within 30 days)
    AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_report_ts, DAY) <= 30
    
    -- User's exposure must be temporally relevant to the cluster
    AND (
        -- CASE 1: User exposed DURING cluster activity window (with generous padding)
        -- If cluster spans Oct 20-25, catch exposures from Oct 18-28
        TIMESTAMP(@user_exposure_date) BETWEEN 
        TIMESTAMP_SUB(first_report_ts, INTERVAL 3 DAY) AND 
        TIMESTAMP_ADD(last_report_ts, INTERVAL 3 DAY)
        
        -- CASE 2: User exposed BEFORE cluster started (incubation period)
        -- If exposure was Oct 15 and cluster started Oct 20, that's 5 days - within incubation
        -- Allow up to 14 days before first report (covers most incubation periods)
        OR (
            TIMESTAMP(@user_exposure_date) < first_report_ts
            AND TIMESTAMP_DIFF(first_report_ts, TIMESTAMP(@user_exposure_date), DAY) <= 14
        )
        
        -- CASE 3: User exposed SHORTLY AFTER cluster peak (recent exposure at still-active site)
        -- If cluster ended Oct 25 and exposure was Oct 27, still relevant
        OR (
            TIMESTAMP(@user_exposure_date) > last_report_ts
            AND TIMESTAMP_DIFF(TIMESTAMP(@user_exposure_date), last_report_ts, DAY) <= 5
        )
    )
    ORDER BY 
    -- Prioritize category match
    CASE WHEN predominant_category = @user_illness_category THEN 1 ELSE 2 END,
    consensus_ratio DESC,
    cluster_size DESC,
    last_report_ts DESC
    LIMIT 1
    """
    
    # Build query parameters dynamically for each adjacent tract
    query_parameters = [
        bigquery.ScalarQueryParameter("user_exposure_date", "TIMESTAMP", user_exposure_date),
        bigquery.ScalarQueryParameter("user_illness_category", "STRING", illness_category or "other"),
    ]
    
    for i, tract in enumerate(adjacent_tracts):
        query_parameters.append(
            bigquery.ScalarQueryParameter(f"tract_{i}", "STRING", tract)
        )
    
    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            print(f"   â„¹ï¸  No matching alert clusters found in {len(adjacent_tracts)} tract(s)")
            # DEBUG: Print why no match
            print(f"   â„¹ï¸  Searched for clusters with:")
            print(f"      - Spatial: {len(adjacent_tracts)} tracts")
            print(f"      - Temporal: exposure date {user_exposure_date.strftime('%Y-%m-%d')}")
            print(f"      - Within 30 days of now")
            return {}
        
        row = results[0]
        
        # DEBUG: Print match details
        print(f"   âœ… Matched via adjacent tract expansion")
        print(f"   âœ… Cluster temporal match:")
        print(f"      - First report: {row.first_report_ts.strftime('%Y-%m-%d %H:%M')}")
        print(f"      - Last report:  {row.last_report_ts.strftime('%Y-%m-%d %H:%M')}")
        print(f"      - User exposure: {user_exposure_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"      - Days exposure vs first: {row.days_exposure_vs_first_report}")
        print(f"      - Days exposure vs last:  {row.days_exposure_vs_last_report}")
        
        # FIXED: Use .get() for optional fields with safe defaults
        return {
            "exposure_cluster_id": row.exposure_cluster_id,
            "cluster_spatial_id": row.cluster_spatial_id,
            "temporal_group": row.temporal_group,
            "sample_exposure_tag": row.sample_exposure_tag,
            "cluster_size": row.cluster_size,
            "first_report_ts": row.first_report_ts.isoformat(),
            "last_report_ts": row.last_report_ts.isoformat(),
            "span_hours": row.span_hours,
            "distinct_tract_ids": row.distinct_tract_ids,
            "distinct_tract_count": row.distinct_tract_count,
            "predominant_disease": row.predominant_disease,
            "predominant_disease_count": row.predominant_disease_count,
            "disease_count": row.disease_count,
            "consensus_ratio": float(row.consensus_ratio),
            "predominant_category": getattr(row, "predominant_category", None) or "other",  # FIXED
            "size_flag": row.size_flag,
            "consensus_flag": row.consensus_flag,
            "alert_flag": row.alert_flag,
            "days_since_last_report": row.days_since_last_report
        }
        
    except Exception as e:
        print(f"âŒ Error querying cluster alerts: {e}")
        import traceback
        traceback.print_exc()
        return {}

def validate_diagnosis(
    user_disease: str,
    user_confidence: float,
    user_illness_category: str,
    cluster_data: Dict
) -> Dict:
    """
    Compare user's diagnosis against cluster's predominant_disease.
    
    FIXED: Added safe handling for missing predominant_category field.
    
    Returns validation result with refined confidence and messaging.
    
    Args:
        user_disease: Disease diagnosed by diagnostic agent
        user_confidence: Original confidence from diagnostic agent
        user_illness_category: User's diagnosis illness category
        cluster_data: Cluster data from query_matching_cluster()
    
    Returns:
        Dict with validation_result, refined_confidence, and reasoning
    """
    if not cluster_data:
        return {
            "validation_result": "NO_MATCH",
            "refined_confidence": user_confidence,
            "refined_diagnosis": user_disease,
            "reasoning": "No active outbreak clusters match your exposure location and timing."
        }
    
    predominant = cluster_data["predominant_disease"]
    consensus = cluster_data["consensus_ratio"]
    cluster_size = cluster_data["cluster_size"]
    
    # FIXED: Safe access to predominant_category with default
    cluster_category = cluster_data.get("predominant_category", "other")
    
    # Case 1: CONFIRMED - Same disease, boost confidence
    if user_disease == predominant:
        # Calculate confidence boost based on cluster strength
        boost = calculate_confidence_boost(cluster_size, consensus)
        refined_confidence = min(user_confidence + boost, 0.99)
        
        return {
            "validation_result": "CONFIRMED",
            "refined_diagnosis": user_disease,
            "refined_confidence": refined_confidence,
            "confidence_boost": boost,
            "original_diagnosis": user_disease,
            "cluster_predominant_disease": predominant,
            "reasoning": (
                f"Your {user_disease} diagnosis matches the predominant disease "
                f"({predominant}) in an active outbreak cluster at your exposure location. "
                f"Cluster has {cluster_size} cases with {consensus:.0%} consensus. "
                f"Confidence increased from {user_confidence:.0%} to {refined_confidence:.0%}."
            )
        }
    
    # Case 2: ALTERNATIVE - Different disease, cluster suggests different diagnosis
    # UPDATED: Now considers illness_category matching
    elif consensus >= 0.60:  # Only suggest alternative if strong cluster evidence
        alt_confidence = calculate_alternative_confidence(
            cluster_size, 
            consensus,
            user_illness_category,
            cluster_category
        )
        
        # Determine if we should suggest the alternative
        # Lower threshold if same category, higher if different
        category_match = (user_illness_category == cluster_category)
        confidence_threshold = 0.50 if category_match else 0.45
        
        if alt_confidence >= confidence_threshold:
            return {
                "validation_result": "ALTERNATIVE",
                "refined_diagnosis": predominant,
                "refined_confidence": alt_confidence,
                "original_diagnosis": user_disease,
                "cluster_predominant_disease": predominant,
                "category_match": category_match,
                "reasoning": (
                    f"Your symptoms suggested {user_disease} ({user_illness_category}), "
                    f"but {consensus:.0%} of {cluster_size} cases at this location were diagnosed with "
                    f"{predominant} ({cluster_category}). "
                    f"{'Category match suggests' if category_match else 'Despite category difference, strong cluster evidence suggests'} "
                    f"considering {predominant} as alternative diagnosis with {alt_confidence:.0%} confidence."
                )
            }
    
    # Case 3: WEAK_MATCH - User's disease is plausible but not predominant
    if consensus < 0.60:
        return {
            "validation_result": "WEAK_MATCH",
            "refined_diagnosis": user_disease,
            "refined_confidence": user_confidence,
            "cluster_predominant_disease": predominant,
            "reasoning": (
                f"A cluster of {cluster_size} cases exists at your exposure location, "
                f"but diagnoses vary. Most common is {predominant} ({consensus:.0%}), "
                f"though your {user_disease} diagnosis is also plausible for this location."
            )
        }
    
    # Case 4: LOW_CONSENSUS - Cluster exists but too diverse
    return {
        "validation_result": "LOW_CONSENSUS",
        "refined_diagnosis": user_disease,
        "refined_confidence": user_confidence,
        "cluster_predominant_disease": predominant,
        "reasoning": (
            f"Multiple illnesses reported at your exposure location "
            f"({cluster_size} cases, {predominant} most common at {consensus:.0%}). "
            f"Unable to confirm or refute your {user_disease} diagnosis based on cluster data."
        )
    }


def calculate_confidence_boost(cluster_size: int, consensus_ratio: float) -> float:
    """
    Calculate confidence boost for CONFIRMED diagnosis based on cluster strength.
    
    Args:
        cluster_size: Number of cases in cluster
        consensus_ratio: Fraction agreeing on predominant disease
    
    Returns:
        Confidence boost (0.10 to 0.30)
    """
    # Base boost from cluster size
    if cluster_size >= 20:
        size_boost = 0.20
    elif cluster_size >= 10:
        size_boost = 0.15
    elif cluster_size >= 5:
        size_boost = 0.12
    else:
        size_boost = 0.10
    
    # Additional boost from consensus
    if consensus_ratio >= 0.90:
        consensus_boost = 0.10
    elif consensus_ratio >= 0.80:
        consensus_boost = 0.07
    elif consensus_ratio >= 0.70:
        consensus_boost = 0.05
    else:
        consensus_boost = 0.03
    
    total_boost = size_boost + consensus_boost
    return min(total_boost, 0.30)  # Cap at 30% boost


def calculate_alternative_confidence(
        cluster_size: int, 
        consensus_ratio: float,
        user_illness_category: str,
        cluster_category: str
) -> float:
    """
    Calculate confidence for alternative diagnosis suggested by cluster.
    
    UPDATED: Now considers illness category matching.
    
    Conservative approach that considers:
    1. Lower base confidence than CONFIRMED cases
    2. Illness category matching (airborne vs foodborne)
    3. Strong cluster evidence required
    
    Args:
        cluster_size: Number of cases in cluster
        consensus_ratio: Fraction agreeing on predominant disease
        user_illness_category: User's diagnosis illness category
        cluster_category: Cluster's predominant illness category
    
    Returns:
        Confidence score for alternative diagnosis (0.40 to 0.85)
    """
    
    # Start conservative, base confidence depends on category match
    if user_illness_category == cluster_category:
        base = 0.55  # Same category = slightly more trust
    else:
        base = 0.40  # Different category = very skeptical
    
    # Boost based on cluster size (need strong evidence)
    if cluster_size >= 15:
        size_boost = 0.20
    elif cluster_size >= 10:
        size_boost = 0.15
    elif cluster_size >= 5:
        size_boost = 0.10
    else:
        size_boost = 0.05
    
    # Boost based on consensus (only very high consensus matters)
    if consensus_ratio >= 0.85:
        consensus_boost = 0.15
    elif consensus_ratio >= 0.80:
        consensus_boost = 0.10
    else:
        consensus_boost = 0.05
    
    confidence = base + size_boost + consensus_boost
    
    return min(confidence, 0.85)

def format_cluster_alert(validation_result: Dict, cluster_data: Dict) -> str:
    """
    Generate user-facing message about cluster validation result.
    
    Args:
        validation_result: Output from validate_diagnosis()
        cluster_data: Cluster data from query_matching_cluster()
    
    Returns:
        Formatted alert message for user
    """
    result_type = validation_result["validation_result"]
    
    if result_type == "NO_MATCH":
        return ""  # No message if no cluster found
    
    cluster_size = cluster_data["cluster_size"]
    sample_tag = cluster_data["sample_exposure_tag"]
    consensus = cluster_data["consensus_ratio"]
    
    # Format the exposure location nicely
    location = sample_tag.replace("_", " ").title() if sample_tag else "this location"
    
    if result_type == "CONFIRMED":
        return f"""âœ… OUTBREAK CONFIRMATION

We've detected an active outbreak cluster of {cluster_size} cases linked to your reported exposure location.

Your diagnosis of {validation_result['refined_diagnosis']} matches the outbreak pattern we're tracking - {consensus:.0%} of cases at this location have been diagnosed with the same condition. 
Based on this strong outbreak pattern, I'm increasing my confidence in this diagnosis from {validation_result.get('original_confidence', 0)*100:.0f}% to {validation_result['refined_confidence']*100:.0f}%.
"""
    
    elif result_type == "ALTERNATIVE":
        category_note = ""
        if validation_result.get("category_match"):
            category_note = " (both in the same illness category)"
        else:
            category_note = " (note: different illness categories)"
            
        return f"""ðŸ©º ALTERNATIVE DIAGNOSIS SUGGESTED

We've detected an active outbreak cluster of {cluster_size} cases linked to your reported exposure location.

While your symptoms initially suggested {validation_result['original_diagnosis']}, {consensus:.0%} of people exposed at this location were diagnosed with {validation_result['refined_diagnosis']}{category_note}. 
Given this outbreak pattern, I'm suggesting {validation_result['refined_diagnosis']} as an alternative diagnosis with {validation_result['refined_confidence']*100:.0f}% confidence.
Please discuss this finding with your healthcare provider.
"""
    
    elif result_type == "WEAK_MATCH":
        return f"""â„¹ï¸ CLUSTER INFORMATION

We've detected {cluster_size} illness reports from your reported exposure location.

The diagnoses vary, with {validation_result['cluster_predominant_disease']} being most common ({consensus:.0%} of cases), though your {validation_result['refined_diagnosis']} diagnosis is also consistent with exposure at this location. 
Your diagnosis remains unchanged, but we're flagging this cluster activity for your awareness.
"""
    
    else:  # LOW_CONSENSUS
        return f"""ðŸ“ CLUSTER DETECTED

{cluster_size} people exposed at your reported exposure location have reported varied illnesses.

Due to the diversity of diagnoses, we cannot confirm or refute your {validation_result['refined_diagnosis']} 
diagnosis based on cluster data. Your original diagnosis stands.
"""

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Main entry point for cluster validation agent.
    
    Called AFTER BQ submission to validate diagnosis against active outbreak clusters.
    
    Input format (JSON):
    {
        "user_disease": "Gastroenteritis",
        "user_confidence": 0.65,
        "exposure_latitude": 41.8781,
        "exposure_longitude": -87.6298,
        "days_since_exposure": 2,
        "illness_category": "foodborne"
    }
    
    Output format (JSON):
    {
        "cluster_found": true/false,
        "cluster_data": {...},
        "validation_result": "CONFIRMED" | "ALTERNATIVE" | "WEAK_MATCH" | "NO_MATCH",
        "refined_diagnosis": "Norovirus",
        "refined_confidence": 0.80,
        "original_diagnosis": "Gastroenteritis",
        "original_confidence": 0.65,
        "confidence_boost": 0.15,
        "reasoning": "...",
        "console_output": "Alert message for user"
    }
    """
    try:
        data = json.loads(user_msg)
    except Exception as e:
        return json.dumps({
            "error": f"Invalid input JSON: {e}",
            "cluster_found": False,
            "validation_result": "ERROR"
        }), history
    
    # Parse input
    user_disease = data.get("user_disease")
    user_confidence = data.get("user_confidence", 0.5)
    exposure_lat = data.get("exposure_latitude")
    exposure_lon = data.get("exposure_longitude")
    days_since_exposure = data.get("days_since_exposure")
    illness_category = data.get("illness_category")
    
    # Validate required fields
    if not all([user_disease, exposure_lat is not None, exposure_lon is not None, 
                days_since_exposure is not None]):
        return json.dumps({
            "error": "Missing required fields: user_disease, exposure_latitude, exposure_longitude, days_since_exposure",
            "cluster_found": False,
            "validation_result": "ERROR"
        }), history
    
    print(f"ðŸ” Validating diagnosis: {user_disease} ({user_confidence:.0%} confidence)")
    print(f"   Exposure: ({exposure_lat}, {exposure_lon}), {days_since_exposure} days ago")
    print(f"   User category: {illness_category}")
    
    # Query for matching cluster
    cluster_data = query_matching_cluster(
        exposure_lat, 
        exposure_lon, 
        days_since_exposure,
        user_disease,
        illness_category
    )
    
    cluster_found = bool(cluster_data)
    
    if cluster_found:
        print(f"âœ… Cluster found: {cluster_data['exposure_cluster_id']}")
        print(f"   Size: {cluster_data['cluster_size']}, Predominant: {cluster_data['predominant_disease']}")
        print(f"   Consensus: {cluster_data['consensus_ratio']:.0%}")
        print(f"   Cluster category: {cluster_data.get('predominant_category', 'unknown')}")
    
    # Validate diagnosis against cluster
    validation_result = validate_diagnosis(
        user_disease, 
        user_confidence, 
        illness_category,
        cluster_data
    )
    
    # Format user message
    console_output = format_cluster_alert(validation_result, cluster_data) if cluster_found else ""
    
    # Build response
    result = {
        "cluster_found": cluster_found,
        "cluster_data": cluster_data,
        "validation_result": validation_result["validation_result"],
        "refined_diagnosis": validation_result["refined_diagnosis"],
        "refined_confidence": validation_result["refined_confidence"],
        "original_diagnosis": validation_result.get("original_diagnosis", user_disease),
        "original_confidence": user_confidence,
        "confidence_boost": validation_result.get("confidence_boost", 0.0),
        "reasoning": validation_result["reasoning"],
        "console_output": console_output
    }
    
    return json.dumps(result, indent=2), history