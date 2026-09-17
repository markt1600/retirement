#!/usr/bin/env python3
"""
Side-by-side Trinity results across markets (full history of each), written
to results/markets_comparison.md.  Inflation-adjusted withdrawals, start-of-
year timing, no fees.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trinity as T  # noqa: E402

MARKETS = ["us", "world", "uk", "germany", "japan"]
PERIODS = [30, 40, 50, 60]


def main():
    out = ["# Trinity across markets (full history, inflation-adjusted withdrawals)", "",
           "Success = share of overlapping historical start years whose portfolio was still positive at the "
           "end of the payout period.  Windows are annual, rebalanced yearly, withdrawal at the start of each "
           "year, no fees.  Local-currency returns, local bonds and local CPI for Japan/UK/Germany; USD, US "
           "Treasuries and US CPI for the US and the world proxy.  Window counts exclude windows that cross a "
           "gap in the data (Japan 1946-47 equities, Germany 1944-48 bonds).", ""]
    metas = {m: T.market_meta(m) for m in MARKETS}
    series = {m: T.load_series(m) for m in MARKETS}
    out += ["| Market | Sample | Equity series |", "|---|---|---|"]
    for m in MARKETS:
        y = series[m][0]
        out.append(f"| {metas[m].get('label', m)} | {y[0]}-{y[-1]} | {metas[m].get('stock_label', '')} |")
    out.append("")

    for alloc in (75, 50):
        for rate in (4, 3.5, 3):
            out += [f"## {rate}% withdrawal rate, {alloc}% stocks / {100 - alloc}% bonds", "",
                    "| Payout period | " + " | ".join(metas[m].get("label", m) for m in MARKETS) + " |",
                    "|---|" + "|".join("---:" for _ in MARKETS) + "|"]
            for p in PERIODS:
                cells = []
                for m in MARKETS:
                    y = series[m][0]
                    rows = T.success_table(series[m], y[0], y[-1], [p], [rate], [alloc], True, "start", m)
                    cells.append(f"{rows[0]['success_pct']:.0f}% ({rows[0]['n_windows']})" if rows else "-")
                out.append(f"| {p} yrs | " + " | ".join(cells) + " |")
            out.append("")

    for thr in (100, 95):
        out += [f"## Highest withdrawal rate with {thr}% success, 75/25 (0.25% grid)", "",
                "| Payout period | " + " | ".join(metas[m].get("label", m) for m in MARKETS) + " |",
                "|---|" + "|".join("---:" for _ in MARKETS) + "|"]
        for p in PERIODS:
            cells = []
            for m in MARKETS:
                y = series[m][0]
                r = T.max_safe_rates(series[m], y[0], y[-1], p, 75, True, "start", (thr,))[thr]
                cells.append("-" if r is None else f"{r:.2f}%")
            out.append(f"| {p} yrs | " + " | ".join(cells) + " |")
        out.append("")

    path = os.path.join(T.RESULTS, "markets_comparison.md")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
