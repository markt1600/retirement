#!/usr/bin/env python3
"""
Build the multi-market annual series (data/markets.csv, data/markets.js).

Markets
  us       S&P Composite TR + 10-yr Treasury TR + US CPI, 1871-2025 (Shiller,
           from data/shiller_annual.csv - run scripts/build_data.py first)
  japan    JST Macrohistory JPN: eq_tr, bond_tr, cpi, 1886-2020,
           extended 2021+ with data/intl_extension.csv
  uk       JST GBR 1871-2020 + extension
  germany  JST DEU 1870-2020 + extension (bond_tr missing 1944-48)
  world    "VWRA-like" global equity proxy in USD:
             1872-1969  GDP-weighted average of the USD total return of all
                        JST countries with data that year (weights = previous
                        year's nominal GDP converted at the previous year's
                        USD rate; returns converted with year-end rates)
             1970-2025  MSCI World (USD, net TR) from data/msci_world_usd.csv
           bonds and CPI are the US series (a USD investor holding a global
           equity fund plus Treasuries).

JST = Jordà-Schularick-Taylor Macrohistory Database R6 (macrohistory.net),
CC BY-NC-SA 4.0.  Cite: Jordà, Schularick & Taylor (2017), "Macrofinancial
History and the New Business Cycle Facts", NBER Macroeconomics Annual 2016;
and Jordà, Knoll, Kuvshinov, Schularick & Taylor (2019), "The Rate of Return
on Everything, 1870-2015", QJE.

Usage:
  python3 scripts/build_markets.py                    # downloads JST R6
  python3 scripts/build_markets.py path/JSTdatasetR6.xlsx
"""
import csv
import io
import json
import math
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
JST_URL = "https://www.macrohistory.net/app/download/9834512569/JSTdatasetR6.xlsx?t=1763503850"

JST_MARKETS = {
    "japan":   ("JPN", "Japan",          "JPY", "JST Japan equity TR (Nikkei/TSE-based)", "JST Japan long-term govt bond TR"),
    "uk":      ("GBR", "United Kingdom", "GBP", "JST UK equity TR (FTSE All-Share-based)", "JST UK consol / gilt TR"),
    "germany": ("DEU", "Germany",        "DEM/EUR", "JST Germany equity TR (CDAX-based)",  "JST Germany long-term govt bond TR"),
}


def load_jst(path_or_none):
    if path_or_none:
        with open(path_or_none, "rb") as f:
            blob = f.read()
        src = os.path.basename(path_or_none)
    else:
        req = urllib.request.Request(JST_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            blob = r.read()
        src = "macrohistory.net JSTdatasetR6.xlsx"
    return pd.read_excel(io.BytesIO(blob), sheet_name=0), src


def read_csv(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))


def nz(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), 4)


def jst_market(jst, iso, ext_rows):
    d = jst[jst.iso == iso].set_index("year").sort_index()
    out = {}
    for y in d.index:
        if y - 1 not in d.index:
            continue
        cpi = None
        if pd.notna(d.loc[y, "cpi"]) and pd.notna(d.loc[y - 1, "cpi"]) and d.loc[y - 1, "cpi"] > 0:
            cpi = (d.loc[y, "cpi"] / d.loc[y - 1, "cpi"] - 1) * 100
        stock = d.loc[y, "eq_tr"] * 100 if pd.notna(d.loc[y, "eq_tr"]) else None
        bond = d.loc[y, "bond_tr"] * 100 if pd.notna(d.loc[y, "bond_tr"]) else None
        out[int(y)] = (nz(stock), nz(bond), nz(cpi))
    for r in ext_rows:
        y = int(r["year"])
        if y not in out:
            out[y] = (nz(float(r["stock_nom"])), nz(float(r["bond_nom"])), nz(float(r["cpi"])))
    # drop leading years with no equity data
    years = sorted(y for y in out if out[y][0] is not None)
    return {y: out[y] for y in range(years[0], years[-1] + 1) if y in out}


