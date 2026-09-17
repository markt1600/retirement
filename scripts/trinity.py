#!/usr/bin/env python3
"""
Trinity-style portfolio success rates on long-history S&P 500 data.

The original Trinity study (Cooley, Hubbard & Walz, AAII Journal, Feb 1998)
used Ibbotson annual data 1926-1995, five stock/bond mixes (100/75/50/25/0),
payout periods of 15, 20, 25 and 30 years, first-year withdrawal rates of
3%-12%, and two withdrawal rules: a fixed nominal dollar amount, or a
dollar amount that grows with CPI.  A period "succeeds" if the portfolio
still has a positive balance at the end of it.

This script reproduces that grid on long annual series (data/markets.csv,
built by scripts/build_data.py + scripts/build_markets.py) and extends the
payout periods to 35, 40, 45, 50 and 60 years, which is where a modern
early retiree actually lives.  Markets: us (Shiller 1871-2025), japan, uk,
germany (JST Macrohistory, local currency) and world (GDP-weighted global
equity proxy in USD spliced to MSCI World, with US bonds and CPI).

Mechanics (all configurable from the CLI):
  * annual steps, portfolio rebalanced to the target mix every year
  * withdrawal taken at the START of each year by default (--timing end
    for end-of-year), before that year's return is applied
  * inflation-adjusted rule: withdrawal_t = rate x initial x CPI_t / CPI_0
  * US: stocks = S&P Composite total return; bonds = 10-year Treasury total
    return (Shiller's constant-maturity series) - not the long-term
    corporate bonds Trinity used.  Other markets: JST equity and long-term
    government bond total returns in local currency.
  * windows that need a series in a year where it is missing (Japan
    equities 1946-47, German bonds 1944-48) are skipped, not failed
  * no fees or taxes

Usage examples:
  python3 scripts/trinity.py                              # full default run
  python3 scripts/trinity.py --start 1926 --end 1995      # Trinity replication
  python3 scripts/trinity.py --market japan --start 1886
  python3 scripts/trinity.py --periods 30,40,50,60 --rates 3,3.5,4,4.5,5
"""
import argparse
import csv
import os
import statistics
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "markets.csv")
MARKETS_JS = os.path.join(ROOT, "data", "markets.js")
RESULTS = os.path.join(ROOT, "results")

DEFAULT_PERIODS = [15, 20, 25, 30, 35, 40, 45, 50, 60]
DEFAULT_RATES = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
DEFAULT_ALLOCS = [100, 75, 50, 25, 0]
SWR_GRID = [x / 4 for x in range(4, 49)]        # 1.00% .. 12.00% in 0.25% steps


