import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import plotly.express as px
import plotly.graph_objects as go

# --- SEADISTUS ---
st.set_page_config(layout="wide")
st.title("💉 Väikelaste vaktsineerimine ja vaktsiinidega ennetatavatesse haigustesse haigestumus")

st.markdown("""

💡 **Mida saad teha?**
- Vali aasta ja haigused, mille andmeid soovid analüüsida.
- Vaata kaardilt, kui palju lapsi on vaktsineeritud ja kui palju haigestumisi samal perioodil on olnud.
- Võrdle konkreetseid maakondi detailsemalt ning jälgi viimase viie aasta trende.
- Analüüsi seost vaktsineerimatuse ja haigestumise vahel.

**Mis on hetkel puudu?**
- 2024 ja 2025 vaktsineerimisandmeid ei ole veel avalikustatud.
- 2025 haigusjuhud on märtsikuu seisuga.

Vaktsineerimise ja haigestumuse andmed on pärit Terviseametist ja Tervise Arengu Instituudist.
""")

# --- LAE ANDMED ---
@st.cache_data
def load_data():
    vakts_df = pd.read_excel("andmestikud/vaktsineerimine.xlsx")
    haigused_df = pd.read_excel("andmestikud/Haigused.xlsx")
    maakond_gdf = gpd.read_file("andmestikud/maakond.json")
    asustus_gdf = gpd.read_file("andmestikud/asustusyksus.json")

    def puhasta(df):
        df.columns = df.columns.str.strip()
        if 'Maakond' in df.columns:
            df["Maakond"] = df["Maakond"].str.strip()
        df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")
        return df

    vakts_df = puhasta(vakts_df)
    haigused_df = puhasta(haigused_df)
    
    if 'MNIMI' in maakond_gdf.columns:
        maakond_gdf["NIMI"] = maakond_gdf["MNIMI"].str.strip()
    else:
        st.error("Maakonna GeoJSON failist puudub 'MNIMI' veerg.")
        return None, None, None, None, None

    if 'ONIMI' in asustus_gdf.columns:
        asustus_gdf["NIMI"] = asustus_gdf["ONIMI"].str.strip()
    else:
        st.error("Asustusüksuse GeoJSON failist puudub 'ONIMI' veerg.")
        return None, None, None, None, None

    # Lisa Tallinn ja Narva Combined_gdf-i
    extra_cities = asustus_gdf[asustus_gdf["NIMI"].isin(["Tallinn", "Narva linn"])]
    combined_gdf = pd.concat([
        maakond_gdf[["NIMI", "geometry"]],
        extra_cities[["NIMI", "geometry"]]
    ], ignore_index=True).drop_duplicates(subset="NIMI")
    
    return vakts_df, haigused_df, maakond_gdf, asustus_gdf, combined_gdf

vakts_df, haigused_df, maakond_gdf, asustus_gdf, combined_gdf = load_data()

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

# --- KUVA TULEMUSED HAIGUSEPÕHISELT TABIDES ---
tabs = st.tabs(valitud_haigused)

for i, haigus in enumerate(valitud_haigused):
    with tabs[i]:
        st.header(f"Andmed haiguse kohta: {haigus}")

 # --- KAARDID ---
        st.markdown(f"#### Maakonnakaardid")
        vakts = vakts_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Vaktsineerimine"})
        haig = haigused_df.query("Aasta == @valitud_aasta")[["Maakond", haigus]].rename(columns={haigus: "Haigestumus"})

        geo_df = combined_gdf.merge(vakts, left_on="NIMI", right_on="Maakond", how="left")
        geo_df = geo_df.merge(haig, on="Maakond", how="left")

        fig_map, axes_map = plt.subplots(1, 2, figsize=(20, 10))

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
        st.markdown(f"#### 📍 Detailne vaade valitud maakondadele")
        for mk in valitud_maakonnad:
            st.markdown(f"##### {mk}")
            
            if mk == "Eesti kokku":
                col_det_stat = st.columns(1)[0] 
     
                with col_det_stat:
                    try:
                        ha_val = haigused_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                        va_val = vakts_df.query("Aasta == @valitud_aasta and Maakond == @mk")[haigus].values[0]
                        
                        st.metric(label=f"Haigestunute arv", value=f"{int(ha_val)}")
                        
                        # Vaktsineerimise puhul tinglik kuvamine: number või tekst väiksema fondiga
                        if valitud_aasta >= 2024 and va_val == 0:
                            st.markdown(f"<p style='font-size: 0.8em; margin-bottom: 0;'>Vaktsineerimise määr (%):</p><p style='font-size: 0.9em; font-weight: bold; color: #ff4b4b; margin-top: 0;'>Selle aasta kohta andmed puuduvad.</p>", unsafe_allow_html=True)
                        else:
                            st.metric(label=f"Vaktsineerimise määr (%)", value=f"{va_val}")


                    except IndexError:
                        st.info(f"Andmed puuduvad maakonna {mk} ja haiguse {haigus} kohta.")
            else:
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
                        
                        # Haigestumise puhul alati number, isegi kui 0
                        st.metric(label=f"Haigestunute arv", value=f"{int(ha_val)}")
                        
                        # Vaktsineerimise puhul tinglik kuvamine: number või tekst väiksema fondiga
                        if valitud_aasta >= 2024 and va_val == 0:
                            st.markdown(f"<p style='font-size: 0.8em; margin-bottom: 0;'>Vaktsineerimise määr (%):</p><p style='font-size: 0.9em; font-weight: bold; color: #ff4b4b; margin-top: 0;'>Selle aasta kohta andmed puuduvad.</p>", unsafe_allow_html=True)
                        else:
                            st.metric(label=f"Vaktsineerimise määr (%)", value=f"{va_val}")

                    except IndexError:
                        st.info(f"Andmed puuduvad maakonna {mk} ja haiguse {haigus} kohta.")
    

 # --- KOKKUVÕTLIKUD TULPGRAAFIKUD HAIGUSE kohta ---
        st.markdown(f"#### 📊 Kokkuvõtlikud tulpdiagrammid")

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
                                   range_y=[0, 100])
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

