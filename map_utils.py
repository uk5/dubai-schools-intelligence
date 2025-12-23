import pydeck as pdk
import pandas as pd
import httpx
import os
import re
import streamlit as st
from shapely.wkt import loads as load_wkt

def parse_geom(wkt):
    """Parses WKT POLYGON Z into a list of [lon, lat] coordinates."""
    try:
        if pd.isna(wkt): return None
        # Basic parsing or using shapely
        poly = load_wkt(wkt)
        if poly.geom_type == 'Polygon':
            coords = list(poly.exterior.coords)
            return [[c[0], c[1]] for c in coords]
    except:
        return None

def get_centroid(wkt):
    """Calculates the [lon, lat] centroid of a WKT polygon."""
    try:
        poly = load_wkt(wkt)
        return [poly.centroid.x, poly.centroid.y]
    except:
        return None

def create_school_map(df_schools, df_zones=None, home_coords=None, drive_times=[15, 30], isochrones=None):
    """
    Renders a high-quality 3D map with schools, zones, and real drive-time isochrones.
    """
    layers = []
    
    # 1. Zone/Population Layer (Polygons)
    if df_zones is not None and not df_zones.empty:
        df_zones['coordinates'] = df_zones['geom'].apply(parse_geom)
        df_zones = df_zones.dropna(subset=['coordinates'])
        # Rename 'Community ' to 'community_name' for easier pydeck access
        df_zones['community_name'] = df_zones['Community '].astype(str)
        df_zones['datatype'] = 'zone'
        
        zone_layer = pdk.Layer(
            "PolygonLayer",
            df_zones,
            get_polygon="coordinates",
            get_fill_color="[0, 128, 255, 25]", # Very transparent blue
            get_line_color=[255, 255, 255, 30],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(zone_layer)

        # Zone Labels removed per user request - tooltips remain active

    # 2. Home Beacon / Centroid Marker
    if home_coords:
        home_df = pd.DataFrame([{"lat": home_coords[0], "lon": home_coords[1], "tooltip_html": ""}])
        home_layer = pdk.Layer(
            "ScatterplotLayer",
            home_df,
            get_position=["lon", "lat"],
            get_color=[255, 255, 255, 255], # Pure White Beacon
            get_radius=200,
            pickable=False
        )
        layers.append(home_layer)

    # 3. Real Isochrones (GeoJsonLayer)
    if isochrones:
        # Add empty tooltip_html to features to prevent template showing literals
        for feat in isochrones:
            if 'properties' not in feat: feat['properties'] = {}
            feat['properties']['tooltip_html'] = ""
            
        iso_layer = pdk.Layer(
            "GeoJsonLayer",
            isochrones,
            opacity=0.3,
            stroked=True,
            filled=True,
            get_fill_color="[properties.fill_color_r, properties.fill_color_g, properties.fill_color_b, 60]",
            get_line_color=[255, 255, 255],
            line_width_min_pixels=1,
            pickable=False # Don't trigger tooltips for isochrones
        )
        layers.append(iso_layer)
    elif home_coords:
        # Fallback simulated circles - also pickable=False
        isochrone_colors = [[0, 255, 128, 40], [255, 255, 0, 30], [255, 128, 0, 20]] 
        for i, dt in enumerate(sorted(drive_times, reverse=True)):
            radius = (dt / 2) * 1000 
            iso_layer = pdk.Layer(
                "ScatterplotLayer",
                pd.DataFrame([{"lat": home_coords[0], "lon": home_coords[1], "tooltip_html": ""}]),
                get_position=["lon", "lat"],
                get_color=isochrone_colors[i % len(isochrone_colors)],
                get_radius=radius,
                pickable=False
            )
            layers.append(iso_layer)

    # 4. School Layer (Scatterplot)
    if not df_schools.empty:
        df_schools = df_schools.dropna(subset=['Latitude', 'Longitude']).copy()
        df_schools['tooltip_html'] = df_schools.apply(
            lambda r: f"""
            <div style="font-family: 'Inter', sans-serif; padding: 12px;">
                <b style="color: #ff4500; font-size: 1.1em;">{r['name']}</b><br/>
                <hr style="margin: 5px 0; border: 0.5px solid rgba(255, 255, 255, 0.2);">
                <div style="font-size: 0.9em; color: white;">
                    <b>Rating:</b> {r['overall_rating']}<br/>
                    <b>Curriculum:</b> {r['curriculum']}<br/>
                    <b>Location:</b> {r['location']}
                </div>
            </div>
            """, axis=1
        )
        school_layer = pdk.Layer(
            "ScatterplotLayer",
            df_schools,
            get_position=["Longitude", "Latitude"],
            get_color=[255, 69, 0, 230],
            get_radius=180,
            pickable=True,
        )
        layers.append(school_layer)
    
    # Update Zone Layer to have tooltip_html
    if df_zones is not None and not df_zones.empty:
        df_zones['tooltip_html'] = df_zones.apply(
            lambda r: f"""
            <div style="font-family: 'Inter', sans-serif; padding: 12px;">
                <b style="color: #00bfff; font-size: 1.1em;">Zone: {r['community_name']}</b><br/>
                <hr style="margin: 5px 0; border: 0.5px solid rgba(0, 191, 255, 0.3);">
                <div style="font-size: 0.9em; color: white;">
                    <b>Population:</b> {r['Total population']}<br/>
                    <b>Density:</b> {r.get('Population Density (person/km2)', 'N/A')}/km²
                </div>
            </div>
            """, axis=1
        )
        # Re-create zone layer with pickable=True
        zone_layer = pdk.Layer(
            "PolygonLayer",
            df_zones,
            get_polygon="coordinates",
            get_fill_color="[0, 128, 255, 25]",
            get_line_color=[255, 255, 255, 30],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )
        # Replace the earlier zone layer if it exists
        if layers and layers[0].type == "PolygonLayer":
            layers[0] = zone_layer
    
    # Robust Tooltip Configuration
    tooltip = {
        "html": "{tooltip_html}",
        "style": {
            "backgroundColor": "rgba(10,10,10,0.95)",
            "color": "white",
            "border": "1px solid #ff4500",
            "borderRadius": "8px",
            "padding": "0px", # Padding handled by inner div
            "zIndex": 1000
        }
    }
    
    # View State
    center_lat = home_coords[0] if home_coords else (df_schools['Latitude'].mean() if not df_schools.empty else 25.2048)
    center_lon = home_coords[1] if home_coords else (df_schools['Longitude'].mean() if not df_schools.empty else 55.2708)
    
    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=11, pitch=40)
    
    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip=tooltip
    )

