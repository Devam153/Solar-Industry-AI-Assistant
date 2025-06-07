"""
Roof Area Visualizer
Interactive drawing component to show detected roof area on satellite image
"""

import streamlit as st
import numpy as np
from PIL import Image, ImageDraw
import io
import json
import google.generativeai as genai
from utils.config import config

# Configure Gemini API
genai.configure(api_key=config.GEMINI_API_KEY)

class RoofVisualizer:
    def __init__(self):
        self.outline_color = (255, 0, 0, 255)  # Red outline
        self.suitable_color = (0, 255, 0, 180)  # Green fill
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def get_ai_roof_boundaries(self, image, suitable_area_sqft, total_area_sqft):
        """
        Use Gemini AI to get precise roof boundary coordinates for tracing
        """
        prompt = f"""
        Analyze this satellite/aerial image and trace the EXACT roof boundaries of the main building.
        
        I need you to provide detailed coordinate points that trace the perimeter of the roof edges.
        Don't give me rectangles - I need the actual roof outline following the building's shape.
        
        For the building in this image:
        - Total roof area: {total_area_sqft:.0f} sq ft
        - Suitable solar area: {suitable_area_sqft:.0f} sq ft
        
        provide:
        1. "roof_outline": Array of [x,y] coordinates that trace the outer roof perimeter
        2. "suitable_outline": Array of [x,y] coordinates for the inner suitable area (avoiding obstacles like HVAC, chimneys, edges)
        
        Make the coordinates follow the actual roof shape visible in the image.
        Use many coordinate points (10-20 points minimum) to create smooth, accurate outlines.
        
        Return in this JSON format:
        {{
            "image_width": {image.width},
            "image_height": {image.height},
            "roof_outline": [
                [x1, y1], [x2, y2], [x3, y3], ..., [xN, yN]
            ],
            "suitable_outline": [
                [x1, y1], [x2, y2], [x3, y3], ..., [xN, yN]
            ]
        }}
        
        Coordinates must be within bounds: x (0-{image.width}), y (0-{image.height}).
        Focus on the main building structure and trace its actual roof edges carefully.
        """
        
        try:
            response = self.model.generate_content([prompt, image])
            response_text = response.text
            
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                boundary_data = json.loads(json_str)
                return boundary_data
            else:
                return None
                
        except Exception as e:
            print(f"AI boundary detection error: {str(e)}")
            return None
    
    def create_roof_overlay(self, image_data, suitable_area_sqft, total_area_sqft):
        """
        Create an overlay showing AI-traced roof outlines
        """
        try:
            # Convert to PIL Image
            original_image = Image.open(io.BytesIO(image_data))
            
            # Get AI-powered roof boundaries
            ai_boundaries = self.get_ai_roof_boundaries(
                original_image, 
                suitable_area_sqft, 
                total_area_sqft
            )
            
            # Create overlay with traced outlines
            if ai_boundaries:
                overlay_image = self._draw_traced_roof_outlines(
                    original_image, 
                    ai_boundaries,
                    suitable_area_sqft, 
                    total_area_sqft
                )
            else:
                # Fallback to simple outline if AI fails
                overlay_image = self._draw_simple_outline(
                    original_image,
                    suitable_area_sqft,
                    total_area_sqft
                )
            
            return overlay_image
            
        except Exception as e:
            st.error(f"Error creating roof overlay: {str(e)}")
            return Image.open(io.BytesIO(image_data))
    
    def _draw_traced_roof_outlines(self, image, ai_boundaries, suitable_area, total_area):
        """
        Draw roof outlines using AI-traced boundaries
        """
        # Create a copy for drawing
        overlay = image.copy().convert("RGBA")
        draw = ImageDraw.Draw(overlay)
        
        
        # Extract boundary coordinates
        roof_outline = ai_boundaries.get('roof_outline', [])
        suitable_outline = ai_boundaries.get('suitable_outline', [])
        
        # Validate and clean coordinates
        roof_points = self._validate_coordinates(roof_outline, image.width, image.height)
        suitable_points = self._validate_coordinates(suitable_outline, image.width, image.height)
        
        # Draw total roof outline (red dotted line)
        if len(roof_points) >= 3:
            self._draw_dotted_outline(draw, roof_points, (255, 0, 0, 255), width=3)
        
        # Draw suitable area (green fill with outline)
        if len(suitable_points) >= 3:
            # Fill suitable area
            draw.polygon(suitable_points, fill=(0, 255, 0, 60), outline=None)
            # Outline suitable area
            self._draw_dotted_outline(draw, suitable_points, (0, 255, 0, 255), width=2)
        
        # Add text labels
        self._add_text_labels(draw, suitable_area, total_area, "AI-Traced")
            
        '''except Exception as e:
            print(f"Error drawing traced boundaries: {str(e)}")
            return self._draw_simple_outline(image, suitable_area, total_area)'''
        
        return overlay
    
    def _draw_dotted_outline(self, draw, points, color, width=2, dash_length=5):
        """
        Draw a dotted outline connecting the points
        """
        if len(points) < 2:
            return
            
        # Close the polygon by adding first point at the end
        closed_points = points + [points[0]]
        
        for i in range(len(closed_points) - 1):
            x1, y1 = closed_points[i]
            x2, y2 = closed_points[i + 1]
            
            # Calculate line length and direction
            dx = x2 - x1
            dy = y2 - y1
            line_length = (dx*dx + dy*dy)**0.5
            
            if line_length == 0:
                continue
                
            # Unit direction vector
            ux = dx / line_length
            uy = dy / line_length
            
            # Draw dashed line
            current_pos = 0
            while current_pos < line_length:
                # Start of dash
                start_x = x1 + ux * current_pos
                start_y = y1 + uy * current_pos
                
                # End of dash
                end_pos = min(current_pos + dash_length, line_length)
                end_x = x1 + ux * end_pos
                end_y = y1 + uy * end_pos
                
                # Draw the dash
                draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
                
                # Move to next dash (skip gap)
                current_pos += dash_length * 2
    
    def _validate_coordinates(self, coordinates, max_width, max_height):
        """
        Validate and clean coordinate points
        """
        valid_points = []
        for coord in coordinates:
            if len(coord) >= 2:
                x = max(0, min(int(coord[0]), max_width - 1))
                y = max(0, min(int(coord[1]), max_height - 1))
                valid_points.append((x, y))
        return valid_points
    
    '''def _draw_simple_outline(self, image, suitable_area, total_area):
        """
        Fallback outline when AI detection fails
        """
        overlay = image.copy().convert("RGBA")
        draw = ImageDraw.Draw(overlay)
        
        width, height = image.size
        
        # Create building outline (center 70% of image with some shape)
        margin_x = int(width * 0.15)

        margin_y = int(height * 0.15)
        
        # Create a more realistic building outline
        roof_points = [
            (margin_x, margin_y + int(height * 0.1)),
            (margin_x + int(width * 0.2), margin_y),
            (width - margin_x - int(width * 0.1), margin_y),
            (width - margin_x, margin_y + int(height * 0.15)),
            (width - margin_x, height - margin_y),
            (margin_x, height - margin_y)
        ]
        
        # Draw roof outline (red dotted)
        self._draw_dotted_outline(draw, roof_points, (255, 0, 0, 255), width=3)
        
        # Suitable area (smaller inner outline)
        suitable_ratio = suitable_area / total_area if total_area > 0 else 0.7
        inner_margin = int(min(width, height) * (1 - suitable_ratio) * 0.1)
        
        suitable_points = [
            (margin_x + inner_margin, margin_y + int(height * 0.1) + inner_margin),
            (margin_x + int(width * 0.2) + inner_margin, margin_y + inner_margin),
            (width - margin_x - int(width * 0.1) - inner_margin, margin_y + inner_margin),
            (width - margin_x - inner_margin, margin_y + int(height * 0.15) + inner_margin),
            (width - margin_x - inner_margin, height - margin_y - inner_margin),
            (margin_x + inner_margin, height - margin_y - inner_margin)
        ]
        
        # Fill and outline suitable area
        draw.polygon(suitable_points, fill=(0, 255, 0, 60), outline=None)
        self._draw_dotted_outline(draw, suitable_points, (0, 255, 0, 255), width=2)
        
        # Add text labels
        self._add_text_labels(draw, suitable_area, total_area, "Estimated")
        
        return overlay'''
    
    def _add_text_labels(self, draw, suitable_area, total_area, detection_method="AI-Traced"):
        """
        Add text labels with background
        """
        draw.rectangle([5, 5, 320, 70], fill=(0, 0, 0, 180))
        draw.text((10, 10), f"Total Roof: {total_area:.0f} sq ft", fill=(255, 255, 255, 255))
        draw.text((10, 30), f"Suitable: {suitable_area:.0f} sq ft", fill=(255, 255, 255, 255))
    
    def display_roof_visualization(self, image_data, ai_analysis):
        """
        Display the roof area visualization in Streamlit
        """        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Original image
            st.subheader("Original Satellite View")
            original_image = Image.open(io.BytesIO(image_data))
            st.image(original_image, use_container_width=True)
        
        with col2:
            # AI-traced overlay image
            st.subheader("Traced Roof Boundaries")
            overlay_image = self.create_roof_overlay(
                image_data,
                ai_analysis.get('suitable_area', 0),
                ai_analysis.get('total_roof_area', 0)
            )
            st.image(overlay_image, use_container_width=True)
            
            # Legend
            st.markdown("""
            **Legend:**
            - 🔴 Red dotted line: Total roof boundary traced
            - 🟩 Green area: Suitable for solar panels
            """)
            
            # Area breakdown
            st.markdown("**Area Breakdown:**")
            total_area = ai_analysis.get('total_roof_area', 0)
            suitable_area = ai_analysis.get('suitable_area', 0)
            obstacle_area = total_area - suitable_area
            
            st.write(f"• Total roof: {total_area:.0f} sq ft")
            st.write(f"• Suitable area: {suitable_area:.0f} sq ft") 
            st.write(f"• Obstacles/margins: {obstacle_area:.0f} sq ft")
            st.write(f"• Utilization: {(suitable_area/total_area*100):.0f}%" if total_area > 0 else "• Utilization: 0%")

def create_roof_visualization(image_data, ai_analysis):
    """
    Main function to create and display AI-powered roof visualization
    """
    visualizer = RoofVisualizer()
    visualizer.display_roof_visualization(image_data, ai_analysis)