import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# --- PEALKIRI ---
st.title("💉 Vaktsineerimine ja haigestumus maakonniti")

# --- LAE ANDMED ---
vakts_df = pd.read_excel("andmestikud/vaktsineerimine.xlsx")
haigused_df = pd.read_excel("andmestikud/Haigused.xlsx")
maakond_gdf = gpd.read_file("andmestikud/maakond.json")

# --- PUHASTUS ---
vakts_df.columns = vakts_df.columns.str.strip()
haigused_df.columns = haigused_df.columns.str.strip()
vakts_df["Maakond"] = vakts_df["Maakond"].str.strip()
haigused_df["Maakond"] = haigused_df["Maakond"].str.strip()
maakond_gdf["NIMI"] = maakond_gdf["MNIMI"].str.strip()

vakts_df["Aasta"] = pd.to_numeric(vakts_df["Aasta"], errors="coerce")
haigused_df["Aasta"] = pd.to_numeric(haigused_df["Aasta"], errors="coerce")

# --- MÄÄRA AASTAD JA HAIUSED ---
aastad = sorted(vakts_df["Aasta"].dropna().unique().astype(int))

haigused = sorted(
    set(vakts_df.columns) &
    set(haigused_df.columns) -
    {"Aasta", "Maakond"}
)

# --- KASUTAJA VALIKUD ---
valitud_aasta = st.sidebar.selectbox("🗓 Vali aasta", aastad)
valitud_haigus = st.sidebar.selectbox("🦠 Vali haigus", haigused)
kõik_maakonnad = sorted(vakts_df["Maakond"].dropna().unique())
valitud_maakond = st.sidebar.selectbox("📍 Vali maakond", kõik_maakonnad)

# --- FILTERDA ---
vaktsineerimine = vakts_df.query("Aasta == @valitud_aasta and Maakond != 'Eesti kokku'")[["Maakond", valitud_haigus]]
vaktsineerimine = vaktsineerimine.rename(columns={valitud_haigus: "Vaktsineerimine"})

haigestumus = haigused_df.query("Aasta == @valitud_aasta and Maakond != 'Eesti kokku'")[["Maakond", valitud_haigus]]
haigestumus = haigestumus.rename(columns={valitud_haigus: "Haigestumus"})

# --- GEOANDMETEGA LIITMINE ---
geo_df = maakond_gdf.merge(vaktsineerimine, left_on="NIMI", right_on="Maakond", how="left")
geo_df = geo_df.merge(haigestumus, left_on="NIMI", right_on="Maakond", how="left")

# --- KAARDID ---
st.subheader(f"{valitud_haigus} ({valitud_aasta}) maakonniti")

fig, axes = plt.subplots(1, 2, figsize=(20, 10))

geo_df.plot(
    column="Vaktsineerimine",
    cmap="YlGnBu",
    linewidth=0.5,
    edgecolor="white",
    legend=True,
    ax=axes[0],
    legend_kwds={"label": "Vaktsineerimise %", "orientation": "horizontal"}
)
axes[0].set_title("Vaktsineerimise määr")
axes[0].axis("off")

geo_df.plot(
    column="Haigestumus",
    cmap="Reds",
    linewidth=0.5,
    edgecolor="white",
    legend=True,
    ax=axes[1],
    legend_kwds={"label": "Haigestunute arv", "orientation": "horizontal"}
)
axes[1].set_title("Haigestumus")
axes[1].axis("off")

st.pyplot(fig)

# --- VALITUD MAAKONNA DETAILNE ÜLEVAADE ---
st.subheader(f"📍 {valitud_maakond} - detailne vaade")

col1, col2 = st.columns([1, 2])

# VÄIKE KAART
with col1:
    maakond_geom = maakond_gdf[maakond_gdf["NIMI"] == valitud_maakond]

    if not maakond_geom.empty and maakond_geom.geometry.notnull().all():
        fig2, ax2 = plt.subplots(figsize=(5, 5))
        maakond_geom.plot(ax=ax2, color="lightblue", edgecolor="black")
        ax2.set_title(f"{valitud_maakond}")
        ax2.axis("off")
        st.pyplot(fig2)
    else:
        st.warning("❗ Valitud maakonnal puudub kehtiv geomeetria.")

# HAAIGESTUNUTE ARV
with col2:
    try:
        haigus_mk = haigused_df.query("Aasta == @valitud_aasta and Maakond == @valitud_maakond")[valitud_haigus].values[0]
        st.metric("Haigestunute arv", f"{int(haigus_mk)}")
    except IndexError:
        st.write("Andmed puuduvad.")

# --- VAKTSINEERIMISE MÄÄR 5 AASTA LÕIKES ---
st.subheader("📈 Vaktsineerimise määr (eelnevad 5 aastat)")

eelnevad_aastad = [a for a in aastad if a < valitud_aasta][-5:]
vakts_ajalugu = vakts_df[
    (vakts_df["Aasta"].isin(eelnevad_aastad)) &
    (vakts_df["Maakond"] == valitud_maakond)
][["Aasta", valitud_haigus]].rename(columns={valitud_haigus: "Vaktsineerimine"}).sort_values("Aasta")

if not vakts_ajalugu.empty:
    st.line_chart(vakts_ajalugu.set_index("Aasta"))
else:
    st.info("Puuduvad andmed vaktsineerimise kohta viimase 5 aasta jooksul.")
