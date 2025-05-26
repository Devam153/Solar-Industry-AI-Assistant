import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')  # You'll need this too

# Solar calculation constants
SOLAR_PANEL_EFFICIENCY = 0.20  # 20% efficiency
PEAK_SUN_HOURS = 5.5  # Average for most locations
ELECTRICITY_RATE = 0.12  # $0.12 per kWh
SYSTEM_COST_PER_WATT = 3.50  # $3.50 per watt installed
