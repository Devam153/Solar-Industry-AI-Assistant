import streamlit as st
from components.ai_analyzer import analyze_roof_with_gemini
from components.solar_calculator import calculate_solar_roi
from utils.geocoding import get_coordinates

st.set_page_config(page_title="Solar AI Assistant", page_icon="🌞")

st.title("🌞 Solar Industry AI Assistant")
st.subheader("Powered by Gemini 2.0 Flash Vision")

# Step 1: Address Input
st.header("Step 1: Enter Property Address")
address = st.text_input("Enter the property address:")

if st.button("Start Solar Analysis") and address:
    # Create progress bar
    progress = st.progress(0)
    status = st.empty()
    
    # Step 2: Geocoding
    status.text("Step 2: Getting coordinates...")
    progress.progress(25)
    coordinates = get_coordinates(address)
    
    # Step 3: AI Analysis
    status.text("Step 3: AI analyzing satellite imagery...")
    progress.progress(50)
    ai_results = analyze_roof_with_gemini(coordinates)
    
    # Step 4: Solar Calculations
    status.text("Step 4: Calculating solar potential...")
    progress.progress(75)
    solar_data = calculate_solar_roi(ai_results)
    
    # Step 5: Display Results
    status.text("Analysis Complete!")
    progress.progress(100)
    
    # Show results
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Roof Area", f"{ai_results['roof_area']} sq ft")
        st.metric("Annual Savings", f"${solar_data['annual_savings']:,}")
    
    with col2:
        st.metric("Solar Potential", f"{solar_data['system_size']} kW")
        st.metric("Payback Period", f"{solar_data['payback_years']} years")
