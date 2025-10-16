## Backtesting Framework – Moving Average Crossover (with Threading & Multiprocessing)
I built a complete mini-backtesting framework in Python that tests a Moving Average Crossover strategy across multiple tickers.
I also implemented threading for faster CSV data loading, multiprocessing for optimization, and added a few bonus things like visualizations, an RSI strategy, and a summary generator.

# Installation
1. Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
pip install -r requirements.txt
If PowerShell blocks script activation:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

2. macOS / Linux (bash or zsh)
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt

# Quick Start
Run a single backtest (10 tickers)
1. Windows
python examples\simple_backtest.py

2. macOS / Linux
python examples/simple_backtest.py

Reuse existing CSVs (offline)
python examples/simple_backtest.py --reuse
Allow short positions
python examples/simple_backtest.py --reuse --allow-shorts
Results are stored in the results/ folder:

equity_curve.csv, metrics.csv, drawdown.csv, trades.csv

equity_curve.png, drawdown.png

# Project Structure
backtester/
│
├── dataio.py         # download_to_csv, load_many_csv (threaded)
├── engine.py         # core backtesting logic
├── portfolio.py      # position and cash tracking
├── metrics.py        # return %, Sharpe, DD, trades
├── strategy.py       # abstract base class
├── utils.py
│
├── strategies/
│   ├── ma_crossover.py
│   └── rsi.py
│
examples/
│   ├── simple_backtest.py
│   ├── threaded_data_load.py
│   ├── parallel_optimization.py
│   ├── strategy_rsi_demo.py
│   └── make_summary.py
│
tests/
│   ├── test_dataio.py
│   ├── test_engine.py
│   ├── test_portfolio.py
│   ├── test_metrics.py
│   ├── test_strategy.py
│   └── test_min_coverage.py
│
data/
│   ├── AAPL.csv ... UNH.csv
│   └── _dup_demo/   # used only for threading demo
│
results/
│   ├── equity_curve.csv/png
│   ├── drawdown.csv/png
│   ├── metrics.csv
│   ├── opt_results.csv
│   ├── summary.md
│   └── results_long_only + results_long_short
### How I Built It
1. Core Backtesting Engine
Iterates through dates and tickers chronologically.

Executes trades at next day’s Open based on signals (to avoid look-ahead).

Tracks cash, positions, equity, and fills.

Applies commissions (0.1%) and slippage (0.05%).

Recomputes total equity daily and logs trades in trades.csv.

Computes: total return, CAGR, Sharpe ratio, max drawdown, win rate, profit factor, average duration.

2. Strategy – Moving Average Crossover
MovingAverageCrossover(short_window, long_window)

Signal rules:

1 → short MA > long MA

0 → neutral

-1 → short (only if allowed)

Signals shifted by one bar to prevent look-ahead bias.

3. Threading for Data Loading
threaded_data_load.py duplicates an existing CSV into N files.

Adds optional per-file latency to simulate network/disk delays.

Compares sequential vs threaded loading times.

Achieves 2×–7× speedup depending on latency and number of files.

4. Multiprocessing for Optimization
parallel_optimization.py runs a grid search of (short, long) window pairs.

Uses multiple CPU cores with ProcessPoolExecutor.

Collects metrics (return, Sharpe, drawdown) and ranks top combinations.

Saves to results/opt_results.csv and prints timing comparisons.

5. Visualization
simple_backtest.py automatically saves:

Equity curve (equity_curve.png)

Drawdown chart (drawdown.png)

Makes it easier to visually compare runs.

6. Summary Report
make_summary.py merges long-only and long+short results.

Writes results/summary.md with metrics, timings, and best combos.

## API (Main Classes)
Backtester
Backtester(
  data: dict[str, pd.DataFrame],
  strategy: Strategy,
  initial_capital: float = 100000.0,
  costs: Costs = Costs(commission=0.001, slippage=0.0005),
  allow_shorts: bool = False
)
Runs the backtest and returns a DataFrame of equity over time.

Strategy
Base class:

generate_signals(data: dict[str, pd.DataFrame]) -> pd.DataFrame
Each subclass defines its own signal logic.

MovingAverageCrossover
Generates ±1/0 signals based on short and long MAs, shifted to avoid look-ahead.

RSI Strategy (Bonus)
An extra file rsi.py defines a basic RSI strategy using 30/70 thresholds.
Demonstrated in examples/strategy_rsi_demo.py.

# Testing and Coverage
Run all tests:

pytest -q --disable-warnings --maxfail=1 --cov=backtester
test_engine.py → smoke test for full engine run.

test_portfolio.py → checks cash and quantity after fills.

test_strategy.py → validates MA signal logic and no look-ahead.

test_dataio.py → tests threaded loader and CSV parsing.

