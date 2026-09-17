# Safe withdrawal rates on long histories (Trinity methodology)

Two static pages, no build step. Open them from disk or via GitHub Pages.

| Page | What it does |
|---|---|
| [`index.html`](index.html) | **Safe withdrawal rate.** Choose a time horizon and the markets to test (US, world proxy, UK, Germany, Japan). For each market the page replays every overlapping historical window of that length with the Trinity study's rules and reports the highest first-year withdrawal rate that survived the required share of windows, plus the 4%-rule success rate and a success-vs-rate chart. Optional portfolio value turns the rate into a first-year amount. An **outcomes-by-age** chart shows, for one market at a chosen rate, the share of windows that are broke, below the start, 1–2×, 2–5× or above 5× in real terms at each age, with an optional mortality wedge (SSA period life table) and the probability of running out while still alive. |
| [`trinity.html`](trinity.html) | **Full Trinity grids.** The classic period × withdrawal-rate success tables for every stock/bond mix, one market at a time, with presets for the original 1926–1995 sample. |

Both pages compute everything in the browser from `data/markets.js`.

## Trinity re-run: what was done

Cooley, Hubbard & Walz (1998) took Ibbotson annual data for 1926–1995, five stock/bond
mixes, payout periods of 15–30 years and first-year withdrawal rates of 3–12%, and counted
how often a portfolio was still positive at the end of every overlapping historical window.
This repo repeats that, with three changes:

1. **Longer data.** US stocks, bonds and CPI come from Shiller's monthly series (1871→),
   turned into January-to-January annual returns. The 1926–1995 slice reproduces Ibbotson's
   averages (stocks 10.5%/yr, CPI 3.1%) and the published Trinity table to within a few points.
2. **Longer periods.** 35, 40, 45, 50 and 60-year payout periods, which is what a 40-year-old
   retiree actually needs. Long windows overlap heavily (96 sixty-year windows contain only
   two or three independent histories), so treat them as "what has happened", not probabilities.
3. **Other markets.** Japan, UK and Germany from the Jordà-Schularick-Taylor Macrohistory
   Database (local equity and long-term government bond total returns, local CPI, 1870–2020,
   extended to 2025), plus a **world equity proxy** in USD: GDP-weighted USD returns of the 18
   JST countries to 1969, spliced to MSCI World from 1970, paired with US Treasuries and US CPI.
   That is the closest free long-history stand-in for a VWRA-style global fund.

Mechanics: annual steps, rebalanced yearly, withdrawal at the start of each year (switchable),
withdrawals either fixed in nominal terms or growing with CPI, a 0.8%/yr fee deducted from the
whole portfolio (editable on the page and via `--fees`; the original study and the replication
below use none), success = positive balance at the end. Bonds are 10-year Treasuries / long government
bonds, not the long-term corporates Trinity used, which makes bond-heavy rows slightly worse.

**Optional spending flexibility** (both pages and the CLI; off by default, not part of the original
study). Two rules, each with its own switch:

- *Base rule:* in any year the portfolio is below X% of its starting value (real terms under the
  inflation-adjusted rule, nominal under the fixed rule), cut that year's withdrawal by Y%.
  Spending returns to the full amount as soon as the portfolio is back above the line.
- *Early-years rule* (sequence-of-returns risk): a second, usually higher line and its own cut that
  apply only during the first N years.

When both trigger in the same year the larger cut is used, not both. The safe rate reported is the
full, uncut starting rate. For the US with a 75/25 mix and 0.8% fees, a 20% cut below 80% lifts the
4% rule from 80% to 98% of 40-year windows and from 73% to 93% of 60-year windows
([`results/trinity_us_1871-2025_cut20below80.md`](results/trinity_us_1871-2025_cut20below80.md));
adding a 10% cut below 90% in the first 10 years changes little on top of that
([`results/trinity_us_1871-2025_cut20below80_early10below90for10.md`](results/trinity_us_1871-2025_cut20below80_early10below90for10.md)).
CLI: `--cut-pct 20 --cut-below 80 --early-cut-pct 10 --early-cut-below 90 --early-years 10`.

### Headline results (inflation-adjusted withdrawals, 0.8% fees, full history of each market)

Success rate at a 4% initial withdrawal, 75% stocks / 25% bonds. Window counts in brackets.

