# helpers.py
"""
Shared helper functions for all agents and the orchestrator.
"""
import json
import re
import sys
from google import genai
from google.genai import types
from config import PROJECT_ID, LOCATION, MODEL
from datetime import datetime, timedelta
import requests

# --- Markdown fence stripper ---
def strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

# --- Chat history serialization helpers ---
def serialize_history(history: list) -> list:
    """
    Converts a list of types.Content to a list of dicts for session storage.
    """
    result = []
    for msg in history:
        # If types.Content object
        if hasattr(msg, 'role') and hasattr(msg, 'parts'):
            part_text = msg.parts[0].text if msg.parts else ""
            result.append({"role": msg.role, "content": part_text})
        # Already a dict
        elif isinstance(msg, dict):
            result.append({"role": msg.get("role"), "content": msg.get("content")})
    return result

def deserialize_history(history: list) -> list:
    """
    Converts a list of dicts (from session) to a list of types.Content for LLM.
    """
    result = []
    for msg in history:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            result.append(types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["content"])]))
    return result

# --- Gemini chat generate ---
def generate(user_message: str, history: list, system_prompt: str):
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    # Apply custom system prompt
    custom = system_prompt
    # Append user message
    if user_message:
        history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
    # Configure
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
        ],
        response_mime_type="text/plain",
        system_instruction=[types.Part.from_text(text=custom)]
    )
    # Stream responses
    resp_text = ""
    for chunk in client.models.generate_content_stream(
        model=MODEL, contents=history, config=cfg
    ):
        resp_text += chunk.text
    # Append model reply to history
    history.append(
        types.Content(role="model", parts=[types.Part.from_text(text=resp_text.strip())])
    )
    return resp_text.strip(), history

# --- JSON extractor ---
def extract_json(raw_text: str):
    clean = strip_fences(raw_text)
    return json.loads(clean)

# --- Date parser (compute days ago) ---
import dateparser

def compute_days_ago(text_date, today=None):
    if not text_date or not isinstance(text_date, str):
        print("⚠️ No valid text_date provided to compute_days_ago.")
        return None

    if not today:
        today = datetime.now()

    text_date = text_date.lower().strip()

    if "over the weekend" in text_date:
        last_sunday = today - timedelta(days=today.weekday() + 1)
        return max((today - last_sunday).days, 0)

    # Normalize phrasing
    text_date = re.sub(r'\b(this past|last|the past|past)\b', '', text_date)
    text_date = re.sub(r'\b(morning|afternoon|evening|night)\b', '', text_date)

    parsed = dateparser.parse(
        text_date,
        settings={
            'PREFER_DATES_FROM': 'past',
            'RELATIVE_BASE': today
        }
    )

    if parsed:
        return max((today - parsed).days, 0)

    print(f"⚠️ Could not parse date: {text_date}")
    return None

def determine_final_diagnosis(top_matches, clarification_answers):
    evidence = {
        "answers": clarification_answers,
        "positive_keywords": ["yes", "y", "true", "present"],
        "negative_keywords": ["no", "n", "false", "absent"]
    }
    scored_matches = []
    for match in top_matches:
        score = match["score"]
        reasoning = []
        if "fever" in match["id"].lower():
            if any("fever" in ans.lower() for ans in clarification_answers):
                score += 0.2
                reasoning.append("Patient confirmed fever")
        scored_matches.append({
            "id": match["id"],
            "final_score": min(1.0, score),
            "reasoning": "; ".join(reasoning) if reasoning else "No additional evidence"
        })
    final_match = max(scored_matches, key=lambda x: x["final_score"])
    return {
        "diagnosis": final_match["id"],
        "confidence": final_match["final_score"],
        "reasoning": final_match["reasoning"] or f"Highest initial score ({final_match['final_score']})"
    }

def clean_location_string(location_string):
    """
    Clean up location string by removing duplicate parts.
    
    Examples:
        "West avenue, West avenue, Springfield, IL" → "West avenue, Springfield, IL"
        "Chicago, IL, Chicago, IL" → "Chicago, IL"
        "Main St, Austin, TX, Austin, TX" → "Main St, Austin, TX"
    
    Args:
        location_string: Raw location string that might have duplicates
    
    Returns:
        Cleaned location string with duplicates removed
    """
    if not location_string:
        return location_string
    
    # Split by comma
    parts = [part.strip() for part in location_string.split(',')]
    
    # Remove consecutive duplicates (case-insensitive)
    cleaned_parts = []
    prev_part_lower = None
    
    for part in parts:
        part_lower = part.lower()
        if part_lower != prev_part_lower:
            cleaned_parts.append(part)
            prev_part_lower = part_lower
    
    # Rejoin with commas
    return ', '.join(cleaned_parts)

