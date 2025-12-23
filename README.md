# Dubai Schools Intelligence App

A powerful geospatial intelligence platform for exploring schools in Dubai with AI-powered chat, real-time proximity search, and road-aware drive-time analysis.

## Features

- 🗺️ **Interactive 3D Map** - Explore 234+ schools across Dubai
- 🤖 **AI Chat Assistant** - Ask questions about schools using Gemini AI
- 📍 **Real Isochrones** - Road-aware drive-time catchment areas (15/30/45/60 min)
- 🏘️ **Zone Intelligence** - Population and density insights for Dubai communities
- 🎯 **Smart Filters** - Filter by curriculum, rating, and proximity
- 📊 **Zone Details** - Click any zone to see population metrics

## Deployment

This app is deployed on Streamlit Community Cloud.

### Local Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   TRAVELTIME_APP_ID=your_app_id
   TRAVELTIME_API_KEY=your_api_key
   ```

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Tech Stack

- **Frontend**: Streamlit
- **Mapping**: Pydeck (WebGL)
- **AI**: Google Gemini 1.5 Pro / Ollama (fallback)
- **Geospatial**: TravelTime Platform API, Shapely
- **Data**: Pandas, Excel

## Data Sources

- Dubai school data (KHDA)
- Dubai population and zone demographics
- TravelTime road network data
