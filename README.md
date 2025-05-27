# Solar Analysis Tool

A comprehensive AI-powered solar potential analysis application that evaluates rooftop solar installation feasibility using satellite imagery and advanced calculations.

## Features

- **Address Geocoding**: Convert addresses to coordinates using Google Maps API
- **Satellite Image Analysis**: Fetch high-resolution satellite images for roof analysis
- **AI Roof Detection**: Automated roof area calculation and obstacle identification
- **Solar Potential Calculation**: Energy generation and financial analysis
- **Indian Market Focus**: Tailored for Indian solar market with INR pricing and regional considerations
- **Comprehensive Reporting**: Detailed analysis reports with recommendations

## Technology Stack

- **Framework**: Streamlit
- **Image Processing**: OpenCV, PIL
- **AI Analysis**: Computer Vision algorithms
- **APIs**: Google Maps Static API, Google Geocoding API
- **Data Visualization**: Matplotlib

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up environment variables:

```bash
GOOGLE_MAPS_API_KEY=your_api_key_here
```

3. Run the application:

```bash
streamlit run app.py
```

## Code Workflow

When a user enters an address, the application follows this workflow:

```
User Input (Address/Coordinates)
       ↓
1. app.py (Main Interface)
       ↓
2. utils/geocoding.py → get_coordinates_from_address()
       ↓
3. utils/image_fetch.py → fetch_satellite_image_complete()
       ↓
4. components/ai_analyzer.py → analyze_roof_for_solar()
       ↓
5. components/solar_calculator.py → calculate_solar_potential()
       ↓
6. components/report_generator.py → generate_solar_report()
       ↓
7. Display Results & Download Options
```

### Detailed Function Flow:

**Step 1: Input Processing**

- `app.py` receives user input (address or coordinates)
- Validates input method and parameters

**Step 2: Geocoding**

- `get_coordinates_from_address()` converts address to lat/lng
- Returns formatted address and coordinates

**Step 3: Image Acquisition**

- `fetch_satellite_image_complete()` calls Google Maps Static API
- Downloads high-resolution satellite image
- Returns image data and metadata

**Step 4: AI Analysis**

- `analyze_roof_for_solar()` processes satellite image
- `RoofAnalyzer` class detects roof area and obstacles
- Calculates suitable area for solar panels
- Estimates panel count and solar potential rating

**Step 5: Solar Calculations**

- `calculate_solar_potential()` performs energy and financial analysis
- `SolarCalculator` class computes:
  - System size (kW)
  - Annual energy generation (kWh)
  - System cost with Indian subsidies
  - Payback period and ROI

**Step 6: Report Generation**

- `generate_solar_report()` creates comprehensive analysis
- `SolarReportGenerator` formats results
- Generates downloadable reports (text and JSON)

**Step 7: Results Display**

- Streamlit interface shows satellite image
- Displays key metrics and financial analysis
- Provides recommendations and download options

## Configuration

The application uses Indian market standards:

- Panel wattage: 330W
- System efficiency: 80%
- Average sun hours: 5.0 hours/day
- Electricity rate: ₹6.50/kWh
- Cost per watt: ₹45/W
- Subsidies: 40% (up to 3kW), 20% (above 3kW)

## API Requirements

- **Google Maps API Key** with enabled services:
  - Static Maps API
  - Geocoding API

## Output

- Roof area analysis
- Solar panel count estimation
- Energy generation projections
- Financial analysis with Indian currency formatting
- Detailed recommendations
- Downloadable reports

## License

This project is for educational and commercial use in the solar industry.