test_min_coverage.py , test_metrics.py→ exercises metrics, trades, and portfolio for coverage.

Coverage measures how much of your main library code (not test code) is executed by tests.
Initially my dataio.py had 0 %, so I added a separate test to fix that.

# Performance Benchmarks
1. Threading (I/O-bound)
=== Threaded Loader Demo ===
Files     : 40
Latency   : 30 ms per file
Workers   : 16
Sequential: 2.18s
Threaded  : 0.29s
Speedup   : 7.37x
2. Multiprocessing (CPU-bound)
Small Grid (8 combos)
Best Combo : (short=50, long=100) — Sharpe = 1.2369
Cores Used : 8
Sequential : 2.87 s
Parallel   : 3.55 s
Speedup    : 0.81×
Larger Grid (35 combos)
Best Combo : (short=30, long=100) — Sharpe = 1.6094
Cores Used : 8
Sequential : 8.85 s
Parallel   : 5.44 s
Speedup    : 1.63×
Explanation:

Small grid tasks were too light → process startup and I/O overhead dominated.

Large grid had more compute per task → parallel efficiency improved to 1.6×.

Realistic speedups (1.5–5×) appear once grids are 30+ combos.

-> Takeaway: threading speeds up I/O tasks dramatically; multiprocessing helps once computation dominates.

## Results Summary
Mode	Total Return %	CAGR %	Sharpe	Max DD %	Win Rate %	Profit Factor
Long Only	103.05	15.15	0.9607	-19.46	57.69	8.09
Long+Short	83.73	12.88	0.8373	-18.91	44.23	2.38
Cores Used: 8
Parallel Timing (Large Grid): Sequential = 8.85 s → Parallel = 5.44 s (1.63× faster)

Observations

Long-only smoother and higher Sharpe.

Shorts increase drawdowns and lower win rate.

Threading: 2–7× faster CSV loading.

Multiprocessing: slower for tiny grids, faster for large.

Sanity checks all passed (no negative cash, equity reconcile OK, no look-ahead).

## Bonus Work I Added
Feature	Description
RSI Strategy	Implemented new strategy in backtester/strategies/rsi.py and demo in examples/strategy_rsi_demo.py.
Visualization	Auto-generated equity_curve.png and drawdown.png saved under results/.
Summary Generator	Script make_summary.py creates Markdown summary combining long-only and long+short runs.
Threading Demo	threaded_data_load.py compares sequential vs threaded file loads with simulated latency.
Multiprocessing Optimization	parallel_optimization.py runs MA grid search using CPU cores, outputs top Sharpe combos.

## Regenerate Results Summary

# Run and save long-only
python examples/simple_backtest.py --reuse
mkdir -p results_long_only
cp results/* results_long_only/

# Run and save long+short
python examples/simple_backtest.py --reuse --allow-shorts
mkdir -p results_long_short
cp results/* results_long_short/

# Regenerate combined summary
python examples/make_summary.py

## Design Highlights
Next-bar execution at Open → avoids look-ahead bias cleanly.

Fixed per-symbol sizing → avoids leverage; keeps capital equal across tickers.

Trade only on signal change → avoids over-trading noise.

Threading for I/O and multiprocessing for CPU → clear real-world concurrency separation.

Sanity checks after each run (cash ≥ 0, equity ≈ mark-to-market).

Extensible architecture → easy to add new strategies.

# Lessons Learned / Problems Solved
Started with 3 tickers (AAPL, MSFT, GOOGL); scaled to 10 tickers for realism.
This required dynamic capital allocation (auto-scales per symbol).

Some CSVs downloaded with duplicate header rows; fixed by coercing numeric columns and dropping bad lines.

Parallel optimization initially slower → realized grid too small. Increased to 35 combos to get 1.6× gain.

Coverage for dataio was 0 % → added dedicated test to improve it.

Created _dup_demo/ folder only for the threading benchmark.

## Commands Reference (Windows, macOS, Linux)
# Run long-only
python examples/simple_backtest.py --reuse

# Run long+short
python examples/simple_backtest.py --reuse --allow-shorts

# Threading demo
python examples/threaded_data_load.py --n 40 --max-workers 16 --io-latency-ms 30

# Optimization
python examples/parallel_optimization.py

# Regenerate summary
python examples/make_summary.py

# Run tests with coverage
pytest -q --disable-warnings --maxfail=1 --cov=backtester
# Conclusion

A functional, modular backtesting engine.

Moving Average Crossover strategy.

Multithreading and multiprocessing examples.

Metrics, plots, and a full results summary.

Unit tests and coverage.

Plus extra features (RSI strategy, visualizations, summary generation).

It now runs smoothly on Windows, macOS, and Linux.
This project took me through a lot of debuggingand latency tuning but in the end I’m happy with how clean and extensible it turned out.