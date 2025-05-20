import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import plotly.express as px
import plotly.graph_objects as go
#import seaborn as sns

#sns.set_style("white")
# --- SEADISTUS ---
st.set_page_config(layout="wide")
st.title("💉 Vaktsineerimine ja haigestumus maakonniti")

# --- LAE ANDMED ---
vakts_df = pd.read_excel("andmestikud/vaktsineerimine.xlsx")
haigused_df = pd.read_excel("andmestikud/Haigused.xlsx")
maakond_gdf = gpd.read_file("andmestikud/maakond.json")
asustus_gdf = gpd.read_file("andmestikud/asustusyksus.json")

# --- PUHASTUS ---
def puhasta(df):
    df.columns = df.columns.str.strip()
    df["Maakond"] = df["Maakond"].str.strip()
    df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")
    return df

vakts_df = puhasta(vakts_df)
haigused_df = puhasta(haigused_df)
maakond_gdf["NIMI"] = maakond_gdf["MNIMI"].str.strip()
asustus_gdf["NIMI"] = asustus_gdf["ONIMI"].str.strip()

# --- LISA TALLINN ja NARVA ---
extra_cities = asustus_gdf[asustus_gdf["NIMI"].isin(["Tallinn", "Narva linn"])]
combined_gdf = pd.concat([
    maakond_gdf[["NIMI", "geometry"]],
    extra_cities[["NIMI", "geometry"]]
], ignore_index=True).drop_duplicates(subset="NIMI")

# --- KASUTAJA VALIKUD ---
aastad = sorted(vakts_df["Aasta"].dropna().unique().astype(int))
haigused = sorted(set(vakts_df.columns) & set(haigused_df.columns) - {"Aasta", "Maakond"})
maakonnad = sorted(set(vakts_df["Maakond"]) | set(haigused_df["Maakond"]))

valitud_aasta = st.sidebar.selectbox("🗓 Vali aasta", aastad)
haiguste_arv = st.sidebar.slider("🦠 Mitu haigust soovid võrrelda?", 1, min(5, len(haigused)), 1)
valitud_haigused = st.sidebar.multiselect("🦠 Vali haigused", options=haigused, default=haigused[:haiguste_arv], max_selections=haiguste_arv)
valitud_maakonnad = st.sidebar.multiselect("📍 Vali kuni 3 maakonda", options=maakonnad, default=[maakonnad[0]], max_selections=3)

if not valitud_maakonnad or not valitud_haigused:
    st.warning("Palun vali vähemalt üks maakond ja üks haigus.")
    st.stop()

mitu_maakonda = len(valitud_maakonnad) > 1
valitud_maakond = valitud_maakonnad[0] if not mitu_maakonda else None

# --- KAARDID ---
tabs = st.tabs(valitud_haigused)
for i, haigus in enumerate(valitud_haigused):
    with tabs[i]:
        vakts = vakts_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Vaktsineerimine"})
        haig = haigused_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Haigestumus"})

        geo_df = combined_gdf.merge(vakts, left_on="NIMI", right_on="Maakond", how="left")
        geo_df = geo_df.merge(haig, on="Maakond", how="left")

        fig, axes = plt.subplots(1, 2, figsize=(20, 10))

        # Vaktsineerimine – 0-100 skaalal
        geo_df.plot(
            column="Vaktsineerimine",
            cmap="viridis",
            linewidth=0.3,
            edgecolor="#f8f8f8",
            legend=True,
            ax=axes[0],
            vmin=0,
            vmax=100,
            legend_kwds={
                "label": "Vaktsineerimise määr (%)",
                "orientation": "horizontal"
            }
        )
        axes[0].set_title("Vaktsineerimine")
        axes[0].axis("off")

        # Haigestumus – jääb dünaamiliseks
        geo_df.plot(
            column="Haigestumus",
            cmap="OrRd",
            linewidth=0.3,
            edgecolor="#f8f8f8",
            legend=True,
            ax=axes[1],
            legend_kwds={
                "label": "Haigestunute arv",
                "orientation": "horizontal"
            }
        )
        axes[1].set_title("Haigestumus")
        axes[1].axis("off")

        st.pyplot(fig)