def geocode_location(location_name, bias_lat=None, bias_lon=None):
    """
    Convert location name to lat/lon using Google Maps APIs.
    
    Strategy:
    1. Try Geocoding API first (for addresses, landmarks)
    2. If that fails, try Places API (New) for business names
    3. Use GPS bias when available
    
    Args:
        location_name: Location string from user
        bias_lat: User's current latitude (optional, for proximity bias)
        bias_lon: User's current longitude (optional, for proximity bias)
    
    Returns:
        (latitude, longitude) or (None, None) if not found
    """
    import os
    import requests
    from math import radians, sin, cos, sqrt, atan2
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance in miles between two lat/lon points"""
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_km = 6371 * c
        return distance_km * 0.621371  # Convert to miles
    
    try:
        # Get API key from environment
        api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if not api_key:
            print("[Geocoding] ❌ ERROR: GOOGLE_MAPS_API_KEY not set in environment")
            return None, None
        
        if not location_name:
            return None, None
        
        location_name = clean_location_string(location_name)
        
        print(f"[Geocoding] Input: '{location_name}'")
        if bias_lat and bias_lon:
            print(f"[Geocoding]   GPS bias: ({bias_lat}, {bias_lon})")
        
        # ====================================================================
        # STRATEGY 1: Try Places API (New) for business names
        # ====================================================================
        try:
            print(f"[Geocoding]   Strategy 1: Searching Places API (New)...")
            
            # Build request URL
            url = "https://places.googleapis.com/v1/places:searchText"
            
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types"
            }
            
            body = {
                "textQuery": location_name,
                "languageCode": "en"
            }
            
            # Add location bias if GPS available
            if bias_lat and bias_lon:
                body["locationBias"] = {
                    "circle": {
                        "center": {
                            "latitude": bias_lat,
                            "longitude": bias_lon
                        },
                        "radius": 50000.0  # 50km = ~31 miles
                    }
                }
            
            response = requests.post(url, headers=headers, json=body, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('places') and len(data['places']) > 0:
                    place = data['places'][0]
                    lat = place['location']['latitude']
                    lon = place['location']['longitude']
                    name = place.get('displayName', {}).get('text', 'Unknown')
                    address = place.get('formattedAddress', name)
                    place_types = place.get('types', [])
                    
                    # Calculate distance
                    distance_miles = None
                    if bias_lat and bias_lon:
                        distance_miles = calculate_distance(bias_lat, bias_lon, lat, lon)
                    
                    print(f"[Geocoding] ✅ Found via Places API: {address}")
                    print(f"[Geocoding]    Name: {name}")
                    print(f"[Geocoding]    Type: {', '.join(place_types[:2])}")
                    print(f"[Geocoding]    Coordinates: ({lat}, {lon})")
                    
                    if distance_miles is not None:
                        print(f"[Geocoding]    📍 Distance: {distance_miles:.1f} miles")
                        if distance_miles > 100:
                            print(f"[Geocoding]    ⚠️  WARNING: Location is {distance_miles:.0f} miles from user")
                    
                    return lat, lon
                else:
                    print(f"[Geocoding]   ℹ️  No results from Places API")
            
            elif response.status_code == 403:
                print(f"[Geocoding]   ⚠️  Places API not enabled or restricted")
            else:
                print(f"[Geocoding]   ⚠️  Places API error: {response.status_code}")
        
        except requests.exceptions.Timeout:
            print(f"[Geocoding]   ⏱️  Places API timeout")
        except Exception as e:
            print(f"[Geocoding]   ⚠️  Places API error: {e}")
        
        # ====================================================================
        # STRATEGY 2: Try Geocoding API (for addresses, landmarks)
        # ====================================================================
        try:
            print(f"[Geocoding]   Strategy 2: Trying Geocoding API...")
            
            import googlemaps
            gmaps = googlemaps.Client(key=api_key)
            
            # Build geocode params
            params = {}
            if bias_lat and bias_lon:
                params['bounds'] = {
                    'southwest': {'lat': bias_lat - 0.2, 'lng': bias_lon - 0.2},
                    'northeast': {'lat': bias_lat + 0.2, 'lng': bias_lon + 0.2}
                }
                params['region'] = 'us'
            
            result = gmaps.geocode(location_name, **params)
            
            if result:
                location = result[0]['geometry']['location']
                lat, lon = location['lat'], location['lng']
                address = result[0].get('formatted_address', 'Unknown')
                place_types = result[0].get('types', [])
                
                # Calculate distance
                distance_miles = None
                if bias_lat and bias_lon:
                    distance_miles = calculate_distance(bias_lat, bias_lon, lat, lon)
                
                print(f"[Geocoding] ✅ Found via Geocoding API: {address}")
                print(f"[Geocoding]    Type: {', '.join(place_types[:2])}")
                print(f"[Geocoding]    Coordinates: ({lat}, {lon})")
                
                if distance_miles is not None:
                    print(f"[Geocoding]    📍 Distance: {distance_miles:.1f} miles")
                    if distance_miles > 100:
                        print(f"[Geocoding]    ⚠️  WARNING: Location is {distance_miles:.0f} miles from user")
                
                return lat, lon
            else:
                print(f"[Geocoding]   ℹ️  No results from Geocoding API")
        
        except Exception as e:
            print(f"[Geocoding]   ⚠️  Geocoding API error: {e}")
        
        # ====================================================================
        # All strategies failed
        # ====================================================================
        print(f"[Geocoding] ❌ Could not geocode: '{location_name}'")
        return None, None
        
    except Exception as e:
        print(f"[Geocoding] ❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def parse_json_from_response(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(match.group()) if match else None
    except Exception as e:
        print("❌ Failed to parse JSON:", e)
        return None

def fix_json(response: str) -> dict:
    try:
        return json.loads(response.strip("`").replace("'", '"'))
    except:
        return {"text": response, "error": "auto_fixed"}

def get_input(prompt: str) -> str:
    text = input(prompt).strip()
    if text.lower() in ("quit", "exit"):
        print("👋 Goodbye!")
        sys.exit(0)
    return text

def normalize_agent_response(raw_response: str, response_type: str) -> dict:
    try:
        cleaned = strip_fences(raw_response)
        data = fix_json(cleaned)
        if data is None:
            data = {}
        if response_type == "exposure":
            if not isinstance(data, dict):
                data = {"questions": [str(data)]}
            if "questions" in data and isinstance(data["questions"], str):
                data["questions"] = [data["questions"]]
        if response_type == "location":
            if not isinstance(data, dict):
                data = {"location_name": str(data)}
            normalized = {
                "current_location_name": data.get("location_name") or data.get("location") or data.get("current_location_name"),
                "current_latitude": data.get("latitude") or data.get("lat") or data.get("current_latitude"),
                "current_longitude": data.get("longitude") or data.get("lon") or data.get("current_longitude"),
                "location_category": data.get("location_category")
            }
            data = normalized
        return data
    except Exception as e:
        print(f"⚠️ Normalization error ({response_type}): {str(e)}")
        return {"error": f"Failed to normalize {response_type} response"}

def reverse_geocode(latitude: float, longitude: float) -> str:
    """
    Convert lat/lon coordinates to a human-readable location name.
    Uses OpenStreetMap Nominatim reverse geocoding API.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        Location string like "123 Main St, Chicago, IL" or None if failed
    """
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1
            },
            headers={"User-Agent": "EarlySignalHealthApp/1.0"},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            
            # Build location string from components
            parts = []
            
            # Street address
            house_number = address.get("house_number", "")
            road = address.get("road", "")
            if house_number and road:
                parts.append(f"{house_number} {road}")
            elif road:
                parts.append(road)
            
            # City
            city = (address.get("city") or 
                   address.get("town") or 
                   address.get("village") or 
                   address.get("municipality"))
            if city:
                parts.append(city)
            
            # State
            state = address.get("state")
            if state:
                parts.append(state)
            
            location_str = ", ".join(parts) if parts else data.get("display_name")
            
            print(f"🗺️ Reverse geocoded ({latitude}, {longitude}) → {location_str}")
            return location_str
            
    except Exception as e:
        print(f"⚠️ Reverse geocoding failed: {e}")
    
    return None