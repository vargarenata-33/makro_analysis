"""
build_report.py
================
Legenerálja az index.html statikus riportot a makro_data.json alapján.

Változtatások a korábbi verzióhoz képest:
  - A Credit_facility_rate és Deposit_facility_rate (hitel-/betéti facilitás)
    teljesen kikerült a pipeline-ból -- sem a grafikonokban, sem a
    korrelációs mátrixban, sem az adattáblában nem szerepel.
  - A GDP mostantól növekedési ütemként (év/év %, GDP_YoY_pct) jelenik meg,
    a korábbi nominális szint (millió RON) helyett.
  - Új szakasz: interaktív lakossági hitelkockázati stressztest. Ez a
    szimuláció teljes egészében a böngészőben fut (sim.js), nem igényel
    Python-t futásidőben -- csak a jelenlegi alapkamat értékét kapja meg
    build-időben (CURRENT_POLICY_RATE), a szintetikus portfóliót és a
    számításokat maga a JS végzi.

Futtatás:
    python build_report.py

Ez felülírja az index.html-t a friss adatokkal. A sim.js-t NEM írja felül
(a szimulációs logika kézzel karbantartott, nem generált fájl) -- csak
belehelyettesíti az aktuális alapkamatot egy külön lépésben, lásd lent.

Nincs szükség plotly/streamlit Python-csomagra az index.html futtatásához;
a Plotly.js CDN-ről töltődik be a böngészőben. Ez a script maga is csak
pandas-t használ (adat-előkészítés), a grafikonokat pedig közvetlenül
Plotly.js JS-hívásokként írja bele a HTML-be.
"""

import os
import json
import pandas as pd

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MAKRO_DATA_PATH = os.path.join(DATA_DIR, "makro_data.json")
TEMPLATE_PATH = os.path.join(DATA_DIR, "index_template.html")
OUTPUT_PATH = os.path.join(DATA_DIR, "index.html")
SIM_JS_PATH = os.path.join(DATA_DIR, "sim.js")

START_QUARTER = "2010Q1"
END_QUARTER = "2026Q1"


