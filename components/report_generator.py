""" Report Generator for Solar Analysis Creates detailed reports and visualizations """
import json
from datetime import datetime
class SolarReportGenerator:
    def __init__(self):
        self.report_data = {}
    
    def generate_analysis_report(self, location_data, image_analysis, solar_calculations):
        """
        Generate comprehensive solar analysis report
        
        Args:
            location_data (dict): Location and address information
            image_analysis (dict): Results from AI roof analysis
            solar_calculations (dict): Solar potential calculations
            
        Returns:
            dict: Complete report data
        """
        report = {
            'report_id': f"solar_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'generated_at': datetime.now().isoformat(),
            'location': {
                'address': location_data.get('formatted_address', 'Unknown'),
                'coordinates': location_data.get('coordinates', {}),
                'lat': location_data.get('coordinates', {}).get('lat'),
                'lng': location_data.get('coordinates', {}).get('lng')
            },
            'roof_analysis': {
                'roof_detected': image_analysis.get('roof_detected', False),
                'total_roof_area': image_analysis.get('total_roof_area', 0),
                'suitable_area': image_analysis.get('suitable_area', 0),
                'estimated_panels': image_analysis.get('estimated_panels', 0),
                'obstacles_count': len(image_analysis.get('obstacles', [])),
                'roof_angle': image_analysis.get('roof_angle', 0),
                'confidence_score': image_analysis.get('confidence_score', 0)
            },
            'solar_potential': {
                'annual_generation': solar_calculations.get('annual_kwh', 0),
                'monthly_average': solar_calculations.get('monthly_kwh', 0),
                'system_size': solar_calculations.get('system_size_kw', 0),
                'efficiency_rating': image_analysis.get('solar_potential', 0)
            },
            'financial_analysis': {
                'estimated_cost': solar_calculations.get('system_cost', 0),
                'annual_savings': solar_calculations.get('annual_savings', 0),
                'payback_period': solar_calculations.get('payback_years', 0),
                'roi_percentage': solar_calculations.get('roi_percentage', 0)
            },
            'recommendation': image_analysis.get('recommendation', 'Analysis needed'),
            'next_steps': self._generate_recommendations(image_analysis, solar_calculations)
        }
        
        return report
    
    def _generate_recommendations(self, image_analysis, solar_calculations):
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        solar_potential = image_analysis.get('solar_potential', 0)
        
        if solar_potential >= 80:
            recommendations.extend([
                "Excellent solar potential - highly recommended for installation",
                "Contact local solar installers for detailed quotes",
                "Consider premium panel options for maximum efficiency"
            ])
        elif solar_potential >= 60:
            recommendations.extend([
                "Good solar potential - installation recommended",
                "Evaluate different panel configurations",
                "Consider energy storage options"
            ])
        elif solar_potential >= 40:
            recommendations.extend([
                "Moderate solar potential - feasible with proper planning",
                "Optimize panel placement to avoid obstacles",
                "Consider high-efficiency panels"
            ])
        else:
            recommendations.extend([
                "Limited solar potential - consider alternatives",
                "Evaluate roof modifications if possible",
                "Consider community solar programs"
            ])
        
        # Add financial recommendations
        payback_years = solar_calculations.get('payback_years', 0)
        if payback_years > 0 and payback_years <= 7:
            recommendations.append("Excellent financial returns expected")
        elif payback_years <= 12:
            recommendations.append("Good financial investment")
        
        return recommendations
    
    def create_summary_text(self, report):
        """Create a human-readable summary of the analysis"""
        location = report['location']['address']
        roof_area = report['roof_analysis']['suitable_area']
        panel_count = report['roof_analysis']['estimated_panels']
        annual_generation = report['solar_potential']['annual_generation']
        annual_savings = report['financial_analysis']['annual_savings']
        
        summary = f"""
            🏠 **Solar Analysis Summary for {location}**

            📏 **Roof Analysis:**
            • Suitable roof area: {roof_area:,.0f} sq ft
            • Estimated solar panels: {panel_count} panels
            • Solar potential rating: {report['roof_analysis']['confidence_score']*100:.0f}%

            ⚡ **Energy Production:**
            • Annual generation: {annual_generation:,.0f} kWh
            • Monthly average: {report['solar_potential']['monthly_average']:,.0f} kWh
            • System size: {report['solar_potential']['system_size']:.1f} kW

            💰 **Financial Analysis:**
            • Estimated system cost: ${report['financial_analysis']['estimated_cost']:,.0f}
            • Annual savings: ${annual_savings:,.0f}
            • Payback period: {report['financial_analysis']['payback_period']:.1f} years

            🎯 **Recommendation:** {report['recommendation']}
        """
        
        return summary.strip()
    
    def export_report_json(self, report):
        """Export report as JSON string"""
        return json.dumps(report, indent=2, default=str)

def generate_solar_report(location_data, image_analysis, solar_calculations):
    """
    Main function to generate comprehensive solar report
    """
    generator = SolarReportGenerator()
    report = generator.generate_analysis_report(location_data, image_analysis, solar_calculations)
    return report