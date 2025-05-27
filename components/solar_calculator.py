
"""
Solar Calculator for Energy and Financial Analysis
Calculates solar potential, energy generation, and cost savings
"""

class SolarCalculator:
    def __init__(self):
        # Standard assumptions - can be made configurable
        self.panel_wattage = 400  # Watts per panel
        self.system_efficiency = 0.85  # Overall system efficiency
        self.avg_sun_hours = 5.5  # Average daily sun hours
        self.electricity_rate = 0.12  # $/kWh
        self.cost_per_watt = 3.50  # System cost per watt installed
        self.federal_tax_credit = 0.30  # 30% federal tax credit
        self.annual_degradation = 0.005  # 0.5% annual panel degradation
    
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
        # Adjust sun hours based on latitude if provided
        sun_hours = self.avg_sun_hours
        if location_lat:
            sun_hours = self._adjust_sun_hours_by_latitude(location_lat)
        
        daily_generation = system_size_kw * sun_hours * self.system_efficiency
        annual_generation = daily_generation * 365
        
        return annual_generation
    
    def _adjust_sun_hours_by_latitude(self, latitude):
        """Adjust sun hours based on latitude"""
        # Simplified adjustment - in production, use detailed solar irradiance data
        lat_abs = abs(latitude)
        
        if lat_abs <= 30:
            return 6.0  # Tropical regions
        elif lat_abs <= 40:
            return 5.5  # Temperate regions
        elif lat_abs <= 50:
            return 4.8  # Northern temperate
        else:
            return 4.0  # High latitude regions
    
    def calculate_financial_metrics(self, system_size_kw, annual_generation):
        """
        Calculate financial metrics for solar installation
        
        Args:
            system_size_kw (float): System size in kW
            annual_generation (float): Annual kWh generation
            
        Returns:
            dict: Financial analysis results
        """
        # System cost calculations
        gross_cost = system_size_kw * 1000 * self.cost_per_watt
        tax_credit_amount = gross_cost * self.federal_tax_credit
        net_cost = gross_cost - tax_credit_amount
        
        # Annual savings
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
        
        return {
            'system_size_kw': system_size_kw,
            'gross_cost': gross_cost,
            'tax_credit_amount': tax_credit_amount,
            'system_cost': net_cost,
            'annual_kwh': annual_generation,
            'monthly_kwh': annual_generation / 12,
            'annual_savings': annual_savings,
            'payback_years': payback_years,
            'lifetime_savings': lifetime_savings,
            'net_savings': net_savings,
            'roi_percentage': roi_percentage
        }
    
    def calculate_complete_analysis(self, panel_count, location_lat=None):
        """
        Perform complete solar analysis
        
        Args:
            panel_count (int): Number of solar panels
            location_lat (float): Latitude for location-specific calculations
            
        Returns:
            dict: Complete solar analysis
        """
        if panel_count <= 0:
            return {
                'error': 'Invalid panel count',
                'system_size_kw': 0,
                'annual_kwh': 0,
                'system_cost': 0,
                'annual_savings': 0,
                'payback_years': 0
            }
        
        # Calculate system size
        system_size = self.calculate_system_size(panel_count)
        
        # Calculate energy generation
        annual_generation = self.calculate_annual_generation(system_size, location_lat)
        
        # Calculate financial metrics
        financial_metrics = self.calculate_financial_metrics(system_size, annual_generation)
        
        return financial_metrics
    
    def get_system_recommendations(self, roof_area, budget=None):
        """
        Recommend optimal system size based on roof area and budget
        
        Args:
            roof_area (float): Available roof area in sq ft
            budget (float): Optional budget constraint
            
        Returns:
            dict: System recommendations
        """
        # Estimate max panels based on roof area (17.6 sq ft per panel)
        max_panels = int(roof_area / 17.6)
        
        # Calculate for different system sizes
        recommendations = []
        
        for size_factor in [0.5, 0.75, 1.0]:
            panel_count = int(max_panels * size_factor)
            if panel_count > 0:
                analysis = self.calculate_complete_analysis(panel_count)
                
                if budget and analysis['system_cost'] <= budget:
                    recommendations.append({
                        'size': f"{size_factor*100:.0f}% of roof",
                        'panel_count': panel_count,
                        'analysis': analysis,
                        'within_budget': True
                    })
                else:
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
    Main function to calculate solar potential for given parameters
    
    Args:
        panel_count (int): Number of solar panels
        location_lat (float): Latitude for location-specific calculations
        
    Returns:
        dict: Complete solar analysis
    """
    calculator = SolarCalculator()
    return calculator.calculate_complete_analysis(panel_count, location_lat)