def world_proxy(jst, msci_rows):
    """GDP-weighted USD equity return across JST countries, then MSCI World."""
    eq = jst.pivot(index="year", columns="iso", values="eq_tr")
    xr = jst.pivot(index="year", columns="iso", values="xrusd")
    gdp = jst.pivot(index="year", columns="iso", values="gdp")
    msci = {int(r["year"]): float(r["msci_world_usd_tr_pct"]) for r in msci_rows}
    first_msci = min(msci)
    out, ncountries = {}, {}
    for y in range(int(eq.index.min()) + 1, first_msci):
        rs, ws = [], []
        for c in eq.columns:
            r, x0, x1, g = eq.loc[y, c], xr.loc[y - 1, c], xr.loc[y, c], gdp.loc[y - 1, c]
            if any(pd.isna(v) for v in (r, x0, x1, g)) or x0 <= 0 or x1 <= 0 or g <= 0:
                continue
            rs.append((1 + r) * x0 / x1 - 1)      # local TR converted to USD
            ws.append(g / x0)                      # previous-year GDP in USD
        if not rs:
            continue
        tot = sum(ws)
        out[y] = round(100 * sum(r * w / tot for r, w in zip(rs, ws)), 4)
        ncountries[y] = len(rs)
    for y, v in msci.items():
        out[y] = v
        ncountries[y] = 0
    return out, ncountries


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    jst, jst_src = load_jst(src)
    shiller = {int(r["year"]): (float(r["stock_nom"]), float(r["bond_nom"]), float(r["cpi"]))
               for r in read_csv("shiller_annual.csv")}
    ext = read_csv("intl_extension.csv")
    msci_rows = read_csv("msci_world_usd.csv")

    markets = {}
    markets["us"] = {
        "label": "United States", "currency": "USD",
        "stock_label": "S&P Composite total return (Shiller)",
        "bond_label": "10-year Treasury total return (Shiller)",
        "cpi_label": "US CPI",
        "notes": "Shiller ie_data.xls, January-to-January annual returns.",
        "series": shiller,
    }
    for key, (iso, label, ccy, slab, blab) in JST_MARKETS.items():
        rows = [r for r in ext if r["market"] == key]
        ext_years = sorted(int(r["year"]) for r in rows)
        markets[key] = {
            "label": label, "currency": ccy,
            "stock_label": slab, "bond_label": blab, "cpi_label": f"{label} CPI (JST)",
            "notes": (f"JST Macrohistory R6 through 2020; {ext_years[0]}-{ext_years[-1]} extended with the "
                      f"MSCI/local-index series kept in data/intl_extension.csv. Local currency, nominal."),
            "series": jst_market(jst, iso, rows),
        }
    proxy, ncty = world_proxy(jst, msci_rows)
    first_msci = min(int(r["year"]) for r in msci_rows)
    series = {}
    for y in sorted(proxy):
        if y in shiller:
            series[y] = (proxy[y], shiller[y][1], shiller[y][2])
    markets["world"] = {
        "label": "World equity proxy (USD)", "currency": "USD",
        "stock_label": f"GDP-weighted JST 18-country USD equity TR to {first_msci - 1}, MSCI World USD from {first_msci}",
        "bond_label": "10-year Treasury total return (Shiller)",
        "cpi_label": "US CPI",
        "notes": ("Stand-in for a global cap-weighted fund such as VWRA / FTSE All-World. Pre-1970 weights are "
                  "previous-year nominal GDP in USD, not market cap; wartime and capital-control years use official "
                  "exchange rates, so 1914-1949 USD returns are indicative only."),
        "series": series,
        "n_countries": ncty,
    }

    # --- write outputs ---
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "markets.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market", "year", "stock_nom", "bond_nom", "cpi"])
        for key, m in markets.items():
            for y in sorted(m["series"]):
                s, b, c = m["series"][y]
                w.writerow([key, y, "" if s is None else s, "" if b is None else b, "" if c is None else c])

    payload = {}
    for key, m in markets.items():
        yrs = sorted(m["series"])
        payload[key] = {
            "label": m["label"], "currency": m["currency"],
            "stock_label": m["stock_label"], "bond_label": m["bond_label"], "cpi_label": m["cpi_label"],
            "notes": m["notes"], "first_year": yrs[0], "last_year": yrs[-1],
            "stock": {y: m["series"][y][0] for y in yrs},
            "bond": {y: m["series"][y][1] for y in yrs},
            "cpi": {y: m["series"][y][2] for y in yrs},
        }
    with open(os.path.join(DATA, "markets.js"), "w") as f:
        f.write("// Generated by scripts/build_markets.py - do not edit by hand.\n")
        f.write(f"// Annual %, nominal, local currency. Sources: Shiller ie_data.xls; {jst_src}; "
                "data/intl_extension.csv; data/msci_world_usd.csv.\n")
        f.write("const MARKETS = " + json.dumps(payload, indent=1) + ";\n")

    for key, m in markets.items():
        yrs = sorted(m["series"])
        gaps = [y for y in yrs if any(v is None for v in m["series"][y])]
        print(f"{key:8s} {yrs[0]}-{yrs[-1]}  years with a gap: {gaps if gaps else 'none'}")


if __name__ == "__main__":
    main()
