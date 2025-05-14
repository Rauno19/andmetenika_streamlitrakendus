import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import plotly.express as px

from shapely.ops import unary_union

st.set_page_config(layout="wide")
st.title("💉 Vaktsineerimine ja haigestumus maakonniti")

# --- LAE ANDMED ---
vakts_df = pd.read_excel("vaktsineerimine.xlsx")
haigused_df = pd.read_excel("Haigused.xlsx")
maakond_gdf = gpd.read_file("maakond.json")
asustus_gdf = gpd.read_file("asustusyksus.json")
estonia_gdf = gpd.read_file("estonia.json")

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
estonia_point = gpd.GeoDataFrame(
    [{"NIMI": "Eesti kokku", "geometry": estonia_center}],
    crs="EPSG:4326"
)

combined_gdf = pd.concat(
    [maakond_gdf[["NIMI", "geometry"]], extra_cities[["NIMI", "geometry"]], estonia_point],
    ignore_index=True
)

# --- KASUTAJA VALIKUD ---
aastad = sorted(vakts_df["Aasta"].dropna().unique().astype(int))
haigused = sorted(set(vakts_df.columns) & set(haigused_df.columns) - {"Aasta", "Maakond"})
kõik_maakonnad = sorted(vakts_df["Maakond"].dropna().unique())

st.sidebar.header("🎛️ Valikud")
valitud_aasta = st.sidebar.selectbox("🗓 Vali aasta", aastad)
valitud_haigus = st.sidebar.selectbox("🦠 Vali haigus", haigused)
valitud_maakond = st.sidebar.selectbox("📍 Vali maakond", ["Eesti kokku"] + kõik_maakonnad)

# --- FILTERDA ANDMED ---
vaktsineerimine = vakts_df.query("Aasta == @valitud_aasta")[["Maakond", valitud_haigus]]
vaktsineerimine = vaktsineerimine.rename(columns={valitud_haigus: "Vaktsineerimine"})
haigestumus = haigused_df.query("Aasta == @valitud_aasta")[["Maakond", valitud_haigus]]
haigestumus = haigestumus.rename(columns={valitud_haigus: "Haigestumus"})

geo_df = combined_gdf[combined_gdf["NIMI"] != "Eesti kokku"].copy()
geo_df = geo_df.merge(vaktsineerimine, left_on="NIMI", right_on="Maakond", how="left")
geo_df = geo_df.merge(haigestumus, left_on="NIMI", right_on="Maakond", how="left")

# --- KAARDID ---
st.subheader(f"{valitud_haigus} ({valitud_aasta}) maakonniti")

fig, axes = plt.subplots(1, 2, figsize=(20, 10))

geo_df.plot(column="Vaktsineerimine", cmap="YlGnBu", linewidth=0.5,
            edgecolor="white", legend=True, ax=axes[0],
            legend_kwds={"label": "Vaktsineerimise %", "orientation": "horizontal"})
axes[0].set_title("Vaktsineerimise määr")
axes[0].axis("off")

geo_df.plot(column="Haigestumus", cmap="Reds", linewidth=0.5,
            edgecolor="white", legend=True, ax=axes[1],
            legend_kwds={"label": "Haigestunute arv", "orientation": "horizontal"})
axes[1].set_title("Haigestumus")
axes[1].axis("off")

st.pyplot(fig)

# --- DETAILNE TABEL ---
if valitud_maakond != "Eesti kokku":
    st.subheader(f"📍 {valitud_maakond} - detailne vaade")
    col1, col2 = st.columns([1, 2])
    with col1:
        maakond_geom = combined_gdf[combined_gdf["NIMI"] == valitud_maakond]
        if not maakond_geom.empty and maakond_geom.geometry.notnull().all():
            fig2, ax2 = plt.subplots(figsize=(5, 5))
            maakond_geom.plot(ax=ax2, color="lightblue", edgecolor="black")
            ax2.set_title(valitud_maakond)
            ax2.axis("off")
            st.pyplot(fig2)
        else:
            st.warning("❗ Valitud maakonnal puudub kehtiv geomeetria.")
    with col2:
        try:
            haigus_mk = haigused_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")[valitud_haigus].values[0]
            vakts_mk = vakts_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")[valitud_haigus].values[0]
            st.metric("Haigestunute arv", f"{int(haigus_mk)}")
            st.metric("Vaktsineerimise määr (%)", f"{vakts_mk}")
        except IndexError:
            st.warning("Andmed puuduvad.")
else:
    st.subheader("🌍 Eesti kokku – ülevaade")
    try:
        haigus_eesti = haigused_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
        vakts_eesti = vakts_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
        col1, col2 = st.columns(2)
        col1.metric("Haigestunute arv", f"{int(haigus_eesti)}")
        col2.metric("Vaktsineerimise määr (%)", f"{vakts_eesti}")
    except IndexError:
        st.warning("Andmed puuduvad.")

# --- TRENDID: VAKTSINEERIMINE JA HAIGUSTE ARV ---
st.subheader("📈 Vaktsineerimise ja haigestumise trend (eelnevad 5 aastat)")

eelnevad_aastad = [a for a in aastad if a < valitud_aasta][-5:]

vakts_ajalugu = vakts_df[
    (vakts_df["Aasta"].isin(eelnevad_aastad)) &
    (vakts_df["Maakond"] == valitud_maakond)
][["Aasta", valitud_haigus]].rename(columns={valitud_haigus: "Vaktsineerimine"}).sort_values("Aasta")

haigus_ajalugu = haigused_df[
    (haigused_df["Aasta"].isin(eelnevad_aastad)) &
    (haigused_df["Maakond"] == valitud_maakond)
][["Aasta", valitud_haigus]].rename(columns={valitud_haigus: "Haigestumus"}).sort_values("Aasta")

if not vakts_ajalugu.empty and not haigus_ajalugu.empty:
    merged_trend = pd.merge(vakts_ajalugu, haigus_ajalugu, on="Aasta")
    fig3 = px.line(merged_trend, x="Aasta", y=["Vaktsineerimine", "Haigestumus"],
                   markers=True, title="Vaktsineerimise ja haigestumise trend", labels={
                       "value": "Väärtus", "variable": "Mõõdik"
                   })
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.warning("❗ Trendide joonistamiseks puuduvad andmed.")

# --- VÕRDLUSGRAAFIK: VAKTSINEERIMATA vs HAIGESTUNUD ---
st.subheader("📊 Haigestunute arv vs vaktsineerimata osakaal")

try:
    vakts_row = vakts_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")
    haigus_row = haigused_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")

    if not vakts_row.empty and not haigus_row.empty:
        vaktsineerimata = 100 - vakts_row[valitud_haigus].values[0]
        haigestunud = haigus_row[valitud_haigus].values[0]

        võrdlus_df = pd.DataFrame({
            "Näitaja": ["Vaktsineerimata osakaal (%)", "Haigestunute arv"],
            "Väärtus": [vaktsineerimata, haigestunud]
        })

        fig4 = px.bar(võrdlus_df, x="Näitaja", y="Väärtus", color="Näitaja",
                      title="Haigestunute arv vs vaktsineerimata osakaal", text="Väärtus")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.warning("❗ Valitud piirkonna kohta puuduvad täielikud andmed.")

except Exception as e:
    st.error(f"❌ Viga võrdlusgraafiku loomisel: {e}")