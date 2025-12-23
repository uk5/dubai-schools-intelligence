
import streamlit as st
import pandas as pd
from rag_engine import SchoolAgent
from map_utils import create_school_map, get_isochrone
import os
from dotenv import load_dotenv

load_dotenv()

# Page Config
st.set_page_config(page_title="Dubai School Explorer", layout="wide", initial_sidebar_state="expanded")

# Load CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Data Initialization
@st.cache_data
def load_data():
    master_path = r"F:\kaustubh_workings\Vision_2025\schools\dxb_schools_v0.1.xlsx"
    pops_path = r"F:\kaustubh_workings\Vision_2025\schools\dxb_pops_v0.1.xlsx"
    
    # Load Master Data
    df = pd.read_excel(master_path)
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Load Population/Zone Data
    df_zones = pd.read_excel(pops_path)
    
    return df, df_zones

df, df_zones = load_data()

# Agent Initialization
if "agent" not in st.session_state:
    st.session_state.agent = SchoolAgent(r"F:\kaustubh_workings\Vision_2025\schools\dxb_schools_v0.1.xlsx")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar - Hard Filters
st.sidebar.title("🔍 School Filters")

curriculum_list = sorted(df['curriculum'].dropna().unique())
selected_curriculum = st.sidebar.multiselect("Curriculum", curriculum_list)

rating_list = sorted(df['overall_rating'].dropna().unique())
selected_rating = st.sidebar.multiselect("Overall Rating", rating_list)

# Proximity Search Logic
st.sidebar.subheader("🚗 Proximity Search")

# 1. Searchable Zone Dropdown
zone_names = ["None"] + sorted(df_zones['Community '].astype(str).unique().tolist())
selected_zone_name = st.sidebar.selectbox("Select Zone (Searchable)", zone_names, index=0)

# Optional manual address search
manual_address = st.sidebar.text_input("OR Enter Home Location (Manual)", "")

selected_drive_times = st.sidebar.multiselect("Select Drive Tiers (mins)", [15, 30, 45, 60], default=[15, 30])

home_coords = None
filtered_df = df.copy()

# Logic to determine home_coords
if selected_zone_name != "None":
    from map_utils import get_centroid
    zone_match = df_zones[df_zones['Community '] == selected_zone_name]
    if not zone_match.empty:
        wkt = zone_match.iloc[0]['geom']
        home_coords_raw = get_centroid(wkt) # [lon, lat]
        if home_coords_raw:
            home_coords = [home_coords_raw[1], home_coords_raw[0]] # [lat, lon]
            st.sidebar.success(f"Located Zone: {selected_zone_name}")
elif manual_address:
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="dubai_schools_explorer")
    try:
        location = geolocator.geocode(manual_address + ", Dubai")
        if location:
            home_coords = [location.latitude, location.longitude]
            st.sidebar.success(f"Located: {location.address[:30]}...")
    except:
        st.sidebar.warning("Manual search failed.")

# Isochrone Fetching with Cache
@st.cache_data
def fetch_isochrones(lat, lon, drive_times):
    all_isochrones = []
    colors = [(0, 255, 128), (255, 255, 0), (255, 128, 0)]
    
    for i, dt in enumerate(sorted(drive_times, reverse=True)):
        iso_data = get_isochrone(lat, lon, minutes=dt)
        
        if iso_data and 'results' in iso_data and len(iso_data['results']) > 0:
            result = iso_data['results'][0]
            
            # time-map returns shapes at the result level
            if 'shapes' in result and len(result['shapes']) > 0:
                c = colors[i % len(colors)]
                geojson_shapes = []
                
                for shape in result['shapes']:
                    # shell is a list of {"lat":..., "lng":...}
                    shell = [[pt['lng'], pt['lat']] for pt in shape['shell']]
                    # Ensure shell is closed
                    if shell[0] != shell[-1]: 
                        shell.append(shell[0])
                    
                    holes = []
                    for hole in shape.get('holes', []):
                        h = [[pt['lng'], pt['lat']] for pt in hole]
                        if h[0] != h[-1]: 
                            h.append(h[0])
                        holes.append(h)
                    
                    geojson_shapes.append([shell] + holes)

                all_isochrones.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": geojson_shapes
                    },
                    "properties": {
                        "drive_time": dt,
                        "fill_color_r": c[0],
                        "fill_color_g": c[1],
                        "fill_color_b": c[2]
                    }
                })
            else:
                st.error(f"No shapes found in response for {dt} minutes")
        else:
            st.error(f"Failed to fetch isochrone for {dt} minutes")
            
    return all_isochrones

isochrone_polygons = None
if home_coords and selected_drive_times:
    with st.spinner("Calculating real-world isochrones..."):
        isochrone_polygons = fetch_isochrones(home_coords[0], home_coords[1], selected_drive_times)
        
        # Debug: Show what we got
        if isochrone_polygons:
            st.success(f"✅ Generated {len(isochrone_polygons)} real isochrone polygons")
        else:
            st.warning("⚠️ No isochrones generated - falling back to circles. Check API keys in .env file.")

# FINAL Filtering Logic: Combine all filters
if home_coords and selected_drive_times:
    from geopy.distance import geodesic
    max_minutes = max(selected_drive_times)
    # Estimate: 1km = 2 mins
    df['est_drive_time'] = df.apply(
        lambda row: geodesic((home_coords[0], home_coords[1]), (row['Latitude'], row['Longitude'])).km * 2
        if pd.notnull(row['Latitude']) else 999, axis=1
    )
    filtered_df = df[df['est_drive_time'] <= max_minutes].copy()
else:
    filtered_df = df.copy()

if selected_curriculum:
    filtered_df = filtered_df[filtered_df['curriculum'].isin(selected_curriculum)]
if selected_rating:
    filtered_df = filtered_df[filtered_df['overall_rating'].isin(selected_rating)]

# Main Layout
st.title("🏙️ Dubai Schools Intelligence")

# Zone Intelligence Card (Click/Select Detail)
if selected_zone_name != "None":
    zone_data = df_zones[df_zones['Community '] == selected_zone_name].iloc[0]
    with st.expander(f"📊 Zone Intelligence: {selected_zone_name}", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Population", f"{zone_data['Total population']:,}")
        c2.metric("Density", f"{zone_data.get('Population Density (person/km2)', 0):.1f}/km²")
        c3.metric("School Hits", len(filtered_df))
        st.info(f"Showing schools within driving distance of {selected_zone_name} centroid.")

col1, col2 = st.columns([2, 1])

with col1:
    # Map Visualization
    st.subheader("Interactive School Map")
    m = create_school_map(
        filtered_df, 
        df_zones=df_zones, 
        home_coords=home_coords, 
        drive_times=selected_drive_times,
        isochrones=isochrone_polygons
    )
    st.pydeck_chart(m)
    
    # Data Table
    st.subheader("Schools List")
    st.dataframe(filtered_df[['name', 'curriculum', 'overall_rating', 'location']].head(50), use_container_width=True)

with col2:
    # Chat Interface
    st.subheader("💬 AI Expert Chat")
    
    # Display chat history
    chat_container = st.container(height=500)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask me about schools in Dubai..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                # Use filtered data as context for the agent
                response = st.session_state.agent.ask(prompt, context_df=filtered_df.head(20))
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# Stats (Final positions)
st.sidebar.markdown("---")
st.sidebar.metric("Total Schools", len(df))
st.sidebar.metric("Filtered Hits", len(filtered_df))
