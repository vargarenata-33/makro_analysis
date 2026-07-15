"""
main.py
=======
Interaktív gazdasági adatelemző webalkalmazás (Streamlit + Plotly).

Bemeneti fájl (ugyanabban a mappában legyen, mint ez a script):
    - makro_data.json   -- a 4 eredeti forrás egyesítve, 4 kulcs alatt:
          NBR_Rates  (NBR kamatlábak, havi)
          HICP       (HICP infláció, havi, Eurostat)
          HPI        (Lakásárindex, negyedéves, Eurostat)
          GDP        (GDP, negyedéves, Eurostat)
      Minden kulcs alatt egy rekordlista van, pl.:
          "NBR_Rates": [{"Date": "2005-01-01", "Policy_Rate": 16.5, ...}, ...]

Futtatás (Cursor terminálban):
    pip install pandas plotly streamlit
    streamlit run main.py

A script:
    1) beolvassa a makro_data.json 4 blokkját pandas-szal,
    2) minden sorozatot negyedéves gyakoriságúra konvertál (havi adatok -> negyedéves átlag),
    3) 2010 Q1 - 2026 Q1 közötti időszakra szűri az adatokat,
    4) egyesíti őket egy közös 'Date' oszlop mentén (final_df),
    5) korrelációs mátrixot és Plotly hőtérképet készít,
    6) mindezt egy interaktív Streamlit weboldalon jeleníti meg.
"""

import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Beállítások
# ---------------------------------------------------------------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MAKRO_DATA_PATH = os.path.join(DATA_DIR, "makro_data.json")
CSS_PATH = os.path.join(DATA_DIR, "style.css")

START_QUARTER = "2010Q1"
END_QUARTER = "2026Q1"


def inject_css(path: str) -> None:
    """Betölti a style.css tartalmát és beinjektálja az oldalba."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 1) Beolvasó függvények -- mind a makro_data.json megfelelő blokkjából
# ---------------------------------------------------------------------------
def _load_makro_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_nbr_rates(path: str) -> pd.DataFrame:
    """NBR kamatlábak (havi gyakoriságú) a 'NBR_Rates' blokkból."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["NBR_Rates"])
    df["Date"] = pd.to_datetime(df["Date"])
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("Date").reset_index(drop=True)


def load_hicp(path: str) -> pd.DataFrame:
    """HICP infláció (havi, %-os havi változás) a 'HICP' blokkból."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["HICP"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def load_hpi(path: str) -> pd.DataFrame:
    """Lakásárindex (negyedéves, %-os negyedéves változás) a 'HPI' blokkból."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["HPI"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def load_gdp(path: str) -> pd.DataFrame:
    """GDP (negyedéves, folyó áras, millió RON) a 'GDP' blokkból."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["GDP"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2) Havi -> negyedéves konverzió (negyedéves átlag)
# ---------------------------------------------------------------------------
def monthly_to_quarterly(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    d = df.copy()
    d["Quarter"] = pd.PeriodIndex(d[date_col], freq="Q")
    numeric_cols = d.select_dtypes("number").columns
    q = d.groupby("Quarter")[numeric_cols].mean().reset_index()
    q["Date"] = q["Quarter"].dt.to_timestamp()
    return q.drop(columns="Quarter")[["Date", *numeric_cols]]


# ---------------------------------------------------------------------------
# 3) Időszak szűrés (2010 Q1 - 2026 Q1)
# ---------------------------------------------------------------------------
def filter_period(df: pd.DataFrame, start: str = START_QUARTER, end: str = END_QUARTER,
                   date_col: str = "Date") -> pd.DataFrame:
    start_ts = pd.Period(start, freq="Q").to_timestamp()
    end_ts = pd.Period(end, freq="Q").to_timestamp()
    mask = (df[date_col] >= start_ts) & (df[date_col] <= end_ts)
    return df.loc[mask].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4) Teljes pipeline: beolvasás -> negyedévesítés -> szűrés -> egyesítés
# ---------------------------------------------------------------------------
@st.cache_data
def build_final_df() -> pd.DataFrame:
    nbr = monthly_to_quarterly(load_nbr_rates(MAKRO_DATA_PATH))
    hicp = monthly_to_quarterly(load_hicp(MAKRO_DATA_PATH))
    hpi = load_hpi(MAKRO_DATA_PATH)          # már negyedéves
    gdp = load_gdp(MAKRO_DATA_PATH)          # már negyedéves

    frames = [filter_period(nbr), filter_period(hicp), filter_period(hpi), filter_period(gdp)]

    final_df = frames[0]
    for f in frames[1:]:
        final_df = final_df.merge(f, on="Date", how="outer")

    return final_df.sort_values("Date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5) Korrelációs mátrix + Plotly hőtérkép
# ---------------------------------------------------------------------------
def build_correlation_heatmap(final_df: pd.DataFrame) -> go.Figure:
    corr = final_df.drop(columns="Date").corr(numeric_only=True)

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        aspect="auto",
        title="Korrelációs mátrix (2010 Q1 - 2026 Q1, negyedéves adatok)",
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=60, b=40),
        height=550,
    )
    return fig, corr


# ---------------------------------------------------------------------------
# 6) Streamlit weboldal
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="RO Makrogazdasági Ledger", layout="wide")
    inject_css(CSS_PATH)

    st.markdown('<p class="report-eyebrow">Makrogazdasági jegyzék · Románia</p>', unsafe_allow_html=True)
    st.title("Román makrogazdasági mutatók")
    st.caption(
        "Adatforrások: NBR kamatlábak, Eurostat HICP infláció, "
        "Eurostat lakásárindex (HPI), Eurostat GDP | Időszak: 2010 Q1 - 2026 Q1, negyedéves bontásban"
    )

    final_df = build_final_df()

    tab1, tab2, tab3 = st.tabs(["📈 Idősorok", "🔥 Korrelációs hőtérkép", "📋 Adattábla"])

    # --- Idősor tab ---
    with tab1:
        numeric_cols = [c for c in final_df.columns if c != "Date"]
        selected = st.multiselect(
            "Válaszd ki a megjelenítendő mutatókat:",
            options=numeric_cols,
            default=numeric_cols,
        )
        if selected:
            fig_ts = go.Figure()
            for col in selected:
                fig_ts.add_trace(go.Scatter(
                    x=final_df["Date"], y=final_df[col],
                    mode="lines+markers", name=col,
                ))
            fig_ts.update_layout(
                height=550,
                xaxis_title="Dátum",
                yaxis_title="Érték",
                legend_title="Mutató",
                hovermode="x unified",
            )
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("Válassz ki legalább egy mutatót a fenti listából.")

    # --- Korreláció tab ---
    with tab2:
        fig_heatmap, corr = build_correlation_heatmap(final_df)
        st.plotly_chart(fig_heatmap, use_container_width=True)
        with st.expander("Korrelációs mátrix nyers értékei"):
            st.dataframe(corr.style.format("{:.3f}"), use_container_width=True)

    # --- Adattábla tab ---
    with tab3:
        st.dataframe(final_df, use_container_width=True)
        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "final_df letöltése CSV-ként",
            data=csv,
            file_name="final_df.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
