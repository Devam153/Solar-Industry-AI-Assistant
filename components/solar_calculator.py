"""
Solar Calculator with Gemini AI optimization for Indian market
regional optimization
"""

import google.generativeai as genai
import json
from utils.config import config

# Configure Gemini API
genai.configure(api_key=config.GEMINI_API_KEY)

class SolarCalculator:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def calculate_solar_potential(self, panel_count, latitude, location_data=None):
        """
        Calculate solar potential with AI optimization for Indian conditions
        """
        try:
            # Get AI-optimized parameters
            ai_params = self._get_ai_optimized_parameters(latitude, panel_count, location_data)
            
            # Base calculations
            system_size_kw = panel_count * config.STANDARD_PANEL_WATTAGE / 1000
            
            # Use AI-optimized sun hours and efficiency
            daily_sun_hours = ai_params.get('daily_sun_hours', config.get_regional_sun_hours(latitude))
            system_efficiency = ai_params.get('system_efficiency', config.SYSTEM_EFFICIENCY)
            
            # Energy calculations
            daily_kwh = system_size_kw * daily_sun_hours * system_efficiency
            annual_kwh = daily_kwh * 365
            monthly_kwh = annual_kwh / 12
            
            # Financial calculations with AI optimization
            electricity_rate = ai_params.get('electricity_rate', config.DEFAULT_ELECTRICITY_RATE)
            cost_per_watt = ai_params.get('cost_per_watt', config.COST_PER_WATT_INSTALLED)
            
            system_cost = system_size_kw * 1000 * cost_per_watt
            
            # Apply subsidies (AI can suggest state-specific rates)
            subsidy_rate = ai_params.get('subsidy_rate', config.CENTRAL_SUBSIDY)
            if system_size_kw <= 3:
                final_cost = system_cost * (1 - subsidy_rate)
            else:
                subsidized_portion = 3 * 1000 * cost_per_watt * subsidy_rate
                remaining_cost = (system_size_kw - 3) * 1000 * cost_per_watt * 0.8  # 20% subsidy above 3kW
                final_cost = system_cost - subsidized_portion - ((system_size_kw - 3) * 1000 * cost_per_watt * 0.2)
            
            # Savings and payback
            annual_savings = annual_kwh * electricity_rate
            payback_years = final_cost / annual_savings if annual_savings > 0 else 0
            
            # 25-year calculations
            total_25_year_savings = annual_savings * 25
            roi_percentage = ((total_25_year_savings - final_cost) / final_cost) * 100 if final_cost > 0 else 0
            
            return {
                'system_size_kw': system_size_kw,
                'daily_kwh': daily_kwh,
                'monthly_kwh': monthly_kwh,
                'annual_kwh': annual_kwh,
                'system_cost': final_cost,
                'system_cost_formatted': config.format_currency(final_cost),
                'annual_savings': annual_savings,
                'annual_savings_formatted': config.format_currency(annual_savings),
                'payback_years': payback_years,
                'roi_percentage': roi_percentage,
                'ai_optimized': True,
                'optimization_notes': ai_params.get('notes', '')
            }
            
        except Exception as e:
            return self._basic_calculation(panel_count, latitude)
    
    def _get_ai_optimized_parameters(self, latitude, panel_count, location_data):
        """
        Get AI-optimized parameters for the specific location
        """
        try:
            prompt = f"""
            Optimize solar calculation parameters for this Indian location:
            - Latitude: {latitude}
            - Panel count: {panel_count}
            - System size: {panel_count * 0.33:.1f} kW
            
            Consider:
            1. Regional solar irradiance patterns in India
            2. Local weather conditions and dust factors
            3. State-specific electricity rates and subsidies
            4. Seasonal variations and monsoon impact
            
            Provide optimized parameters in JSON format:
            {{
                "daily_sun_hours": optimized_hours_considering_weather,
                "system_efficiency": efficiency_with_dust_heat_factors,
                "electricity_rate": state_specific_rate_inr_per_kwh,
                "cost_per_watt": regional_installation_cost_inr,
                "subsidy_rate": applicable_subsidy_percentage,
                "notes": "brief explanation of optimizations"
            }}
            
            Be realistic for Indian conditions - account for dust, heat, monsoon, and regional variations.
            """
            response = self.model.generate_content(prompt)
            response_text = response.text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        
        except Exception as e:
            print(f"AI optimization failed: {str(e)}")
        
        # Return defaults if AI fails
        return {
            'daily_sun_hours': config.get_regional_sun_hours(latitude),
            'system_efficiency': config.SYSTEM_EFFICIENCY,
            'electricity_rate': config.DEFAULT_ELECTRICITY_RATE,
            'cost_per_watt': config.COST_PER_WATT_INSTALLED,
            'subsidy_rate': config.CENTRAL_SUBSIDY,
            'notes': 'Default parameters used'
        }
    
    def _basic_calculation(self, panel_count, latitude):
        system_size_kw = panel_count * config.STANDARD_PANEL_WATTAGE / 1000
        daily_sun_hours = config.get_regional_sun_hours(latitude)
        
        daily_kwh = system_size_kw * daily_sun_hours * config.SYSTEM_EFFICIENCY
        annual_kwh = daily_kwh * 365
        monthly_kwh = annual_kwh / 12
        
        system_cost = system_size_kw * 1000 * config.COST_PER_WATT_INSTALLED
        final_cost = system_cost * (1 - config.CENTRAL_SUBSIDY)
        
        annual_savings = annual_kwh * config.DEFAULT_ELECTRICITY_RATE
        payback_years = final_cost / annual_savings if annual_savings > 0 else 0
        
        total_25_year_savings = annual_savings * 25
        roi_percentage = ((total_25_year_savings - final_cost) / final_cost) * 100 if final_cost > 0 else 0
        
        return {
            'system_size_kw': system_size_kw,
            'daily_kwh': daily_kwh,
            'monthly_kwh': monthly_kwh,
            'annual_kwh': annual_kwh,
            'system_cost': final_cost,
            'system_cost_formatted': config.format_currency(final_cost),
            'annual_savings': annual_savings,
            'annual_savings_formatted': config.format_currency(annual_savings),
            'payback_years': payback_years,
            'roi_percentage': roi_percentage,
            'ai_optimized': False,
            'optimization_notes': 'Basic calculation without AI optimization'
        }

def calculate_solar_potential(panel_count, latitude, location_data=None):
    """
    Main function to calculate solar potential with AI optimization
    """
    calculator = SolarCalculator()
    return calculator.calculate_solar_potential(panel_count, latitude, location_data)