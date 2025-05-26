
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_google_maps_api():
    """Test Google Maps API key for Geocoding and Static Maps APIs"""
    
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key:
        print("❌ ERROR: GOOGLE_MAPS_API_KEY not found in .env file")
        return False
    
    print(f"🔑 Testing API Key: {api_key[:10]}...")
    print("-" * 50)
    
    # Test 1: Geocoding API
    print("🌍 Testing Geocoding API...")
    test_address = "1600 Amphitheatre Parkway, Mountain View, CA"
    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={test_address}&key={api_key}"
    
    try:
        response = requests.get(geocoding_url)
        data = response.json()
        
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            lat, lng = location['lat'], location['lng']
            print(f"✅ Geocoding API: SUCCESS")
            print(f"   Address: {test_address}")
            print(f"   Coordinates: {lat}, {lng}")
        else:
            print(f"❌ Geocoding API: FAILED - {data['status']}")
            return False
            
    except Exception as e:
        print(f"❌ Geocoding API: ERROR - {str(e)}")
        return False
    
    print("-" * 50)
    
    # Test 2: Static Maps API (Satellite Image)
    print("🛰️ Testing Static Maps API...")
    static_map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=20&size=640x640&maptype=satellite&key={api_key}"
    
    try:
        response = requests.get(static_map_url)
        
        if response.status_code == 200 and response.headers.get('content-type', '').startswith('image'):
            print(f"✅ Static Maps API: SUCCESS")
            print(f"   Image size: {len(response.content)} bytes")
            print(f"   Image URL: {static_map_url}")
        else:
            print(f"❌ Static Maps API: FAILED - Status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Static Maps API: ERROR - {str(e)}")
        return False
    
    print("-" * 50)
    print("🎉 ALL TESTS PASSED! Your Google Maps API is ready for the solar project!")
    return True

if __name__ == "__main__":
    print("🧪 Testing Google Maps API Configuration")
    print("=" * 50)
    test_google_maps_api()