# --- VÕRDLUSDIAGRAMM ---
        st.markdown(f"#### 📉 Vaktsineerimata inimeste ja haigestumuse suhe")
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
        st.markdown(f"#### 📈 Trend eelneva viie aasta kohta)")
    
        max_vakts_data_year = vakts_df["Aasta"].max() 

        eelnevad_aastad_vakts = sorted([a for a in aastad if a <= max_vakts_data_year and a >= max(1, valitud_aasta - 4)])
        eelnevad_aastad_haigus = sorted([a for a in aastad if a <= valitud_aasta and a >= max(1, valitud_aasta - 4)])
        
        fig_trend = go.Figure()

        for mk_trend in valitud_maakonnad:
            # Vaktsineerimise ajalugu, filtreeritud kuni max_vakts_data_year
            vakts_ajalugu = vakts_df[(vakts_df["Aasta"].isin(eelnevad_aastad_vakts)) & (vakts_df["Maakond"] == mk_trend)][["Aasta", haigus]].rename(columns={haigus: "Vaktsineerimine"})
            
            # Haiguse ajalugu, kuni valitud_aasta
            haigus_ajalugu = haigused_df[(haigused_df["Aasta"].isin(eelnevad_aastad_haigus)) & (haigused_df["Maakond"] == mk_trend)][["Aasta", haigus]].rename(columns={haigus: "Haigestumus"})

            # Eemaldame read, kus tegelik vaktsineerimise väärtus on 0 (eeldame, et see tähendab "andmed puuduvad" selles kontekstis)
            vakts_ajalugu = vakts_ajalugu[vakts_ajalugu["Vaktsineerimine"] != 0].dropna()
            haigus_ajalugu = haigus_ajalugu[haigus_ajalugu["Haigestumus"] != 0].dropna() # Kuva haigestumise 0, kui need on teadaolevad 0-d

            if vakts_ajalugu.empty and haigus_ajalugu.empty:
                continue 

            if not vakts_ajalugu.empty:
                
                fig_trend.add_trace(go.Scatter(x=vakts_ajalugu["Aasta"], y=vakts_ajalugu["Vaktsineerimine"], 
                                                mode="lines+markers", name=f"{mk_trend} – Vakts", yaxis="y1"))
            
            # Joonistame haigestumise joone alati, kui andmeid on
            if not haigus_ajalugu.empty:
                fig_trend.add_trace(go.Scatter(x=haigus_ajalugu["Aasta"], y=haigus_ajalugu["Haigestumus"], 
                                                mode="lines+markers", name=f"{mk_trend} – Haigus", yaxis="y2"))

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

 # --- AJALOOLISED JOON- JA TULPGRAAFIKUD ---
        st.markdown(f"#### 📊 Ajaloolised andmed")

        # Optimeerime andmete ettevalmistust
        historical_v_df = vakts_df.query("Aasta <= @valitud_aasta")
        historical_h_df = haigused_df

        col1_hist, col2_hist = st.columns(2)

        # Vaktsineerimine ajalugu (joon)
        with col1_hist:
            st.write("**Vaktsineerimise määr (%)**")
            fig_v, ax_v = plt.subplots(figsize=(5, 3))
            found_data = False
            for mk_name in valitud_maakonnad:
                series = historical_v_df.query("Maakond == @mk_name")[["Aasta", haigus]].dropna().set_index("Aasta")[haigus]
                if not series.empty:
                    series.sort_index().plot(ax=ax_v, marker="o", linewidth=2, alpha=0.8, label=mk_name)
                    found_data = True
            
            if found_data:
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
                ax_v.set_title(f"Vaktsineerimine ajalugu ({haigus})", fontsize=12)
                plt.tight_layout()
                st.pyplot(fig_v)
            else:
                st.info(f"Vaktsineerimise ajaloolised andmed puuduvad haiguse {haigus} kohta valitud maakondadele.")

        # Haigestumus ajalugu (joon)
        with col2_hist:
            st.write("**Haigestumus (juhtumid)**")
            fig_h, ax_h = plt.subplots(figsize=(5, 3))
            found_data = False
            for mk_name in valitud_maakonnad:
                series = historical_h_df.query("Maakond == @mk_name")[["Aasta", haigus]].dropna().set_index("Aasta")[haigus]
                if not series.empty:
                    series.sort_index().plot(ax=ax_h, marker="o", linewidth=2, alpha=0.8, label=mk_name)
                    found_data = True
            
            if found_data:
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
                ax_h.set_title(f"Haigestumus ajalugu ({haigus})", fontsize=12)
                plt.tight_layout()
                st.pyplot(fig_h)
            else:
                st.info(f"Haigestumuse ajaloolised andmed puuduvad haiguse {haigus} kohta valitud maakondadele.")