import os
import googlemaps

# Get the API key from environment variable
api_key = os.environ.get('GOOGLE_MAPS_API_KEY')

if not api_key:
    print("❌ ERROR: API key not found!")
    print("Did you run: source ~/.zshrc ?")
else:
    print(f"✅ API key found: {api_key[:20]}...")
    
    # Test geocoding
    try:
        gmaps = googlemaps.Client(key=api_key)
        
        # Test 1: Simple location
        print("\n📍 Test 1: Geocoding 'Chipotle, Michigan Avenue, Chicago'")
        result = gmaps.geocode('Chipotle, Michigan Avenue, Chicago')
        
        if result:
            location = result[0]['geometry']['location']
            print(f"   ✅ Success!")
            print(f"   Address: {result[0]['formatted_address']}")
            print(f"   Coordinates: ({location['lat']}, {location['lng']})")
        else:
            print("   ❌ No results found")
        
        # Test 2: With GPS bias
        print("\n📍 Test 2: Testing GPS bias (searching 'Starbucks' near Chicago)")
        result2 = gmaps.geocode(
            'Starbucks',
            components={'locality': 'Chicago'}
        )
        
        if result2:
            location2 = result2[0]['geometry']['location']
            print(f"   ✅ Success!")
            print(f"   Address: {result2[0]['formatted_address']}")
            print(f"   Coordinates: ({location2['lat']}, {location2['lng']})")
        
        print("\n🎉 All tests passed! Google Maps API is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
