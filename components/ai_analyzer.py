"""
Solar Roof Analysis using Google Gemini
Handles roof detection and solar panel placement analysis
"""
from PIL import Image
import io
import google.generativeai as genai
import json
from utils.config import config

# Configure Gemini API
genai.configure(api_key=config.GEMINI_API_KEY)

class RoofAnalyzer:
    def __init__(self):
        self.roof_detected = False
        self.roof_area = 0
        self.suitable_area = 0
        self.obstacles = []
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    def perform_gemini_roof_analysis(self, image):
        """
        Perform roof analysis using Gemini Vision AI
        """
        prompt = """
        Analyze this satellite image of an Indian residential building for solar panel installation potential. 
        
        Please examine:
        1. Roof area and structure (flat/sloped)
        2. Obstacles like water tanks, AC units, satellite dishes, staircase access
        3. Suitable area for solar panels (excluding obstacles and margins)
        4. Roof orientation and potential shading
        5. Overall solar installation feasibility
        
        Provide your analysis in the following JSON format:
        {
            "roof_detected": true/false,
            "total_area": estimated_roof_area_in_sqft,
            "suitable_area": usable_area_for_panels_in_sqft,
            "obstacles": [
                {"type": "water_tank", "area": area_in_sqft, "impact": "high/medium/low"},
                {"type": "ac_unit", "area": area_in_sqft, "impact": "medium"},
                {"type": "staircase", "area": area_in_sqft, "impact": "high"}
            ],
            "roof_angle": estimated_angle_in_degrees,
            "solar_potential": percentage_0_to_100,
            "confidence": confidence_score_0_to_1,
            "analysis_notes": "detailed observations about the roof"
        }
        
        Focus on Indian residential building characteristics. Be realistic about area estimates for typical Indian homes (600-1500 sq ft roof area).
        """
        
        response = self.model.generate_content([prompt, image])
        
        # Extract JSON from response
        response_text = response.text
        
        # Find JSON in the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            json_str = response_text[start_idx:end_idx]
            analysis_data = json.loads(json_str)
            
            # Validate and set defaults if needed
            return {
                'roof_detected': analysis_data.get('roof_detected', True),
                'total_area': float(analysis_data.get('total_area', 800)),
                'suitable_area': float(analysis_data.get('suitable_area', 600)),
                'obstacles': analysis_data.get('obstacles', []),
                'roof_angle': int(analysis_data.get('roof_angle', 15)),
                'solar_potential': int(analysis_data.get('solar_potential', 75)),
                'confidence': float(analysis_data.get('confidence', 0.85)),
                'analysis_notes': analysis_data.get('analysis_notes', '')
            }
        
    def analyze_satellite_image(self, image_data):
        """
        Analyze satellite image for roof detection and solar suitability using Gemini AI
        
        Args:
            image_data (bytes): Raw image data from satellite
            
        Returns:
            dict: Analysis results including roof area, obstacles, etc.
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Use Gemini for AI-powered roof analysis
            analysis_results = self.perform_gemini_roof_analysis(image)
            
            return {
                'success': True,
                'roof_detected': analysis_results['roof_detected'],
                'total_roof_area': analysis_results['total_area'],
                'suitable_area': analysis_results['suitable_area'],
                'obstacles': analysis_results['obstacles'],
                'roof_angle': analysis_results['roof_angle'],
                'solar_potential': analysis_results['solar_potential'],
                'confidence_score': analysis_results['confidence']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Gemini AI analysis failed: {str(e)}"
            }

    def estimate_panel_count(self, suitable_area, panel_size=20):
        """
        Estimate number of solar panels that can fit
        
        Args:
            suitable_area (float): Area suitable for panels in sq ft
            panel_size (float): Size of individual panel in sq ft (Indian standard)
            
        Returns:
            int: Estimated number of panels
        """
        if suitable_area <= 0:
            return 0
        
        # Account for spacing between panels and installation constraints
        usable_area = suitable_area * 0.60  # 60% utilization factor
        panel_count = int(usable_area / panel_size)
        
        # Cap at reasonable Indian residential limits for single building (5-20 panels)
        return min(panel_count, 20)
    
    def generate_ai_recommendation(self, analysis_results, panel_count):
        """
        Generate AI-powered recommendations using Gemini
        """
        try:
            prompt = f"""
            Based on this solar roof analysis for an Indian residential building:
            - Roof area: {analysis_results['total_roof_area']:.0f} sq ft
            - Suitable area: {analysis_results['suitable_area']:.0f} sq ft
            - Solar potential: {analysis_results['solar_potential']}%
            - Estimated panels: {panel_count}
            - Obstacles found: {len(analysis_results['obstacles'])} items
            
            Provide a professional recommendation for solar installation in 2-3 sentences, 
            considering Indian market conditions, subsidies, and payback period.
            """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            # Fallback recommendation
            solar_potential = analysis_results['solar_potential']
            if solar_potential >= 75:
                return "Excellent solar potential"
            elif solar_potential >= 60:
                return "Good solar potential"
            elif solar_potential >= 50:
                return "Moderate solar potential"
            else:
                return "Limited solar potential"

def analyze_roof_for_solar(image_data):
    """
    Main function to analyze roof for solar potential using Gemini AI
    
    Args:
        image_data (bytes): Satellite image data
        
    Returns:
        dict: Complete analysis results with AI-powered insights
    """
    analyzer = RoofAnalyzer()
    analysis = analyzer.analyze_satellite_image(image_data)
    
    if analysis['success']:
        panel_count = analyzer.estimate_panel_count(analysis['suitable_area'])
        analysis['estimated_panels'] = panel_count
        

        analysis['recommendation'] = analyzer.generate_ai_recommendation(analysis, panel_count)
    
    return analysis