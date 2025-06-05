import requests
import os
from dotenv import load_dotenv
import io
from PIL import Image
import base64

# Load environment variables
load_dotenv()

def fetch_satellite_image(lat, lng, zoom=21, size="640x640", image_format="png"):
    """
    Fetch high-resolution satellite image using Google Maps Static API
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        zoom (int): Zoom level (1-21, higher = more detailed) - Default 21 for single building
        size (str): Image size in format "widthxheight" (max 640x640 for free tier)
        image_format (str): Image format (png, jpg, gif)
        
    Returns:
        dict: Contains 'image_data', 'url', 'success' if successful, 'error' if failed
    """
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key:
        return {"error": "Google Maps API key not found in environment variables"}
    
    # Validate coordinates
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return {"error": "Invalid coordinates provided"}
    
    # Google Maps Static API endpoint
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    
    params = {
        'center': f"{lat},{lng}",
        'zoom': zoom,
        'size': size,
        'maptype': 'satellite',
        'format': image_format,
        'key': api_key
    }
    
    try:
        print(f"🛰️ Fetching satellite image for coordinates: {lat}, {lng} at zoom {zoom}")
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            # Check if response is actually an image
            content_type = response.headers.get('content-type', '')
            if content_type.startswith('image'):
                return {
                    'image_data': response.content,
                    'url': response.url,
                    'size': len(response.content),
                    'content_type': content_type,
                    'success': True
                }
            else:
                # Response might be an error message
                try:
                    error_text = response.text
                    return {"error": f"API returned error: {error_text}"}
                except:
                    return {"error": "Invalid response from Maps API"}
        else:
            return {"error": f"HTTP error {response.status_code}: {response.text}"}
            
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def get_image_info(image_data):
    """
    Get image information using PIL
    
    Args:
        image_data (bytes): Image data
        
    Returns:
        dict: Image information (width, height, format, etc.)
    """
    try:
        image = Image.open(io.BytesIO(image_data))
        return {
            'width': image.width,
            'height': image.height,
            'format': image.format,
            'mode': image.mode,
            'success': True
        }
    except Exception as e:
        return {"error": f"Failed to analyze image: {str(e)}"}

def fetch_satellite_image_complete(address=None, lat=None, lng=None, zoom=21):
    """
    Complete workflow: geocode address (if needed) and fetch satellite image
    Returns image data in memory without saving to disk
    
    Args:
        address (str): Address to geocode (optional if lat/lng provided)
        lat (float): Latitude (optional if address provided)
        lng (float): Longitude (optional if address provided)
        zoom (int): Zoom level for the satellite image
        
    Returns:
        dict: Complete result with coordinates, image data, and image info
    """
    from .geocoding import get_coordinates_from_address
    
    # Get coordinates if not provided
    if lat is None or lng is None:
        if not address:
            return {"error": "Either address or coordinates (lat, lng) must be provided"}
        
        print(f"📍 Geocoding address: {address}")
        geo_result = get_coordinates_from_address(address)
        
        if 'error' in geo_result:
            return {"error": f"Geocoding failed: {geo_result['error']}"}
        
        lat = geo_result['lat']
        lng = geo_result['lng']
        formatted_address = geo_result.get('formatted_address', address)
    else:
        formatted_address = f"{lat}, {lng}"
    
    # Fetch satellite image with the specified zoom level
    image_result = fetch_satellite_image(lat, lng, zoom=zoom)
    
    if 'error' in image_result:
        return {"error": f"Image fetch failed: {image_result['error']}"}
    
    # Get image info
    image_info = get_image_info(image_result['image_data'])
    
    return {
        'success': True,
        'coordinates': {'lat': lat, 'lng': lng},
        'formatted_address': formatted_address,
        'image_url': image_result['url'],
        'image_data': image_result['image_data'],  # Raw bytes for in-memory use
        'image_size_bytes': image_result['size'],
        'image_info': image_info,
        'content_type': image_result['content_type']
    }

def convert_image_for_streamlit(image_data):
    """
    Convert image data to format suitable for Streamlit display
    
    Args:
        image_data (bytes): Raw image data
        
    Returns:
        PIL.Image: Image object that can be displayed in Streamlit
    """
    try:
        return Image.open(io.BytesIO(image_data))
    except Exception as e:
        print(f"Error converting image for Streamlit: {str(e)}")
        return None

# Test function for in-memory processing
def test_in_memory_fetch():
    """Test the in-memory image fetching functionality"""
    print("🧪 Testing In-Memory Satellite Image Fetching")
    print("=" * 60)
    
    test_locations = [
        {"address": "1600 Amphitheatre Parkway, Mountain View, CA", "name": "Google HQ"},
        {"lat": 37.4220095, "lng": -122.0847514, "name": "Googleplex (Direct Coords)"}
    ]
    
    for i, location in enumerate(test_locations, 1):
        print(f"\n🏢 Test {i}: {location['name']}")
        print("-" * 40)
        
        if 'address' in location:
            result = fetch_satellite_image_complete(address=location['address'])
        else:
            result = fetch_satellite_image_complete(lat=location['lat'], lng=location['lng'])
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Success!")
            print(f"   📍 Coordinates: {result['coordinates']['lat']}, {result['coordinates']['lng']}")
            print(f"   📏 Image size: {result['image_size_bytes']} bytes")
            print(f"   🌐 Address: {result['formatted_address']}")
            
            # Test Streamlit conversion
            streamlit_image = convert_image_for_streamlit(result['image_data'])
            if streamlit_image:
                print(f"   🖼️ Streamlit ready: {streamlit_image.size}")
            else:
                print(f"   ❌ Streamlit conversion failed")
    
    print("\n" + "=" * 60)
    print("🎉 In-memory image fetching tests completed!")

if __name__ == "__main__":
    test_in_memory_fetch()