def _load_makro_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_nbr_rates(path: str) -> pd.DataFrame:
    """NBR alapkamat (havi). A hitel-/betéti facilitás oszlopokat eldobjuk."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["NBR_Rates"])
    df["Date"] = pd.to_datetime(df["Date"])
    df["Policy_Rate"] = pd.to_numeric(df["Policy_Rate"], errors="coerce")
    return df[["Date", "Policy_Rate"]].sort_values("Date").reset_index(drop=True)


def load_hicp(path: str) -> pd.DataFrame:
    data = _load_makro_json(path)
    df = pd.DataFrame(data["HICP"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def load_hpi(path: str) -> pd.DataFrame:
    data = _load_makro_json(path)
    df = pd.DataFrame(data["HPI"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def load_gdp_growth(path: str) -> pd.DataFrame:
    """GDP -- a nominális szint helyett év/év %-os növekedési ütemet adunk vissza."""
    data = _load_makro_json(path)
    df = pd.DataFrame(data["GDP"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["GDP_YoY_pct"] = df["GDP_current_prices"].pct_change(4) * 100
    return df[["Date", "GDP_YoY_pct"]]


def monthly_to_quarterly(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    d = df.copy()
    d["Quarter"] = pd.PeriodIndex(d[date_col], freq="Q")
    numeric_cols = d.select_dtypes("number").columns
    q = d.groupby("Quarter")[numeric_cols].mean().reset_index()
    q["Date"] = q["Quarter"].dt.to_timestamp()
    return q.drop(columns="Quarter")[["Date", *numeric_cols]]


def filter_period(df: pd.DataFrame, start: str = START_QUARTER, end: str = END_QUARTER,
                   date_col: str = "Date") -> pd.DataFrame:
    start_ts = pd.Period(start, freq="Q").to_timestamp()
    end_ts = pd.Period(end, freq="Q").to_timestamp()
    mask = (df[date_col] >= start_ts) & (df[date_col] <= end_ts)
    return df.loc[mask].reset_index(drop=True)


def build_final_df() -> pd.DataFrame:
    nbr = monthly_to_quarterly(load_nbr_rates(MAKRO_DATA_PATH))
    hicp = monthly_to_quarterly(load_hicp(MAKRO_DATA_PATH))
    hpi = load_hpi(MAKRO_DATA_PATH)
    gdp = load_gdp_growth(MAKRO_DATA_PATH)

    frames = [filter_period(nbr), filter_period(hicp), filter_period(hpi), filter_period(gdp)]
    final_df = frames[0]
    for f in frames[1:]:
        final_df = final_df.merge(f, on="Date", how="outer")
    return final_df.sort_values("Date").reset_index(drop=True)


COLS = ["Policy_Rate", "HICP_MoM_pct", "HPI_QoQ_pct", "GDP_YoY_pct"]
LABELS = {
    "Policy_Rate": "Alapkamat (%)",
    "HICP_MoM_pct": "HICP infláció (havi %)",
    "HPI_QoQ_pct": "Lakásárindex (n/n %)",
    "GDP_YoY_pct": "GDP növekedés (év/év %)",
}


def fmt(v, dec=2):
    return "—" if pd.isna(v) else f"{v:.{dec}f}"


def main():
    final_df = build_final_df()

    chart_data = {"dates": final_df["Date"].dt.strftime("%Y-%m-%d").tolist()}
    for c in COLS:
        chart_data[c] = [None if pd.isna(v) else round(float(v), 4) for v in final_df[c]]

    corr = final_df[COLS].corr(numeric_only=True)
    chart_data["corr_labels"] = [LABELS[c] for c in COLS]
    chart_data["corr_matrix"] = corr.round(3).values.tolist()

    latest_policy = final_df.dropna(subset=["Policy_Rate"]).iloc[-1]
    latest_hicp = final_df.dropna(subset=["HICP_MoM_pct"]).iloc[-1]
    latest_hpi = final_df.dropna(subset=["HPI_QoQ_pct"]).iloc[-1]
    latest_gdp = final_df.dropna(subset=["GDP_YoY_pct"]).iloc[-1]
    ticker = {
        "policy_rate": round(float(latest_policy["Policy_Rate"]), 2),
        "hicp_mom": round(float(latest_hicp["HICP_MoM_pct"]), 2),
        "hpi_qoq": round(float(latest_hpi["HPI_QoQ_pct"]), 1),
        "gdp_yoy": round(float(latest_gdp["GDP_YoY_pct"]), 1),
    }

    table_df = final_df.tail(12).copy()
    table_df["Date"] = table_df["Date"].dt.strftime("%Y-%m")
    rows_html = ""
    for _, r in table_df[["Date", *COLS]].iloc[::-1].iterrows():
        cells = (
            f"<td>{r['Date']}</td>"
            f"<td>{fmt(r['Policy_Rate'])}</td>"
            f"<td>{fmt(r['HICP_MoM_pct'])}</td>"
            f"<td>{fmt(r['HPI_QoQ_pct'], 1)}</td>"
            f"<td>{fmt(r['GDP_YoY_pct'], 1)}</td>"
        )
        rows_html += f"<tr>{cells}</tr>"

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    repl = {
        "__DATES__": json.dumps(chart_data["dates"]),
        "__POLICY__": json.dumps(chart_data["Policy_Rate"]),
        "__HICP__": json.dumps(chart_data["HICP_MoM_pct"]),
        "__HPI__": json.dumps(chart_data["HPI_QoQ_pct"]),
        "__GDP__": json.dumps(chart_data["GDP_YoY_pct"]),
        "__CORR_LABELS__": json.dumps(chart_data["corr_labels"], ensure_ascii=False),
        "__CORR_MATRIX__": json.dumps(chart_data["corr_matrix"]),
        "__TICK_POLICY__": f"{ticker['policy_rate']:.2f}",
        "__TICK_HICP__": f"{ticker['hicp_mom']:+.2f}",
        "__TICK_HPI__": f"{ticker['hpi_qoq']:+.1f}",
        "__TICK_GDP__": f"{ticker['gdp_yoy']:+.1f}",
        "__TABLE_ROWS__": rows_html,
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    # sim.js: csak az aktuális alapkamatot cseréljük bele (a fájl maga kézzel
    # karbantartott, nem generáljuk újra minden sorát)
    with open(SIM_JS_PATH, "r", encoding="utf-8") as f:
        simjs = f.read()
    if "__CURRENT_POLICY_RATE__" in simjs:
        simjs = simjs.replace("__CURRENT_POLICY_RATE__", str(ticker["policy_rate"]))
        with open(SIM_JS_PATH, "w", encoding="utf-8") as f:
            f.write(simjs)

    print(f"index.html frissítve -- {len(final_df)} negyedév, "
          f"utolsó alapkamat: {ticker['policy_rate']}%")


if __name__ == "__main__":
    main()
