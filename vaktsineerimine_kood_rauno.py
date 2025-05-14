import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
from shapely.ops import unary_union

# --- LAE ANDMED ---
vakts_df = pd.read_excel("andmestikud/vaktsineerimine.xlsx")
haigused_df = pd.read_excel("andmestikud/Haigused.xlsx")
maakond_gdf = gpd.read_file("andmestikud/maakond.json")
asustus_gdf = gpd.read_file("andmestikud/asustusyksus.json")
estonia_gdf = gpd.read_file("andmestikud/estonia.json")

# --- PUHASTUS ---
vakts_df.columns = vakts_df.columns.str.strip()
haigused_df.columns = haigused_df.columns.str.strip()
vakts_df["Maakond"] = vakts_df["Maakond"].str.strip()
haigused_df["Maakond"] = haigused_df["Maakond"].str.strip()
maakond_gdf["NIMI"] = maakond_gdf["MNIMI"].str.strip()
asustus_gdf["NIMI"] = asustus_gdf["ONIMI"].str.strip()

vakts_df["Aasta"] = pd.to_numeric(vakts_df["Aasta"], errors="coerce")
haigused_df["Aasta"] = pd.to_numeric(haigused_df["Aasta"], errors="coerce")

# --- LISA TALLINN, NARVA, EESTI KOKKU ---
extra_cities = asustus_gdf[asustus_gdf["NIMI"].isin(["Tallinn", "Narva linn"])]
estonia_center = estonia_gdf.geometry.centroid.iloc[0]
estonia_point = gpd.GeoDataFrame([{"NIMI": "Eesti kokku", "geometry": estonia_center}], crs="EPSG:4326")

combined_gdf = pd.concat(
    [maakond_gdf[["NIMI", "geometry"]],
     extra_cities[["NIMI", "geometry"]],
     estonia_point],
    ignore_index=True
)

# --- AASTAD JA HAIUSED ---
aastad = sorted(vakts_df["Aasta"].dropna().unique().astype(int))
haigused = sorted(set(vakts_df.columns) & set(haigused_df.columns) - {"Aasta", "Maakond"})

# --- KASUTAJA VALIKUD ---
valitud_aasta = st.sidebar.selectbox("🗓 Vali aasta", aastad)
valitud_haigus = st.sidebar.selectbox("🦠 Vali haigus", haigused)

# --- ANDMETE LIITMINE ---
vaktsineerimine = vakts_df.query("Aasta == @valitud_aasta")[["Maakond", valitud_haigus]].rename(columns={valitud_haigus: "Vaktsineerimine"})
haigestumus = haigused_df.query("Aasta == @valitud_aasta")[["Maakond", valitud_haigus]].rename(columns={valitud_haigus: "Haigestumus"})

geo_df = combined_gdf.merge(vaktsineerimine, left_on="NIMI", right_on="Maakond", how="left")
geo_df = geo_df.merge(haigestumus, left_on="NIMI", right_on="Maakond", how="left")

# --- INTERAKTIIVNE KAART ---
st.subheader(f"🗺 Klikitav maakonnakaart – {valitud_haigus} ({valitud_aasta})")
maakonnakaart = geo_df[geo_df["NIMI"] != "Eesti kokku"]

fig = px.choropleth_mapbox(
    maakonnakaart,
    geojson=maakonnakaart.geometry.__geo_interface__,
    locations=maakonnakaart.index,
    color="Vaktsineerimine",
    hover_name="NIMI",
    mapbox_style="carto-positron",
    center={"lat": 58.7, "lon": 25.3},
    zoom=5.5,
    opacity=0.65,
    color_continuous_scale="YlGnBu",
    custom_data=["NIMI"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

click = st.plotly_chart(fig, use_container_width=True)

# --- TUVASTA KLIKK JA UUENDA MAAKOND ---
click_json = st.session_state.get("last_click")
if click_json := st.experimental_get_query_params().get("maakond_click"):
    valitud_maakond = click_json[0]
elif click := st.session_state.get("plotly_click"):
    valitud_maakond = click["points"][0]["customdata"][0]
else:
    valitud_maakond = st.sidebar.selectbox("📍 Vali maakond", sorted(vakts_df["Maakond"].dropna().unique()))

# --- DETAILID ---
st.subheader(f"📍 {valitud_maakond} – detailne ülevaade")

if valitud_maakond != "Eesti kokku":
    col1, col2 = st.columns([1, 2])

    with col1:
        geom = combined_gdf[combined_gdf["NIMI"] == valitud_maakond]
        if not geom.empty:
            st.map(geom.set_geometry("geometry"))

    with col2:
        try:
            haigus = haigused_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")[valitud_haigus].values[0]
            vakts = vakts_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")[valitud_haigus].values[0]
            st.metric("Haigestunute arv", f"{int(haigus)}")
            st.metric("Vaktsineerimise määr (%)", f"{vakts}")
        except IndexError:
            st.write("Andmed puuduvad.")
else:
    try:
        haigus = haigused_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
        vakts = vakts_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
        col1, col2 = st.columns(2)
        col1.metric("Haigestunute arv", f"{int(haigus)}")
        col2.metric("Vaktsineerimise määr (%)", f"{vakts}")
    except IndexError:
        st.write("Andmed puuduvad.")

# --- GRAAFIK VAKTS. MÄÄRAST ---
st.subheader("📈 Vaktsineerimise määr (eelnevad 5 aastat)")

eelnevad = [a for a in aastad if a < valitud_aasta][-5:]
vakts_ajalugu = vakts_df[
    (vakts_df["Aasta"].isin(eelnevad)) & (vakts_df["Maakond"] == valitud_maakond)
][["Aasta", valitud_haigus]].rename(columns={valitud_haigus: "Vaktsineerimine"}).sort_values("Aasta")

if not vakts_ajalugu.empty:
    graaf = px.line(
        vakts_ajalugu,
        x="Aasta",
        y="Vaktsineerimine",
        markers=True,
        range_y=[0, 100],
        title="Vaktsineerimise määr (eelnevad 5 aastat)"
    )
    graaf.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(graaf, use_container_width=True)
else:
    st.info("Puuduvad andmed vaktsineerimise kohta viimase 5 aasta jooksul.")