# --- DETAILNE VAADE ---
for mk in valitud_maakonnad:
    st.markdown(f"#### 📍 {mk} – detailne vaade")
    col1, col2 = st.columns([1, 2])

    with col1:
        maakond_geom = combined_gdf[combined_gdf["NIMI"] == mk]
        if not maakond_geom.empty:
            fig2, ax2 = plt.subplots(figsize=(5, 5))
            maakond_geom.plot(ax=ax2, color="#aad3df", edgecolor="#2c3e50")
            ax2.set_title(mk)
            ax2.axis("off")
            st.pyplot(fig2)

    with col2:
        for haigus in valitud_haigused:
            try:
                ha = haigused_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                va = vakts_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                st.metric(f"{haigus} – Haigestunute arv", f"{int(ha)}")
                st.metric(f"{haigus} – Vaktsineerimise määr (%)", f"{va}")
            except IndexError:
                st.info(f"Andmed puuduvad: {haigus}")

# --- VÕRDLUSDIAGRAMM ---
for haigus in valitud_haigused:
    st.markdown(f"#### 📉 Vaktsineerimata vs haigestumus ({haigus})")
    scatter_df = vakts_df[vakts_df["Aasta"] == valitud_aasta][["Maakond", haigus]].rename(columns={haigus: "Vaktsineerimine"})
    scatter_df = scatter_df.merge(
        haigused_df[haigused_df["Aasta"] == valitud_aasta][["Maakond", haigus]].rename(columns={haigus: "Haigestumus"}),
        on="Maakond")
    scatter_df["Vaktsineerimata"] = 100 - scatter_df["Vaktsineerimine"]

    fig3 = px.scatter(scatter_df, x="Vaktsineerimata", y="Haigestumus", text="Maakond",
                      labels={"Vaktsineerimata": "Vaktsineerimata %", "Haigestumus": "Haigestunute arv"},
                      title="Seos: vaktsineerimata vs haigestunud")
    fig3.update_traces(textposition="top center")
    st.plotly_chart(fig3, use_container_width=True)

# --- TRENDIJOON (uuendatud legendiga) ---
st.markdown("#### 📈 Trend (eelnevad 5 aastat)")
eelnevad_aastad = [a for a in aastad if a < valitud_aasta][-5:]
fig = go.Figure()

for mk in valitud_maakonnad:
    for haigus in valitud_haigused:
        vakts_ajalugu = vakts_df[(vakts_df["Aasta"].isin(eelnevad_aastad)) & (vakts_df["Maakond"] == mk)][["Aasta", haigus]].rename(columns={haigus: "Vaktsineerimine"})
        haigus_ajalugu = haigused_df[(haigused_df["Aasta"].isin(eelnevad_aastad)) & (haigused_df["Maakond"] == mk)][["Aasta", haigus]].rename(columns={haigus: "Haigestumus"})

        if vakts_ajalugu.empty or haigus_ajalugu.empty:
            continue

        ajalugu_df = vakts_ajalugu.merge(haigus_ajalugu, on="Aasta").sort_values("Aasta")

        fig.add_trace(go.Scatter(x=ajalugu_df["Aasta"], y=ajalugu_df["Vaktsineerimine"], mode="lines+markers", name=f"{mk} – {haigus} – Vakts", yaxis="y1"))
        fig.add_trace(go.Scatter(x=ajalugu_df["Aasta"], y=ajalugu_df["Haigestumus"], mode="lines+markers", name=f"{mk} – {haigus} – Haigus", yaxis="y2"))

fig.update_layout(
    xaxis=dict(title="Aasta", tickmode="linear"),
    yaxis=dict(title="Vaktsineerimine (%)", range=[0, 100], side="left"),
    yaxis2=dict(title="Haigestumus (arv)", overlaying="y", side="right"),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.3,
        xanchor="center",
        x=0.5,
        traceorder="normal",
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(0,0,0,0)"
    ),
    margin=dict(l=40, r=40, t=30, b=80),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# --- AJALOOLINE TULPGRAAFIK ---
# --- AJALOOLISED ANDMED – visuaalselt puhas versioon ---
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

#plt.style.use("seaborn-white")  # puhas ja hele

max_vakts_aasta = 2023

