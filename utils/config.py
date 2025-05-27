"""
Configuration management for Solar Analysis Application
Centralized settings and constants
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SolarConfig:
    """Configuration class for solar analysis settings"""
    
    # API Configuration
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    
    # Image Settings
    DEFAULT_ZOOM_LEVEL = 20
    DEFAULT_IMAGE_SIZE = "640x640"
    MAX_IMAGE_SIZE = "640x640"  # Free tier limit
    IMAGE_FORMAT = "png"
    
    # Solar Panel Specifications
    STANDARD_PANEL_WATTAGE = 400  # Watts
    STANDARD_PANEL_SIZE_SQFT = 17.6  # Square feet
    PANEL_EFFICIENCY = 0.22  # 22% efficiency
    
    # System Performance
    SYSTEM_EFFICIENCY = 0.85  # 85% overall system efficiency
    INVERTER_EFFICIENCY = 0.96  # 96% inverter efficiency
    DC_AC_RATIO = 1.2  # DC to AC ratio
    
    # Financial Defaults
    DEFAULT_ELECTRICITY_RATE = 0.12  # $/kWh
    COST_PER_WATT_INSTALLED = 3.50  # $/W
    FEDERAL_TAX_CREDIT = 0.30  # 30%
    ANNUAL_DEGRADATION = 0.005  # 0.5% per year
    SYSTEM_LIFETIME = 25  # Years
    
    # Regional Solar Data (simplified)
    SOLAR_IRRADIANCE_BY_REGION = {
        'southwest': 6.5,  # kWh/m²/day
        'southeast': 5.8,
        'west': 5.5,
        'midwest': 4.8,
        'northeast': 4.2,
        'northwest': 4.0
    }
    
    # Analysis Thresholds
    MIN_ROOF_AREA_SQFT = 100  # Minimum roof area for solar
    MIN_PANELS_RECOMMENDED = 6  # Minimum panels for viable system
    EXCELLENT_SOLAR_THRESHOLD = 80  # % for excellent rating
    GOOD_SOLAR_THRESHOLD = 60  # % for good rating
    
    # Streamlit UI Settings
    PAGE_TITLE = "Solar Roof Analysis"
    PAGE_ICON = "🔆"
    LAYOUT = "wide"
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        issues = []
        
        if not cls.GOOGLE_MAPS_API_KEY:
            issues.append("GOOGLE_MAPS_API_KEY is not set")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    @classmethod
    def get_regional_sun_hours(cls, latitude):
        """Get estimated daily sun hours based on latitude"""
        lat_abs = abs(latitude)
        
        if lat_abs <= 25:
            return 6.5  # Tropical
        elif lat_abs <= 35:
            return 5.8  # Subtropical
        elif lat_abs <= 45:
            return 5.2  # Temperate
        elif lat_abs <= 55:
            return 4.5  # Cool temperate
        else:
            return 3.8  # Subarctic
    
    @classmethod
    def get_electricity_rates_by_state(cls):
        """Average electricity rates by state (simplified)"""
        return {
            'CA': 0.21, 'NY': 0.18, 'MA': 0.22, 'CT': 0.21, 'RI': 0.20,
            'TX': 0.12, 'FL': 0.11, 'GA': 0.11, 'NC': 0.11, 'SC': 0.12,
            'AZ': 0.13, 'NV': 0.12, 'CO': 0.12, 'UT': 0.10, 'NM': 0.12,
            'WA': 0.09, 'OR': 0.11, 'ID': 0.10, 'MT': 0.11, 'WY': 0.11
        }

# Global configuration instance
config = SolarConfig()

# Helper functions
def get_config_summary():
    """Get a summary of current configuration"""
    return {
        'api_configured': bool(config.GOOGLE_MAPS_API_KEY),
        'default_zoom': config.DEFAULT_ZOOM_LEVEL,
        'panel_wattage': config.STANDARD_PANEL_WATTAGE,
        'system_efficiency': config.SYSTEM_EFFICIENCY,
        'tax_credit': config.FEDERAL_TAX_CREDIT * 100,
        'system_lifetime': config.SYSTEM_LIFETIME
    }

def validate_environment():
    """Validate the environment setup"""
    validation = config.validate_config()
    
    if validation['valid']:
        return {
            'status': 'ready',
            'message': 'All configuration validated successfully'
        }
    else:
        return {
            'status': 'error',
            'message': f"Configuration issues: {', '.join(validation['issues'])}"
        }