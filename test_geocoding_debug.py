import os
import googlemaps

# Get API key
api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
print(f"API Key: {api_key[:20]}...")

# Initialize client
gmaps = googlemaps.Client(key=api_key)

# User's GPS location (Chicago)
user_lat = 41.8922417
user_lon = -87.6179083

print("\n" + "="*70)
print("TEST 1: Simple query (no bounds)")
print("="*70)

try:
    result1 = gmaps.geocode("McDonald's")
    if result1:
        print(f"✅ Found: {result1[0]['formatted_address']}")
        print(f"   Types: {result1[0]['types']}")
    else:
        print("❌ No results")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("TEST 2: With typo (Mc donalds)")
print("="*70)

try:
    result2 = gmaps.geocode("Mc donalds")
    if result2:
        print(f"✅ Found: {result2[0]['formatted_address']}")
        print(f"   Types: {result2[0]['types']}")
    else:
        print("❌ No results")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("TEST 3: With GPS bounds")
print("="*70)

try:
    result3 = gmaps.geocode(
        "Mc donalds",
        bounds={
            'southwest': {'lat': user_lat - 0.2, 'lng': user_lon - 0.2},
            'northeast': {'lat': user_lat + 0.2, 'lng': user_lon + 0.2}
        }
    )
    if result3:
        print(f"✅ Found: {result3[0]['formatted_address']}")
        print(f"   Types: {result3[0]['types']}")
        print(f"   Location: {result3[0]['geometry']['location']}")
    else:
        print("❌ No results")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("TEST 4: With region parameter")
print("="*70)

try:
    result4 = gmaps.geocode(
        "Mc donalds",
        region='us',
        bounds={
            'southwest': {'lat': user_lat - 0.2, 'lng': user_lon - 0.2},
            'northeast': {'lat': user_lat + 0.2, 'lng': user_lon + 0.2}
        }
    )
    if result4:
        print(f"✅ Found: {result4[0]['formatted_address']}")
        print(f"   Types: {result4[0]['types']}")
    else:
        print("❌ No results")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*70)
print("TEST 5: Just 'McDonald' (no 's')")
print("="*70)

try:
    result5 = gmaps.geocode(
        "McDonald",
        bounds={
            'southwest': {'lat': user_lat - 0.2, 'lng': user_lon - 0.2},
            'northeast': {'lat': user_lat + 0.2, 'lng': user_lon + 0.2}
        }
    )
    if result5:
        print(f"✅ Found: {result5[0]['formatted_address']}")
        print(f"   Types: {result5[0]['types']}")
    else:
        print("❌ No results")
except Exception as e:
    print(f"❌ Error: {e}")
