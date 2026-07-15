# Román Makrogazdasági Ledger

Negyedévesített makrogazdasági idősorok (NBR kamatlábak, Eurostat HICP-infláció,
lakásárindex, GDP) egyesítve, korrelációs elemzéssel és két megjelenítési
móddal: egy élő **Streamlit** dashboard és egy önálló, statikus **HTML** riport.

## Tartalom

| Fájl              | Szerep                                                                 |
|--------------------|------------------------------------------------------------------------|
| `main.py`          | Adatpipeline + interaktív Streamlit webalkalmazás                     |
| `makro_data.json`  | A 4 forrás egyesítve, 4 blokkban (`NBR_Rates`, `HICP`, `HPI`, `GDP`)   |
| `style.css`        | Közös design rendszer ("ledger" téma) -- a Streamlit appba injektálva és az `index.html`-hez linkelve |
| `index.html`       | Önálló, statikus interaktív riport (nem igényel szervert/Streamlitet) |
| `build_report.py`  | Az `index.html`-t generáló script -- akkor futtasd újra, ha a `makro_data.json` frissül |

## Adatok

| Blokk       | Gyakoriság | Mértékegység                  | Forrás   |
|-------------|-----------|--------------------------------|----------|
| `NBR_Rates` | havi      | % p.a. (alapkamat, hitel-/betéti facilitás) | Banca Naţională a României |
| `HICP`      | havi      | havi %-os változás             | Eurostat (`prc_hicp_mmor`) |
| `HPI`       | negyedéves| negyedéves %-os változás       | Eurostat (`prc_hpi_q`) |
| `GDP`       | negyedéves| millió RON, folyó áron          | Eurostat (`tipsna15`) |

## Adatpipeline (`main.py`)

1. **Beolvasás** -- a `makro_data.json` 4 blokkja `pandas.DataFrame`-mé alakítva.
2. **Negyedévesítés** -- a havi sorozatok (`NBR_Rates`, `HICP`) negyedéves
   átlaggal kerülnek negyedéves gyakoriságúra (`monthly_to_quarterly`).
3. **Szűrés** -- minden sorozat a **2010 Q1 -- 2026 Q1** időszakra szűrve
   (`filter_period`).
4. **Egyesítés** -- a 4 tábla `Date` oszlop mentén `outer` merge-elve
   egy közös `final_df` táblázatba.
5. **Korreláció** -- `final_df.corr()` + Plotly hőtérkép (`build_correlation_heatmap`).

## Futtatás

### Élő Streamlit dashboard

```bash
pip install pandas plotly streamlit
streamlit run main.py
```

Ez megnyit egy böngészőablakot (`http://localhost:8501`), 3 füllel:
idősor-grafikon (kiválasztható mutatókkal), korrelációs hőtérkép, és a
nyers `final_df` tábla CSV-letöltési lehetőséggel.

A `style.css` tartalma automatikusan beinjektálódik az oldalba
(`inject_css()` függvény), így a Streamlit alap kinézete helyett a
projekt saját "ledger" designját kapod.

### Statikus HTML riport

Az `index.html` önmagában, szerver nélkül is megnyitható bármelyik
böngészőben (dupla kattintás, vagy `open index.html` / `start index.html`),
feltéve hogy a `style.css` ugyanabban a mappában van. A benne lévő Plotly
grafikonok interaktívak (zoom, hover, legend-kikapcsolás), de az adatok
build-időben be vannak égetve -- ha a `makro_data.json` változik, a riportot
újra kell generálni:

```bash
python build_report.py
```

Ez felülírja az `index.html`-t a friss adatokkal.

## Design

A `style.css` egy "ledger" (jegybanki könyvelési napló) vizuális nyelvet
követ: mély tintakék háttér, arany ékezetszín a kamatlábakhoz, monospace
számok, szerif címsorok. Ugyanez a token-rendszer szolgálja ki mind a
Streamlit appot (CSS injektálással), mind a statikus `index.html`-t
(közvetlen `<link>`), így a két felület vizuálisan egységes marad.

## Függőségek

```
pandas
plotly
streamlit
```

(A `build_report.py` csak build-időben kell, futásidőben az `index.html`
semmilyen Python-függőséget nem igényel -- a Plotly.js CDN-ről töltődik be.)
