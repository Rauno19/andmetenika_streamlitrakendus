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
# Kasuta Streamlit'i sisseehitatud vahemällu salvestamist, et vältida andmete korduva laadimist
@st.cache_data
def load_data():
    vakts_df = pd.read_excel("andmestikud/vaktsineerimine.xlsx")
    haigused_df = pd.read_excel("andmestikud/Haigused.xlsx")
    maakond_gdf = gpd.read_file("andmestikud/maakond.json")
    asustus_gdf = gpd.read_file("andmestikud/asustusyksus.json")

    # --- PUHASTUS ---
    def puhasta(df):
        df.columns = df.columns.str.strip()
        # Kontrolli, kas 'Maakond' veerg on olemas enne strip'i
        if 'Maakond' in df.columns:
            df["Maakond"] = df["Maakond"].str.strip()
        df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")
        return df

    vakts_df = puhasta(vakts_df)
    haigused_df = puhasta(haigused_df)
    
    # Kindlusta, et 'NIMI' veerg on olemas enne kasutamist
    if 'MNIMI' in maakond_gdf.columns:
        maakond_gdf["NIMI"] = maakond_gdf["MNIMI"].str.strip()
    else:
        # Alternatiivne lahendus või veateade, kui 'MNIMI' puudub
        st.error("Maakonna GeoJSON failist puudub 'MNIMI' veerg.")
        return None, None, None, None, None # Tagasta None'id, et vältida edasisi vigu

    if 'ONIMI' in asustus_gdf.columns:
        asustus_gdf["NIMI"] = asustus_gdf["ONIMI"].str.strip()
    else:
        st.error("Asustusüksuse GeoJSON failist puudub 'ONIMI' veerg.")
        return None, None, None, None, None

    # --- LISA TALLINN ja NARVA ---
    extra_cities = asustus_gdf[asustus_gdf["NIMI"].isin(["Tallinn", "Narva linn"])]
    combined_gdf = pd.concat([
        maakond_gdf[["NIMI", "geometry"]],
        extra_cities[["NIMI", "geometry"]]
    ], ignore_index=True).drop_duplicates(subset="NIMI")
    
    return vakts_df, haigused_df, maakond_gdf, asustus_gdf, combined_gdf

vakts_df, haigused_df, maakond_gdf, asustus_gdf, combined_gdf = load_data()

# Kontrolli, kas andmete laadimine õnnestus
if vakts_df is None or haigused_df is None or combined_gdf is None:
    st.stop()


# --- KASUTAJA VALIKUD ---
aastad = sorted(vakts_df["Aasta"].dropna().unique().astype(int))
haigused = sorted(list(set(vakts_df.columns) & set(haigused_df.columns) - {"Aasta", "Maakond"}))
maakonnad = sorted(list(set(vakts_df["Maakond"]) | set(haigused_df["Maakond"])))


valitud_aasta = st.sidebar.selectbox("🗓 Vali aasta", aastad)
haiguste_arv = st.sidebar.slider("🦠 Mitu haigust soovid võrrelda?", 1, min(5, len(haigused)), 1)
valitud_haigused = st.sidebar.multiselect("🦠 Vali haigused", options=haigused, default=haigused[:haiguste_arv], max_selections=haiguste_arv)
valitud_maakonnad = st.sidebar.multiselect("📍 Vali kuni 3 maakonda", options=maakonnad, default=[maakonnad[0]], max_selections=3)

if not valitud_maakonnad or not valitud_haigused:
    st.warning("Palun vali vähemalt üks maakond ja üks haigus.")
    st.stop()

# --- KAARDID, DETAILVAADE, VÕRDLUSDIAGRAMM, TRENDIJOON ja AJALOOLINE TULPGRAAFIK HAIGUSEPÕHISELT ---
# Loome tabid iga valitud haiguse jaoks
tabs = st.tabs(valitud_haigused)

