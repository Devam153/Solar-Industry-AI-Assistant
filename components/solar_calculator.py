"""
Solar Calculator for Energy and Financial Analysis
Calculates solar potential, energy generation, and cost savings
"""

from utils.config import config

class SolarCalculator:
    def __init__(self):
        # Indian residential solar specifications
        self.panel_wattage = 330  # Watts per panel (common in India)
        self.system_efficiency = 0.80  # Overall system efficiency (slightly lower due to dust/heat)
        self.avg_sun_hours = 5.0  # Average daily sun hours in India
        self.electricity_rate = 6.50  # ₹/kWh (average residential rate in India)
        self.cost_per_watt = 45  # ₹/W system cost (realistic for India)
        self.subsidies = 0.40  # 40% central + state subsidies (up to certain capacity)
        self.annual_degradation = 0.005  # 0.5% annual panel degradation
        self.max_subsidy_capacity = 3  # kW (typical subsidy limit for residential)
    
    def calculate_system_size(self, panel_count):
        """Calculate total system size in kW"""
        return (panel_count * self.panel_wattage) / 1000
    
    def calculate_annual_generation(self, system_size_kw, location_lat=None):
        """
        Calculate annual energy generation in kWh
        
        Args:
            system_size_kw (float): System size in kilowatts
            location_lat (float): Latitude for sun hours adjustment
            
        Returns:
            float: Annual kWh generation
        """
        # Adjust sun hours based on Indian regions if latitude provided
        sun_hours = self.avg_sun_hours
        if location_lat:
            sun_hours = self._adjust_sun_hours_for_india(location_lat)
        
        # Account for Indian conditions (dust, heat, monsoon)
        daily_generation = system_size_kw * sun_hours * self.system_efficiency
        annual_generation = daily_generation * 365
        
        return annual_generation
    
    def _adjust_sun_hours_for_india(self, latitude):
        """Adjust sun hours based on Indian regions"""
        return config.get_regional_sun_hours(latitude)
    
    def calculate_financial_metrics(self, system_size_kw, annual_generation):
        """
        Calculate financial metrics for solar installation in India
        
        Args:
            system_size_kw (float): System size in kW
            annual_generation (float): Annual kWh generation
            
        Returns:
            dict: Financial analysis results in INR with Indian formatting
        """
        # System cost calculations in INR
        gross_cost = system_size_kw * 1000 * self.cost_per_watt
        
        # Calculate subsidy (40% up to 3kW, 20% for remaining)
        subsidized_capacity = min(system_size_kw, self.max_subsidy_capacity)
        remaining_capacity = max(0, system_size_kw - self.max_subsidy_capacity)
        
        subsidy_amount = (subsidized_capacity * 1000 * self.cost_per_watt * 0.40) + \
                        (remaining_capacity * 1000 * self.cost_per_watt * 0.20)
        
        net_cost = gross_cost - subsidy_amount
        
        # Annual savings in INR
        annual_savings = annual_generation * self.electricity_rate
        
        # Payback period
        payback_years = net_cost / annual_savings if annual_savings > 0 else 0
        
        # 25-year lifetime value (accounting for degradation)
        lifetime_generation = 0
        for year in range(25):
            year_generation = annual_generation * ((1 - self.annual_degradation) ** year)
            lifetime_generation += year_generation
        
        lifetime_savings = lifetime_generation * self.electricity_rate
        net_savings = lifetime_savings - net_cost
        roi_percentage = (net_savings / net_cost * 100) if net_cost > 0 else 0
        
        # Format currency values using Indian number system - FULL NUMBERS ONLY
        def format_indian_currency(amount):
            """Format currency in Indian number system with proper commas - full numbers only"""
            # Convert to integer for formatting
            amount_int = int(amount)
            amount_str = str(amount_int)
            
            # Indian number system formatting
            if len(amount_str) <= 3:
                return f"₹{amount_str}"
            
            # Start from the right and add commas
            result = amount_str[-3:]  # Last 3 digits
            remaining = amount_str[:-3]
            
            # Add commas every 2 digits from right to left (Indian system)
            while len(remaining) > 2:
                result = remaining[-2:] + ',' + result
                remaining = remaining[:-2]
            
            # Add any remaining digits
            if remaining:
                result = remaining + ',' + result
            
            return f"₹{result}"
        
        return {
            'system_size_kw': system_size_kw,
            'gross_cost': gross_cost,
            'gross_cost_formatted': format_indian_currency(gross_cost),
            'subsidy_amount': subsidy_amount,
            'subsidy_amount_formatted': format_indian_currency(subsidy_amount),
            'system_cost': net_cost,
            'system_cost_formatted': format_indian_currency(net_cost),
            'annual_kwh': annual_generation,
            'monthly_kwh': annual_generation / 12,
            'annual_savings': annual_savings,
            'annual_savings_formatted': format_indian_currency(annual_savings),
            'payback_years': payback_years,
            'lifetime_savings': lifetime_savings,
            'lifetime_savings_formatted': format_indian_currency(lifetime_savings),
            'net_savings': net_savings,
            'net_savings_formatted': format_indian_currency(net_savings),
            'roi_percentage': roi_percentage,
            'currency': 'INR',
            'currency_symbol': '₹'
        }
    
    def calculate_complete_analysis(self, panel_count, location_lat=None):
        """
        Perform complete solar analysis for Indian market
        
        Args:
            panel_count (int): Number of solar panels
            location_lat (float): Latitude for location-specific calculations
            
        Returns:
            dict: Complete solar analysis with Indian currency formatting
        """
        if panel_count <= 0:
            return {
                'error': 'Invalid panel count',
                'system_size_kw': 0,
                'annual_kwh': 0,
                'system_cost': 0,
                'system_cost_formatted': '₹0',
                'annual_savings': 0,
                'annual_savings_formatted': '₹0',
                'payback_years': 0,
                'currency': 'INR'
            }
        
        # Cap at realistic residential limits for India (typically 3-10kW)
        max_panels = 30  # ~10kW system
        panel_count = min(panel_count, max_panels)
        
        # Calculate system size
        system_size = self.calculate_system_size(panel_count)
        
        # Calculate energy generation
        annual_generation = self.calculate_annual_generation(system_size, location_lat)
        
        # Calculate financial metrics
        financial_metrics = self.calculate_financial_metrics(system_size, annual_generation)
        
        return financial_metrics
    
    def get_system_recommendations(self, roof_area, budget=None):
        """
        Recommend optimal system size based on roof area and budget for Indian homes
        """
        # Estimate max panels based on roof area (16 sq ft per panel for Indian conditions)
        max_panels = min(int(roof_area / 16), 30)  # Cap at 30 panels (~10kW)
        
        # Calculate for different system sizes suitable for Indian homes
        recommendations = []
        
        for size_factor in [0.3, 0.6, 1.0]:  # Smaller increments for Indian market
            panel_count = max(1, int(max_panels * size_factor))
            if panel_count > 0:
                analysis = self.calculate_complete_analysis(panel_count)
                
                recommendations.append({
                    'size': f"{size_factor*100:.0f}% of roof",
                    'panel_count': panel_count,
                    'analysis': analysis,
                    'within_budget': budget is None or analysis['system_cost'] <= budget
                })
        
        return {
            'max_panels': max_panels,
            'recommendations': recommendations
        }

def calculate_solar_potential(panel_count, location_lat=None):
    """
    Main function to calculate solar potential for Indian market
    
    Args:
        panel_count (int): Number of solar panels
        location_lat (float): Latitude for location-specific calculations
        
    Returns:
        dict: Complete solar analysis in Indian context
    """
    calculator = SolarCalculator()
    return calculator.calculate_complete_analysis(panel_count, location_lat)