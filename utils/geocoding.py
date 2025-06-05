import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_coordinates_from_address(address):
    """
    Convert an address to latitude and longitude coordinates using Google Maps Geocoding API
    
    Args:
        address (str): The address to geocode
        
    Returns:
        dict: Contains 'lat', 'lng', 'formatted_address' if successful, 'error' if failed
    """
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key:
        return {"error": "Google Maps API key not found in environment variables"}
    
    # Google Maps Geocoding API endpoint
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        'address': address,
        'key': api_key
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data['status'] == 'OK':
            result = data['results'][0]
            location = result['geometry']['location']
            
            return {
                'lat': location['lat'],
                'lng': location['lng'],
                'formatted_address': result['formatted_address'],
                'success': True
            }
        elif data['status'] == 'ZERO_RESULTS':
            return {"error": "No results found for the given address"}
        elif data['status'] == 'OVER_QUERY_LIMIT':
            return {"error": "API quota exceeded"}
        elif data['status'] == 'REQUEST_DENIED':
            return {"error": "API request denied - check your API key"}
        else:
            return {"error": f"Geocoding failed: {data['status']}"}
            
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def validate_coordinates(lat, lng):
    """
    Validate if coordinates are within valid ranges
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        
    Returns:
        bool: True if coordinates are valid
    """
    try:
        lat = float(lat)
        lng = float(lng)
        return -90 <= lat <= 90 and -180 <= lng <= 180
    except (ValueError, TypeError):
        return False

# Test function for geocoding
def test_geocoding():
    """Test the geocoding function with sample addresses"""
    print("🧪 Testing Geocoding Functions")
    print("=" * 50)
    
    test_addresses = [
        "1600 Amphitheatre Parkway, Mountain View, CA",
        "1 Apple Park Way, Cupertino, CA",
        "350 5th Ave, New York, NY 10118"  # Empire State Building
    ]
    
    for address in test_addresses:
        print(f"Testing address: {address}")
        result = get_coordinates_from_address(address)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Success!")
            print(f"Coordinates: {result['lat']}, {result['lng']}")
            print(f"Formatted: {result['formatted_address']}")
            
            # Validate coordinates
            if validate_coordinates(result['lat'], result['lng']):
                print(f"Coordinates are valid")
            else:
                print(f"Invalid coordinates")
    
    print("\n" + "=" * 50)
    print("Geocoding tests completed!")

if __name__ == "__main__":
    test_geocoding()