def load_series(market, path=DATA):
    years, stock, bond, cpi = [], [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["market"] != market:
                continue
            years.append(int(row["year"]))
            stock.append(float(row["stock_nom"]) / 100 if row["stock_nom"] != "" else None)
            bond.append(float(row["bond_nom"]) / 100 if row["bond_nom"] != "" else None)
            cpi.append(float(row["cpi"]) / 100 if row["cpi"] != "" else None)
    if not years:
        raise SystemExit(f"market '{market}' not found in {path}")
    return years, stock, bond, cpi


def market_meta(market):
    """Labels from data/markets.js (a JS constant wrapping JSON)."""
    try:
        with open(MARKETS_JS) as f:
            txt = f.read()
        body = txt[txt.index("const MARKETS = ") + len("const MARKETS = "):].rstrip().rstrip(";")
        import json
        return json.loads(body).get(market, {})
    except (OSError, ValueError):
        return {}


def run_window(stock, bond, cpi, i0, years, alloc, rate, inflation_adjusted, timing):
    """Simulate one payout period starting at index i0.  Returns terminal
    balance per 1.0 initial (nominal); <= 0 means failure; None means the
    window needs a series that has a gap, so it cannot be scored."""
    bal = 1.0
    w = rate
    a = alloc
    # Check the whole window for gaps first, so that a window is either
    # scored or skipped regardless of when it would have run out of money.
    for i in range(i0, i0 + years):
        if (a > 0 and stock[i] is None) or (a < 1 and bond[i] is None) or (inflation_adjusted and cpi[i] is None):
            return None
    for k in range(years):
        i = i0 + k
        if timing == "start":
            bal -= w
            if bal <= 0:
                return 0.0
        bal *= 1 + a * (stock[i] or 0) + (1 - a) * (bond[i] or 0)
        if timing == "end":
            bal -= w
            if bal <= 0:
                return 0.0
        if inflation_adjusted:
            w *= 1 + cpi[i]
    return bal


def success_table(series, start, end, periods, rates, allocs, inflation_adjusted, timing, market="us"):
    """Return list of result dicts, one per (period, alloc, rate)."""
    years, stock, bond, cpi = series
    idx = {y: i for i, y in enumerate(years)}
    out = []
    for p in periods:
        starts = [y for y in range(start, end - p + 2) if y in idx and (y + p - 1) in idx]
        if not starts:
            continue
        for alloc in allocs:
            a = alloc / 100
            for r in rates:
                fails, terminals, skipped = [], [], 0
                for y in starts:
                    t = run_window(stock, bond, cpi, idx[y], p, a, r / 100, inflation_adjusted, timing)
                    if t is None:
                        skipped += 1
                        continue
                    terminals.append(t)
                    if t <= 0:
                        fails.append(y)
                n = len(terminals)
                if n == 0:
                    continue
                out.append(OrderedDict(
                    market=market, sample_start=start, sample_end=end,
                    model="inflation_adjusted" if inflation_adjusted else "nominal",
                    timing=timing, period=p, stock_pct=alloc, rate_pct=r,
                    n_windows=n, n_skipped=skipped, n_success=n - len(fails),
                    success_pct=round(100 * (n - len(fails)) / n, 1),
                    median_terminal_per_1000=round(1000 * statistics.median(terminals), 0),
                    min_terminal_per_1000=round(1000 * min(terminals), 0),
                    failed_starts=" ".join(str(y) for y in fails),
                ))
    return out


def max_safe_rates(series, start, end, period, alloc, inflation_adjusted, timing, thresholds):
    """For each success threshold (percent), the highest rate on SWR_GRID whose
    success rate is >= threshold, scanning the grid once.  Because success is
    monotone in the rate, take the last grid point that still clears it."""
    rows = success_table(series, start, end, [period], SWR_GRID, [alloc], inflation_adjusted, timing)
    out = {}
    for t in thresholds:
        best = None
        for x in rows:
            if x["success_pct"] >= t:
                best = x["rate_pct"]
            else:
                break
        out[t] = best
    return out


def md_grid(rows, periods, rates, alloc):
    head = "| Payout period | " + " | ".join(f"{r:g}%" for r in rates) + " |"
    sep = "|---|" + "|".join("---:" for _ in rates) + "|"
    lines = [head, sep]
    by = {(x["period"], x["rate_pct"]): x for x in rows if x["stock_pct"] == alloc}
    for p in periods:
        cells = []
        n = None
        for r in rates:
            x = by.get((p, r))
            if x is None:
                cells.append("-")
            else:
                n = x["n_windows"]
                cells.append(f"{x['success_pct']:.0f}")
        if n is None:
            continue
        lines.append(f"| {p} yrs ({n} windows) | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def md_swr(series, start, end, periods, allocs, inflation_adjusted, timing):
    lines = ["| Payout period | " + " | ".join(f"{a}/{100-a}" for a in allocs) + " |",
             "|---|" + "|".join("---:" for _ in allocs) + "|"]
    for p in periods:
        cells = []
        for a in allocs:
            m = max_safe_rates(series, start, end, p, a, inflation_adjusted, timing, (100, 95))
            f = lambda v: "-" if v is None else f"{v:.2f}%"
            cells.append(f"{f(m[100])} / {f(m[95])}")
        if any(c != "- / -" for c in cells):
            lines.append(f"| {p} yrs | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def parse_list(s, cast=float):
    return [cast(x) for x in s.split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="us", choices=["us", "japan", "uk", "germany", "world"])
    ap.add_argument("--start", type=int, default=None, help="first start year of the sample (default: first year in data)")
    ap.add_argument("--end", type=int, default=None, help="last year of the sample (default: last year in data)")
    ap.add_argument("--periods", default=",".join(map(str, DEFAULT_PERIODS)))
    ap.add_argument("--rates", default=",".join(map(str, DEFAULT_RATES)))
    ap.add_argument("--allocs", default=",".join(map(str, DEFAULT_ALLOCS)), help="stock %% of each mix")
    ap.add_argument("--timing", choices=["start", "end"], default="start", help="withdrawal timing within the year")
    ap.add_argument("--label", default=None, help="basename for output files (default from sample years)")
    ap.add_argument("--out", default=RESULTS)
    ap.add_argument("--data", default=DATA)
    args = ap.parse_args()

    series = load_series(args.market, args.data)
    meta = market_meta(args.market)
    years = series[0]
    start = args.start or years[0]
    end = args.end or years[-1]
    periods = parse_list(args.periods, int)
    rates = [r if r != int(r) else int(r) for r in parse_list(args.rates)]
    allocs = parse_list(args.allocs, int)
    label = args.label or f"{args.market}_{start}-{end}"
    os.makedirs(args.out, exist_ok=True)

    all_rows = []
    md = [f"# Trinity-style success rates: {meta.get('label', args.market)}, sample {start}-{end}", "",
          f"Withdrawals at {args.timing} of year; annual rebalancing; "
          f"stocks = {meta.get('stock_label', 'stocks')}; bonds = {meta.get('bond_label', 'bonds')}; "
          f"inflation = {meta.get('cpi_label', 'CPI')}; no fees. "
          f"Cells are % of overlapping historical start years whose portfolio ended the "
          f"payout period with a positive balance; the window count in each row excludes "
          f"windows that cross a gap in the data.", ""]
    if meta.get("notes"):
        md += [f"_{meta['notes']}_", ""]
    for infl in (True, False):
        rows = success_table(series, start, end, periods, rates, allocs, infl, args.timing, args.market)
        all_rows += rows
        title = "Inflation-adjusted withdrawals" if infl else "Fixed nominal withdrawals"
        md += [f"## {title}", ""]
        for a in allocs:
            md += [f"### {a}% stocks / {100 - a}% bonds", "", md_grid(rows, periods, rates, a), ""]
        md += [f"### Highest withdrawal rate with 100% / 95% success ({title.lower()})", "",
               "Rate grid is 0.25% steps; '-' means even 1% failed the threshold.", "",
               md_swr(series, start, end, periods, allocs, infl, args.timing), ""]

    csv_path = os.path.join(args.out, f"success_rates_{label}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    md_path = os.path.join(args.out, f"trinity_{label}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md))
    print(f"wrote {csv_path} ({len(all_rows)} rows) and {md_path}")


if __name__ == "__main__":
    main()
