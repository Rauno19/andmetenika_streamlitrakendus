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

# --- KOKKUVÕTE EESTI KOHTA ---
st.subheader("🌍 Kogu Eesti kohta")

try:
    vakts_eesti = vakts_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
    haigus_eesti = haigused_df.query("Aasta == @valitud_aasta and Maakond == 'Eesti kokku'")[valitud_haigus].values[0]
except IndexError:
    vakts_eesti = haigus_eesti = None

col1, col2 = st.columns(2)
col1.metric("Vaktsineerimise määr (%)", f"{vakts_eesti}" if vakts_eesti else "–")
col2.metric("Haigestunute arv", f"{int(haigus_eesti)}" if haigus_eesti else "–")