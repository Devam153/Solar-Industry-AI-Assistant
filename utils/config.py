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
    DEFAULT_ZOOM_LEVEL = 21  # Much higher zoom for single building focus
    DEFAULT_IMAGE_SIZE = "640x640"
    MAX_IMAGE_SIZE = "640x640"  # Free tier limit
    IMAGE_FORMAT = "png"
    
    # Solar Panel Specifications (Indian standards)
    STANDARD_PANEL_WATTAGE = 330  # Watts (common in India)
    STANDARD_PANEL_SIZE_SQFT = 16  # Square feet (smaller for Indian panels)
    PANEL_EFFICIENCY = 0.20  # 20% efficiency
    
    # System Performance (Indian conditions)
    SYSTEM_EFFICIENCY = 0.80  # 80% overall system efficiency (dust/heat factor)
    INVERTER_EFFICIENCY = 0.95  # 95% inverter efficiency
    DC_AC_RATIO = 1.15  # DC to AC ratio
    
    # Financial Defaults (Indian market in INR)
    DEFAULT_ELECTRICITY_RATE = 6.50  # ₹/kWh (Indian residential rate)
    COST_PER_WATT_INSTALLED = 45  # ₹/W (Indian market rate)
    CENTRAL_SUBSIDY = 0.40  # 40% central + state subsidies
    ANNUAL_DEGRADATION = 0.005  # 0.5% per year
    SYSTEM_LIFETIME = 25  # Years
    CURRENCY_SYMBOL = "₹"  # Indian Rupee symbol
    CURRENCY_CODE = "INR"
    
    # Regional Solar Data (India specific)
    SOLAR_IRRADIANCE_BY_REGION = {
        'south_india': 5.5,  # kWh/m²/day (Karnataka, Tamil Nadu, Kerala)
        'west_india': 5.8,   # Gujarat, Rajasthan, Maharashtra
        'north_india': 4.8,  # Delhi, UP, Haryana
        'central_india': 5.3, # MP, Telangana
        'east_india': 4.5,   # West Bengal, Odisha
        'northeast_india': 4.0  # Assam, other NE states
    }
    
    # Analysis Thresholds (Indian residential)
    MIN_ROOF_AREA_SQFT = 200  # Minimum roof area for solar
    MIN_PANELS_RECOMMENDED = 3  # Minimum panels for viable system
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
        """Get estimated daily sun hours based on Indian latitude"""
        lat_abs = abs(latitude)
        
        # Indian solar zones
        if lat_abs <= 15:
            return 5.5  # South India (Karnataka, Tamil Nadu, Kerala)
        elif lat_abs <= 20:
            return 5.3  # Central India (Maharashtra, Telangana)
        elif lat_abs <= 25:
            return 5.1  # North-Central (MP, Gujarat, Rajasthan)
        elif lat_abs <= 30:
            return 4.8  # North India (Delhi, UP, Haryana)
        else:
            return 4.5  # Far North (Himachal, J&K)
    
    @classmethod
    def get_electricity_rates_by_state(cls):
        """Average electricity rates by Indian states in ₹/kWh"""
        return {
            'MH': 7.2, 'GJ': 5.8, 'RJ': 6.1, 'KA': 6.8, 'TN': 5.5,
            'AP': 6.2, 'TS': 6.5, 'UP': 5.9, 'DL': 7.5, 'HR': 6.3,
            'PB': 6.1, 'WB': 6.8, 'OR': 5.2, 'JH': 5.4, 'MP': 6.0,
            'KL': 5.8, 'AS': 5.1, 'BR': 4.9, 'HP': 4.8, 'UK': 5.2
        }
    
    @classmethod
    def format_currency(cls, amount):
        """Format amount in Indian currency"""
        if amount >= 10000000:  # 1 crore or more
            return f"₹{amount/10000000:.1f} Cr"
        elif amount >= 100000:  # 1 lakh or more
            return f"₹{amount/100000:.1f} L"
        else:
            return f"₹{amount:,.0f}"

# Global configuration instance
config = SolarConfig()


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