def get_isochrone(lat, lon, minutes=15, travel_mode="driving"):
    """
    Calculates drive-time catchment using TravelTime API.
    """
    # Try to get API keys from Streamlit secrets first (for cloud), then from .env (for local)
    app_id = None
    api_key = None
    
    # First try Streamlit secrets (cloud deployment)
    if hasattr(st, 'secrets'):
        try:
            app_id = st.secrets.get("TRAVELTIME_APP_ID")
            api_key = st.secrets.get("TRAVELTIME_API_KEY")
        except Exception as e:
            pass
    
    # Fallback to environment variables (local development)
    if not app_id:
        app_id = os.getenv("TRAVELTIME_APP_ID")
    if not api_key:
        api_key = os.getenv("TRAVELTIME_API_KEY")
    
    # If still no keys, show helpful error
    if not app_id or not api_key:
        st.error("⚠️ TravelTime API keys not configured. Add them in Streamlit Cloud Secrets.")
        return None
    
    # Use the correct endpoint: time-map instead of isochrones
    url = "https://api.traveltimeapp.com/v4/time-map"
    headers = {
        "X-Application-Id": str(app_id),
        "X-Api-Key": str(api_key),
        "Content-Type": "application/json"
    }
    
    from datetime import datetime, timedelta
    
    # Get current time + 1 hour in ISO format (API requirement)
    departure_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    data = {
        "departure_searches": [
            {
                "id": f"isochrone-{minutes}min",
                "coords": {"lat": lat, "lng": lon},
                "transportation": {"type": travel_mode},
                "departure_time": departure_time,
                "travel_time": minutes * 60
            }
        ]
    }
    
    try:
        response = httpx.post(url, headers=headers, json=data, timeout=10.0)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"TravelTime API Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        st.error(f"TravelTime Exception: {str(e)}")
        return None