for haigus in valitud_haigused:
    st.markdown(f"#### 📈 Ajaloolised andmed – {haigus}")

    v_ajalugu_dict = {}
    h_ajalugu_dict = {}

    for mk in valitud_maakonnad:
        v_df = vakts_df.query("Maakond == @mk and Aasta <= @max_vakts_aasta")[["Aasta", haigus]].dropna()
        h_df = haigused_df.query("Maakond == @mk")[["Aasta", haigus]].dropna()

        if not v_df.empty:
            v_ajalugu_dict[mk] = v_df.set_index("Aasta")[haigus]
        if not h_df.empty:
            h_ajalugu_dict[mk] = h_df.set_index("Aasta")[haigus]

    col1, col2 = st.columns(2)

    # Vaktsineerimine
    with col1:
        st.write("**Vaktsineerimise määr (%)**")
        if v_ajalugu_dict:
            fig_v, ax_v = plt.subplots(figsize=(5, 3))
            for mk, series in v_ajalugu_dict.items():
                series.sort_index().plot(ax=ax_v, marker="o", linewidth=2, alpha=0.8, label=mk)
            ax_v.set_xlabel("Aasta", fontsize=10)
            ax_v.set_ylabel("", fontsize=10)
            ax_v.set_ylim(0, 100)
            ax_v.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
            ax_v.spines['top'].set_visible(False)
            ax_v.spines['right'].set_visible(False)
            ax_v.spines['left'].set_color("#cccccc")
            ax_v.spines['bottom'].set_color("#cccccc")
            ax_v.tick_params(axis='both', colors="#555555")
            ax_v.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5, integer=True))
            ax_v.legend(title="Maakond", fontsize=8, title_fontsize=9)
            plt.tight_layout()
            st.pyplot(fig_v)
        else:
            st.info("Vaktsineerimise andmed puuduvad.")

    # Haigestumus
    with col2:
        st.write("**Haigestumus (juhtumid)**")
        if h_ajalugu_dict:
            fig_h, ax_h = plt.subplots(figsize=(5, 3))
            for mk, series in h_ajalugu_dict.items():
                series.sort_index().plot(ax=ax_h, marker="o", linewidth=2, alpha=0.8, label=mk)
            ax_h.set_xlabel("Aasta", fontsize=10)
            ax_h.set_ylabel("", fontsize=10)
            ax_h.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
            ax_h.spines['top'].set_visible(False)
            ax_h.spines['right'].set_visible(False)
            ax_h.spines['left'].set_color("#cccccc")
            ax_h.spines['bottom'].set_color("#cccccc")
            ax_h.tick_params(axis='both', colors="#555555")
            ax_h.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5, integer=True))
            ax_h.legend(title="Maakond", fontsize=8, title_fontsize=9)
            plt.tight_layout()
            st.pyplot(fig_h)
        else:
            st.info("Haigestumuse andmed puuduvad.")

# --- KOKKUVÕTLIKUD TULPGRAAFIKUD ---
st.markdown("#### 📊 Kokkuvõtlikud tulpgraafikud (vaktsineerimine ja haigestumus) – kõik valitud maakonnad")

for haigus in valitud_haigused:
    vakts_data = []
    haigus_data = []
    for mk in valitud_maakonnad:
        try:
            vakts = vakts_df.query("Aasta == @valitud_aasta & Maakond == @mk")[haigus].values[0]
            haig = haigused_df.query("Aasta == @valitud_aasta & Maakond == @mk")[haigus].values[0]
            vakts_data.append({"Maakond": mk, "Vaktsineerimine (%)": vakts})
            haigus_data.append({"Maakond": mk, "Haigestumus (juhtumid)": haig})
        except:
            continue

    df_vakts = pd.DataFrame(vakts_data)
    df_haigus = pd.DataFrame(haigus_data)

    col1, col2 = st.columns(2)
    with col1:
        if not df_vakts.empty:
            fig_vakts = px.bar(df_vakts, x="Maakond", y="Vaktsineerimine (%)", color="Maakond",
                               title=f"Vaktsineerimise määr ({haigus}, {valitud_aasta})",
                               color_discrete_sequence=px.colors.qualitative.Set2)
            fig_vakts.update_layout(showlegend=False)
            st.plotly_chart(fig_vakts, use_container_width=True)
        else:
            st.info("Vaktsineerimise andmed puuduvad.")

    with col2:
        if not df_haigus.empty:
            fig_haigus = px.bar(df_haigus, x="Maakond", y="Haigestumus (juhtumid)", color="Maakond",
                                title=f"Haigestumus ({haigus}, {valitud_aasta})",
                                color_discrete_sequence=px.colors.qualitative.Set1)
            fig_haigus.update_layout(showlegend=False)
            st.plotly_chart(fig_haigus, use_container_width=True)
        else:
            st.info("Haigestumuse andmed puuduvad.")