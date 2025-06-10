import streamlit as st
import os
from dotenv import load_dotenv
from utils.image_fetch import fetch_satellite_image_complete, convert_image_for_streamlit
from utils.geocoding import get_coordinates_from_address
from components.ai_analyzer import analyze_roof_for_solar
from components.solar_calculator import calculate_solar_potential
from components.report_generator import generate_solar_report, SolarReportGenerator
from components.roof_visualizer import create_roof_visualization
from utils.config import config, validate_environment
import time
import json

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Solar Analysis",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean minimalist design
st.markdown("""
<style>
    .main > div {
        padding: 2rem 1rem;
        max-width: 1400px;
        margin: 0 auto;
    }
    
    .main-header {
        margin-bottom: 3rem;
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    
    .main-header p {
        font-size: 1.1rem;
        color: #6b7280;
        margin: 0;
    }

    
    .stButton > button {
        width: 100%;
        background: #3b82f6;
        color: white;
        border: none;
        padding: 0.875rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.2s;
        margin-top: 1rem;
    }
    
    .stButton > button:hover {
        background: #2563eb;
        transform: translateY(-1px);
    }
    
    .metric-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-card {
        flex: 1;
        background: #f8fafc;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1f2937;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    
    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 1rem;
    }
    
    .stRadio > div {
        display: flex;
        gap: 1rem;
    }
    
    .advanced-settings {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #e5e7eb;
    }
    
    [data-testid="stExpander"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        margin-top: 1rem;
    }
    
    .stProgress > div > div {
        background: #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Simple header
    st.markdown("""
    <div class="main-header">
        <h1>Solar Analysis</h1>
        <p>AI-powered solar potential analysis for your property</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API 
    validation = validate_environment()
    if validation['status'] != 'ready':
        st.error("⚠️ Please configure your Google Maps API key in the .env file")
        st.stop()
    
    # Input Section
    with st.container():
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1]) # 2 parts of space, 1 part of space
        
        with col1:
            st.markdown('<div class="section-title">Location</div>', unsafe_allow_html=True)
            input_method = st.radio("Input Method", ["Address", "Coordinates"], horizontal=True)
            
            if input_method == "Address":
                address = st.text_input(
                    "Enter Address",
                    placeholder="Enter your address (e.g., 123 Main St, City, State)"
                )
                coords_lat = coords_lng = None
            else:
                col_lat, col_lng = st.columns(2)
                with col_lat:
                    coords_lat = st.number_input("Latitude", value=19.0760, format="%.6f")
                with col_lng:
                    coords_lng = st.number_input("Longitude", value=72.8777, format="%.6f")
                address = None
        
        with col2:
            st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)
            zoom_level = st.slider("Image Zoom Level", 15, 21, 21)
        
        analyze_button = st.button("🚀 Analyze Solar Potential", type="primary")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Process analysis
    if analyze_button:
        with st.spinner("Analyzing your property..."):
            # Fetch satellite image with the correct zoom level
            if input_method == "Address" and address:
                result = fetch_satellite_image_complete(address=address, zoom=zoom_level)
            elif input_method == "Coordinates" and coords_lat is not None and coords_lng is not None:
                result = fetch_satellite_image_complete(lat=coords_lat, lng=coords_lng, zoom=zoom_level)
            else:
                st.error("Please provide location information")
                return
            
            if 'error' in result:
                st.error(f"Error: {result['error']}")
                return
            
            # AI Analysis
            ai_analysis = analyze_roof_for_solar(result['image_data'])
            
            if not ai_analysis.get('success', False):
                st.error(f"Analysis failed: {ai_analysis.get('error', 'Unknown error')}")
                return
            
            # Solar calculations
            panel_count = ai_analysis.get('estimated_panels', 0)
            solar_calculations = calculate_solar_potential(panel_count, result['coordinates']['lat'])
            
            # Generate report
            report = generate_solar_report(result, ai_analysis, solar_calculations)
            
            st.success("Analysis complete!")
            
            # Store in session state
            st.session_state.update({
                'satellite_result': result,
                'ai_analysis': ai_analysis,
                'solar_calculations': solar_calculations,
                'report': report
            })
    
    # Display Results
    if 'satellite_result' in st.session_state:
        result = st.session_state.satellite_result
        ai_analysis = st.session_state.ai_analysis
        solar_calculations = st.session_state.solar_calculations
        report = st.session_state.report
        
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        col_img, col_data = st.columns([1, 1])
        
        # Satellite Image
        with col_img:
            st.markdown('<div class="section-title">Satellite View</div>', unsafe_allow_html=True)
            streamlit_image = convert_image_for_streamlit(result['image_data'])
            
            if streamlit_image:
                st.image(
                    streamlit_image,
                    caption=result['formatted_address'],
                    use_container_width=True
                )
        
        # Analysis Results
        with col_data:
            st.markdown('<div class="section-title">Analysis Results</div>', unsafe_allow_html=True)
            
            # Key metrics
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.metric("Roof Area", f"{ai_analysis['suitable_area']:,.0f} sq ft")
            
            with col_b:
                st.metric("Solar Panels", f"{ai_analysis['estimated_panels']}")
            
            with col_c:
                st.metric("System Size", f"{solar_calculations['system_size_kw']:.1f} kW")
            
            # Energy & Financial metrics
            col_d, col_e = st.columns(2)
            
            with col_d:
                st.metric("Annual Energy", f"{solar_calculations['annual_kwh']:,.0f} kWh")
                st.metric("System Cost", solar_calculations.get('system_cost_formatted', f"₹{solar_calculations['system_cost']:,.0f}"))
            
            with col_e:
                st.metric("Monthly Average", f"{solar_calculations['monthly_kwh']:,.0f} kWh")
                st.metric("Annual Savings", solar_calculations.get('annual_savings_formatted', f"₹{solar_calculations['annual_savings']:,.0f}"))
        
        # Add Roof Visualization
        create_roof_visualization(result['image_data'], ai_analysis)
        
        # Solar Potential
        st.markdown('<div class="section-title">Solar Potential</div>', unsafe_allow_html=True)
        
        solar_potential = ai_analysis.get('solar_potential', 0)
        col_rating, col_bar = st.columns([1, 3])
        
        with col_rating:
            if solar_potential >= 80:
                st.success(f"Excellent ({solar_potential}%)")
            elif solar_potential >= 60:
                st.info(f"Good ({solar_potential}%)")
            else:
                st.warning(f"Fair ({solar_potential}%)")
        
        with col_bar:
            st.progress(solar_potential / 100)
        
        
        # Detailed Analysis - Fixed to show consistent values
        with st.expander("📊 Detailed Analysis"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Roof Analysis**")
                st.write(f"• Total roof area: {ai_analysis['total_roof_area']:,.0f} sq ft")
                st.write(f"• Suitable area: {ai_analysis['suitable_area']:,.0f} sq ft")
                st.write(f"• Roof angle: {ai_analysis['roof_angle']}°")
                st.write(f"• Confidence: {ai_analysis['confidence_score']*100:.0f}%")
            
            with col2:
                st.write("**System Details**")
                st.write(f"• Panel wattage: 330W each")
                st.write(f"• System efficiency: 80%")
                st.write(f"• Payback period: {solar_calculations['payback_years']:.1f} years")
                st.write(f"• 25-year ROI: {solar_calculations['roi_percentage']:.0f}%")
        
        # Download Reports
        st.markdown('<div class="section-title">Export Reports</div>', unsafe_allow_html=True)
        
        report_generator = SolarReportGenerator()
        report_summary = report_generator.create_summary_text(report)
        report_json = report_generator.export_report_json(report)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                "📄 Download Summary",
                data=report_summary,
                file_name=f"solar_analysis_{result['coordinates']['lat']:.4f}_{result['coordinates']['lng']:.4f}.txt",
                mime="text/plain"
            )
        
        with col2:
            st.download_button(
                "📊 Download JSON Report",
                data=report_json,
                file_name=f"solar_report_{result['coordinates']['lat']:.4f}_{result['coordinates']['lng']:.4f}.json",
                mime="application/json"
            )
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
