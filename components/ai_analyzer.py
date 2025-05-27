"""
AI Analyzer for Solar Roof Analysis
Handles roof detection and solar panel placement analysis
"""

import cv2
import numpy as np
from PIL import Image
import io
from utils.config import config

class RoofAnalyzer:
    def __init__(self):
        self.roof_detected = False
        self.roof_area = 0
        self.suitable_area = 0
        self.obstacles = []
    
    def analyze_satellite_image(self, image_data):
        """
        Analyze satellite image for roof detection and solar suitability
        
        Args:
            image_data (bytes): Raw image data from satellite
            
        Returns:
            dict: Analysis results including roof area, obstacles, etc.
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to OpenCV format for analysis
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Placeholder analysis - in production, this would use ML models
            analysis_results = self._perform_roof_analysis(cv_image)
            
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
                'error': f"Analysis failed: {str(e)}"
            }
    
    def _perform_roof_analysis(self, cv_image):
        """
        Perform actual roof analysis using computer vision
        Note: This is a simplified placeholder implementation for single Indian residential building
        """
        height, width = cv_image.shape[:2]
        
        # More realistic roof area for a SINGLE Indian residential building at zoom level 21
        # Typical Indian homes: 600-1500 sq ft built-up area
        estimated_building_area_sqft = np.random.uniform(600, 1200)  # Single building roof area
        suitable_area = estimated_building_area_sqft * np.random.uniform(0.65, 0.75)  # 65-75% suitable
        
        # Common obstacles in Indian homes (scaled for single building)
        obstacles = [
            {'type': 'water_tank', 'area': 80, 'position': (width//2, height//3)},
            {'type': 'staircase', 'area': 60, 'position': (width//3, height//2)},
            {'type': 'satellite_dish', 'area': 12, 'position': (width//4, height//4)},
            {'type': 'ac_unit', 'area': 20, 'position': (width//5, height//5)}
        ]
        
        return {
            'roof_detected': True,
            'total_area': estimated_building_area_sqft,
            'suitable_area': suitable_area,
            'obstacles': obstacles,
            'roof_angle': np.random.randint(5, 25),  # Flatter roofs common in India
            'solar_potential': np.random.randint(75, 85),  # Good potential for most of India
            'confidence': np.random.uniform(0.80, 0.90)
        }
    
    def estimate_panel_count(self, suitable_area, panel_size=16):
        """
        Estimate number of solar panels that can fit (Indian conditions)
        
        Args:
            suitable_area (float): Area suitable for panels in sq ft
            panel_size (float): Size of individual panel in sq ft (Indian standard)
            
        Returns:
            int: Estimated number of panels
        """
        if suitable_area <= 0:
            return 0
        
        # Account for spacing between panels and installation constraints
        usable_area = suitable_area * 0.75  # 75% utilization factor
        panel_count = int(usable_area / panel_size)
        
        # Cap at reasonable Indian residential limits for single building (5-20 panels)
        return min(panel_count, 20)

def analyze_roof_for_solar(image_data):
    """
    Main function to analyze roof for solar potential in Indian context
    
    Args:
        image_data (bytes): Satellite image data
        
    Returns:
        dict: Complete analysis results with Indian standards
    """
    analyzer = RoofAnalyzer()
    
    # Perform AI analysis
    analysis = analyzer.analyze_satellite_image(image_data)
    
    if analysis['success']:
        # Add panel count estimation
        panel_count = analyzer.estimate_panel_count(analysis['suitable_area'])
        analysis['estimated_panels'] = panel_count
        
        # Add recommendation based on Indian market conditions
        solar_potential = analysis['solar_potential']
        if solar_potential >= 80:
            analysis['recommendation'] = "Excellent solar potential - highly recommended for installation with government subsidies available"
        elif solar_potential >= 65:
            analysis['recommendation'] = "Good solar potential - installation recommended, check for state subsidies"
        elif solar_potential >= 50:
            analysis['recommendation'] = "Moderate solar potential - feasible with proper planning and net metering"
        else:
            analysis['recommendation'] = "Limited solar potential - consider rooftop optimization or community solar"
    
    return analysis