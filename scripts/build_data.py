#!/usr/bin/env python3
"""
Build the long-history annual return series used by the Trinity re-run.

Source: Robert Shiller's "U.S. Stock Markets 1871-Present and CAPE Ratio"
workbook (ie_data.xls, https://shillerdata.com).  It carries, monthly since
January 1871:

  * S&P Composite price, dividends, CPI, 10-year Treasury yield (GS10)
  * a real total-return price index for stocks (col J)
  * a real total-return index for a constant-maturity 10-year Treasury
    bond (col S, "Real Total Bond Returns")

We convert both real indices back to nominal with the CPI column, then take
January-to-January annual returns.  Year Y is "January Y -> January Y+1", so
the last complete year is the last one for which the following January is
present in the file.

Outputs (relative to repo root):

  data/shiller_monthly.csv   month, cpi, stock_tr_index, bond_tr_index (nominal)
  data/shiller_annual.csv    year, stock_nom, bond_nom, cpi (annual %)

Run scripts/build_markets.py afterwards to fold this into data/markets.*

Usage:
  python3 scripts/build_data.py                  # download latest ie_data.xls
  python3 scripts/build_data.py path/to/ie_data.xls
"""
import io
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

# shillerdata.com rotates the blob URL when the file is updated.  Try the
# current one first, then the historic Yale mirror.
URLS = [
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/70fec4f5-727f-4e53-b5f1-179af109c5fa/ie_data.xls",
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls",
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
]

# 0-based column positions in the "Data" sheet (see docstring in the sheet).
COL_DATE, COL_P, COL_D, COL_E, COL_CPI, COL_GS10 = 0, 1, 2, 3, 4, 6
COL_REAL_TR_PRICE = 9      # "Real Total Return Price"
COL_REAL_BOND_TR = 18      # "Real Total Bond Returns"


def fetch_workbook(path_or_none):
    if path_or_none:
        with open(path_or_none, "rb") as f:
            return f.read(), os.path.basename(path_or_none)
    last_err = None
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                blob = r.read()
            if blob[:4] == b"\xd0\xcf\x11\xe0":      # OLE2 signature => real .xls
                return blob, url
            last_err = f"{url}: not an .xls file"
        except Exception as e:                       # noqa: BLE001
            last_err = f"{url}: {e}"
    raise SystemExit(f"Could not download ie_data.xls ({last_err})")


def parse_monthly(blob):
    raw = pd.read_excel(io.BytesIO(blob), sheet_name="Data", header=None)
    # Data rows have a numeric "YYYY.MM" in column 0.
    date = pd.to_numeric(raw.iloc[:, COL_DATE], errors="coerce")
    rows = raw[date.notna() & (date >= 1871)].copy()
    d = rows.iloc[:, COL_DATE].astype(float)
    year = d.astype(int)
    # Shiller writes October as 1871.1 (i.e. .10) -> round to recover month.
    month = ((d - year) * 100).round().astype(int)
    out = pd.DataFrame({
        "year": year.values,
        "month": month.values,
        "price": pd.to_numeric(rows.iloc[:, COL_P], errors="coerce").values,
        "dividend": pd.to_numeric(rows.iloc[:, COL_D], errors="coerce").values,
        "cpi": pd.to_numeric(rows.iloc[:, COL_CPI], errors="coerce").values,
        "gs10": pd.to_numeric(rows.iloc[:, COL_GS10], errors="coerce").values,
        "real_stock_tr": pd.to_numeric(rows.iloc[:, COL_REAL_TR_PRICE], errors="coerce").values,
        "real_bond_tr": pd.to_numeric(rows.iloc[:, COL_REAL_BOND_TR], errors="coerce").values,
    })
    out = out.dropna(subset=["cpi", "real_stock_tr", "real_bond_tr"]).reset_index(drop=True)
    cpi0 = out.loc[0, "cpi"]
    # Real index * (CPI_t / CPI_0) = nominal index (both indices are 1871.01 = base).
    out["stock_tr_index"] = out["real_stock_tr"] * out["cpi"] / cpi0
    out["bond_tr_index"] = out["real_bond_tr"] * out["cpi"] / cpi0
    out["stock_tr_index"] /= out.loc[0, "stock_tr_index"]
    out["bond_tr_index"] /= out.loc[0, "bond_tr_index"]
    return out


def to_annual(m):
    jan = m[m["month"] == 1].set_index("year")
    years = sorted(jan.index)
    rows = []
    for y in years:
        if y + 1 not in jan.index:
            continue
        a, b = jan.loc[y], jan.loc[y + 1]
        rows.append({
            "year": int(y),
            "stock_nom": round((b["stock_tr_index"] / a["stock_tr_index"] - 1) * 100, 4),
            "bond_nom": round((b["bond_tr_index"] / a["bond_tr_index"] - 1) * 100, 4),
            "cpi": round((b["cpi"] / a["cpi"] - 1) * 100, 4),
        })
    return pd.DataFrame(rows)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    blob, where = fetch_workbook(src)
    monthly = parse_monthly(blob)
    annual = to_annual(monthly)
    os.makedirs(DATA_DIR, exist_ok=True)
    monthly_out = monthly[["year", "month", "price", "dividend", "cpi", "gs10",
                           "stock_tr_index", "bond_tr_index"]]
    monthly_out.to_csv(os.path.join(DATA_DIR, "shiller_monthly.csv"), index=False,
                       float_format="%.6f")
    annual.to_csv(os.path.join(DATA_DIR, "shiller_annual.csv"), index=False)
    last_month = f"{int(monthly.iloc[-1]['year'])}-{int(monthly.iloc[-1]['month']):02d}"
    print(f"source: {where}")
    print(f"monthly rows: {len(monthly)}  (through {last_month})")
    print(f"annual years: {annual['year'].min()}-{annual['year'].max()}  ({len(annual)} years)")
    print(annual.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