for i, haigus in enumerate(valitud_haigused):
    with tabs[i]:
        st.header(f"Andmed haiguse kohta: {haigus}")

        # --- KAARDID ---
        st.markdown(f"#### 🗺 Maakonnakaardid ({haigus}, {valitud_aasta})")
        vakts = vakts_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Vaktsineerimine"})
        haig = haigused_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Haigestumus"})

        geo_df = combined_gdf.merge(vakts, left_on="NIMI", right_on="Maakond", how="left")
        geo_df = geo_df.merge(haig, on="Maakond", how="left")

        fig_map, axes_map = plt.subplots(1, 2, figsize=(20, 10))

        # Vaktsineerimine – 0-100 skaalal
        geo_df.plot(
            column="Vaktsineerimine",
            cmap="viridis",
            linewidth=0.3,
            edgecolor="#f8f8f8",
            legend=True,
            ax=axes_map[0],
            vmin=0,
            vmax=100,
            legend_kwds={
                "label": "Vaktsineerimise määr (%)",
                "orientation": "horizontal"
            }
        )
        axes_map[0].set_title(f"Vaktsineerimine ({haigus})")
        axes_map[0].axis("off")

        # Haigestumus – jääb dünaamiliseks
        geo_df.plot(
            column="Haigestumus",
            cmap="OrRd",
            linewidth=0.3,
            edgecolor="#f8f8f8",
            legend=True,
            ax=axes_map[1],
            legend_kwds={
                "label": "Haigestunute arv",
                "orientation": "horizontal"
            }
        )
        axes_map[1].set_title(f"Haigestumus ({haigus})")
        axes_map[1].axis("off")

        st.pyplot(fig_map)


        # --- DETAILNE VAADE ---
        st.markdown(f"#### 📍 Detailne vaade valitud maakondadele ({haigus})")
        for mk in valitud_maakonnad:
            st.markdown(f"##### {mk}")
            col1_det, col2_det = st.columns([1, 2])

            with col1_det:
                maakond_geom = combined_gdf[combined_gdf["NIMI"] == mk]
                if not maakond_geom.empty:
                    fig2, ax2 = plt.subplots(figsize=(5, 5))
                    maakond_geom.plot(ax=ax2, color="#aad3df", edgecolor="#2c3e50")
                    ax2.set_title(mk)
                    ax2.axis("off")
                    st.pyplot(fig2)

            with col2_det:
                try:
                    ha_val = haigused_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                    va_val = vakts_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                    st.metric(f"Haigestunute arv", f"{int(ha_val)}")
                    st.metric(f"Vaktsineerimise määr (%)", f"{va_val}")
                except IndexError:
                    st.info(f"Andmed puuduvad maakonna {mk} ja haiguse {haigus} kohta.")

        # --- VÕRDLUSDIAGRAMM ---
        st.markdown(f"#### 📉 Vaktsineerimata vs haigestumus ({haigus})")
        scatter_df = vakts_df[vakts_df["Aasta"] == valitud_aasta][["Maakond", haigus]].rename(columns={haigus: "Vaktsineerimine"})
        scatter_df = scatter_df.merge(
            haigused_df[haigused_df["Aasta"] == valitud_aasta][["Maakond", haigus]].rename(columns={haigus: "Haigestumus"}),
            on="Maakond")
        scatter_df["Vaktsineerimata"] = 100 - scatter_df["Vaktsineerimine"]

        fig3 = px.scatter(scatter_df, x="Vaktsineerimata", y="Haigestumus", text="Maakond",
                          labels={"Vaktsineerimata": "Vaktsineerimata %", "Haigestumus": "Haigestunute arv"},
                          title=f"Seos: vaktsineerimata vs haigestunud ({haigus})")
        fig3.update_traces(textposition="top center")
        st.plotly_chart(fig3, use_container_width=True)

        # --- TRENDIJOON (eelnevad 5 aastat) ---
        st.markdown(f"#### 📈 Trend ({haigus}, eelnevad 5 aastat)")
        eelnevad_aastad = [a for a in aastad if a < valitud_aasta][-5:]
        
        # Lisame valitud aasta ka trendijoontele, kui see on eelnevate aastatega samal real
        if valitud_aasta in aastad:
            eelnevad_aastad.append(valitud_aasta)
            eelnevad_aastad = sorted(list(set(eelnevad_aastad))) # Eemalda duplikaadid ja sorteeri

        fig_trend = go.Figure()

        for mk_trend in valitud_maakonnad:
            vakts_ajalugu = vakts_df[(vakts_df["Aasta"].isin(eelnevad_aastad)) & (vakts_df["Maakond"] == mk_trend)][["Aasta", haigus]].rename(columns={haigus: "Vaktsineerimine"})
            haigus_ajalugu = haigused_df[(haigused_df["Aasta"].isin(eelnevad_aastad)) & (haigused_df["Maakond"] == mk_trend)][["Aasta", haigus]].rename(columns={haigus: "Haigestumus"})

            if vakts_ajalugu.empty or haigus_ajalugu.empty:
                continue

            ajalugu_df = vakts_ajalugu.merge(haigus_ajalugu, on="Aasta").sort_values("Aasta")

            fig_trend.add_trace(go.Scatter(x=ajalugu_df["Aasta"], y=ajalugu_df["Vaktsineerimine"], mode="lines+markers", name=f"{mk_trend} – Vakts", yaxis="y1"))
            fig_trend.add_trace(go.Scatter(x=ajalugu_df["Aasta"], y=ajalugu_df["Haigestumus"], mode="lines+markers", name=f"{mk_trend} – Haigus", yaxis="y2"))

        fig_trend.update_layout(
            xaxis=dict(title="Aasta", tickmode="linear"),
            yaxis=dict(title="Vaktsineerimine (%)", range=[0, 100], side="left"),
            yaxis2=dict(title="Haigestumus (arv)", overlaying="y", side="right"),
            title=f"Vaktsineerimise ja haigestumuse trend ({haigus})",
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
        st.plotly_chart(fig_trend, use_container_width=True)

        # --- AJALOOLISED TULPGRAAFIKUD ---
        st.markdown(f"#### 📊 Ajaloolised andmed – {haigus}")

        v_ajalugu_dict = {}
        h_ajalugu_dict = {}

        max_vakts_aasta = 2023 # See konstant võiks olla mujal defineeritud, kui see on üleüldine piirang

        for mk_hist in valitud_maakonnad:
            v_df = vakts_df.query("Maakond == @mk_hist and Aasta <= @max_vakts_aasta")[["Aasta", haigus]].dropna()
            h_df = haigused_df.query("Maakond == @mk_hist")[["Aasta", haigus]].dropna()

            if not v_df.empty:
                v_ajalugu_dict[mk_hist] = v_df.set_index("Aasta")[haigus]
            if not h_df.empty:
                h_ajalugu_dict[mk_hist] = h_df.set_index("Aasta")[haigus]

        col1_hist, col2_hist = st.columns(2)

        # Vaktsineerimine ajalugu
        with col1_hist:
            st.write("**Vaktsineerimise määr (%)**")
            if v_ajalugu_dict:
                fig_v, ax_v = plt.subplots(figsize=(5, 3))
                for mk_name, series in v_ajalugu_dict.items():
                    series.sort_index().plot(ax=ax_v, marker="o", linewidth=2, alpha=0.8, label=mk_name)
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
                ax_v.set_title(f"Vaktsineerimine ajalugu ({haigus})", fontsize=12) # Lisa pealkiri
                plt.tight_layout()
                st.pyplot(fig_v)
            else:
                st.info(f"Vaktsineerimise ajaloolised andmed puuduvad haiguse {haigus} kohta.")

        # Haigestumus ajalugu
        with col2_hist:
            st.write("**Haigestumus (juhtumid)**")
            if h_ajalugu_dict:
                fig_h, ax_h = plt.subplots(figsize=(5, 3))
                for mk_name, series in h_ajalugu_dict.items():
                    series.sort_index().plot(ax=ax_h, marker="o", linewidth=2, alpha=0.8, label=mk_name)
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
                ax_h.set_title(f"Haigestumus ajalugu ({haigus})", fontsize=12) # Lisa pealkiri
                plt.tight_layout()
                st.pyplot(fig_h)
            else:
                st.info(f"Haigestumuse ajaloolised andmed puuduvad haiguse {haigus} kohta.")

     # --- KOKKUVÕTLIKUD TULPGRAAFIKUD HAIGUSE kohta---
        st.markdown(f"#### 📊 Kokkuvõtlikud tulpgraafikud ({haigus}) – kõik valitud maakonnad")

        vakts_data_bar = []
        haigus_data_bar = []
        for mk_bar in valitud_maakonnad:
            try:
                vakts_val = vakts_df.query("Aasta == @valitud_aasta & Maakond == @mk_bar")[haigus].values[0]
                haig_val = haigused_df.query("Aasta == @valitud_aasta & Maakond == @mk_bar")[haigus].values[0]
                vakts_data_bar.append({"Maakond": mk_bar, "Vaktsineerimine (%)": vakts_val})
                haigus_data_bar.append({"Maakond": mk_bar, "Haigestumus (juhtumid)": haig_val})
            except IndexError:
                pass 

        df_vakts_bar = pd.DataFrame(vakts_data_bar)
        df_haigus_bar = pd.DataFrame(haigus_data_bar)

        col1_bar, col2_bar = st.columns(2)
        with col1_bar:
            if not df_vakts_bar.empty:
                fig_vakts_bar = px.bar(df_vakts_bar, x="Maakond", y="Vaktsineerimine (%)", color="Maakond",
                                   title=f"Vaktsineerimise määr ({haigus}, {valitud_aasta})",
                                   color_discrete_sequence=px.colors.qualitative.Set2,
                                   range_y=[0, 100]) # LISATUD see rida!
                fig_vakts_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_vakts_bar, use_container_width=True)
            else:
                st.info(f"Vaktsineerimise andmed puuduvad haiguse {haigus} kohta.")

        with col2_bar:
            if not df_haigus_bar.empty:
                fig_haigus_bar = px.bar(df_haigus_bar, x="Maakond", y="Haigestumus (juhtumid)", color="Maakond",
                                    title=f"Haigestumus ({haigus}, {valitud_aasta})",
                                    color_discrete_sequence=px.colors.qualitative.Set1)
                fig_haigus_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_haigus_bar, use_container_width=True)
            else:
                st.info(f"Haigestumuse andmed puuduvad haiguse {haigus} kohta.")