| Payout period | United States | World proxy (USD) | United Kingdom | Germany | Japan |
|---|---:|---:|---:|---:|---:|
| 30 yrs | 94% (126) | 82% (126) | 76% (126) | 74% (92) | 86% (80) |
| 40 yrs | 80% (116) | 71% (116) | 54% (116) | 62% (72) | 92% (60) |
| 50 yrs | 71% (106) | 53% (106) | 37% (106) | 54% (52) | 88% (40) |
| 60 yrs | 73% (96) | 45% (96) | 30% (96) | 34% (32) | 80% (20) |

Highest withdrawal rate that succeeded in at least 95% of windows, 75/25:

| Payout period | United States | World proxy (USD) | United Kingdom | Germany | Japan |
|---|---:|---:|---:|---:|---:|
| 30 yrs | 3.75% | 3.25% | 2.75% | – | 3.00% |
| 40 yrs | 3.50% | 3.00% | 2.25% | – | 3.75% |
| 50 yrs | 3.25% | 2.50% | 2.00% | 1.25% | 3.50% |
| 60 yrs | 3.25% | 2.50% | 2.00% | 1.50% | 3.50% |

For the US alone, the rate that never failed in 1871–2025 is 3.25% at 30 years and 2.75% at
60 years for a 75/25 mix; a 50/50 mix at 4% survives 89% of 30-year windows but only 41%
of 60-year ones. The 0.8% fee costs roughly 0.4–0.5 points of safe withdrawal rate; set fees
to zero on the page to see the gross figures. Full grids for every market, both withdrawal rules and every mix are in
[`results/`](results/), and the cross-market view is
[`results/markets_comparison.md`](results/markets_comparison.md).

Read Japan and Germany with care. Windows that need a missing series are skipped, not scored:
Japanese equities are missing for 1946–47 and German bonds for 1944–48, so every pre-war
Japanese window and every German window with bonds that crosses the war is dropped. Japan's
"100% at 60 years" rests on 20 windows that all start in 1948–1966. German windows that include
1923 fail at any withdrawal rate; under the fixed-nominal rule hyperinflation makes withdrawals
worthless, so use the inflation-adjusted rule for Germany. The 100%-equity rows for both
countries have no gaps.

## Data

| File | Contents | Source |
|---|---|---|
| `data/shiller_monthly.csv` | monthly CPI, nominal stock and 10-yr bond total-return indices, 1871→ | Shiller, `ie_data.xls` |
| `data/shiller_annual.csv` | US annual % returns, Jan→Jan | derived |
| `data/intl_extension.csv` | Japan / UK / Germany 2021–2025 equity, bond, CPI | MSCI / local index data (from the earlier SGD planner in this repo's history) |
| `data/msci_world_usd.csv` | MSCI World USD total return 1970–2025 | same |
| `data/markets.csv`, `data/markets.js` | unified annual series for `us`, `japan`, `uk`, `germany`, `world` | built from the above plus JST R6 |
| `data/mortality.js` | annual probability of death by age and sex, ages 30–110 | SSA period life table |

Rebuild (needs `pandas`, `xlrd`, `openpyxl`):

```
python3 scripts/build_data.py            # downloads Shiller's ie_data.xls
python3 scripts/build_markets.py         # downloads JST R6, writes data/markets.*
python3 scripts/trinity.py --market us   # one market, writes results/ (add --fees 0 for gross)
python3 scripts/compare_markets.py       # cross-market summary
```

`scripts/trinity.py --help` lists the options (sample years, periods, rates, mixes, withdrawal
timing). Both build scripts also accept a local path to the workbook.

JST data is CC BY-NC-SA 4.0. Cite Jordà, Schularick & Taylor (2017), "Macrofinancial History and
the New Business Cycle Facts", *NBER Macroeconomics Annual 2016*, and Jordà, Knoll, Kuvshinov,
Schularick & Taylor (2019), "The Rate of Return on Everything, 1870–2015", *QJE*.

### About the fja05680/sp500 repository

[fja05680/sp500](https://github.com/fja05680/sp500) holds S&P 500 *membership lists* from 1996
onward (which tickers were in the index on each date). It has no prices or returns, and its
author notes that reconstructing index returns from it requires paid survivorship-bias-free price
data. It is the right tool for stock-level backtests since 1996, but it cannot supply the
century-plus of index returns a longer-than-Trinity study needs, which is why the return series
here come from Shiller and JST instead.
