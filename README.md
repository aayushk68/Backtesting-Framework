# Backtesting Framework

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Tests](https://img.shields.io/badge/Tests-Pytest-brightgreen)
![Status](https://img.shields.io/badge/Status-Active-success)

A modular **Python backtesting framework** with realistic next-bar execution, portfolio accounting, performance metrics, **threaded** CSV loading (I/O-bound speedups), and **multiprocessing** for parameter optimization (CPU-bound speedups).  
Originally built for a Moving Average Crossover assignment, now generalized to support multiple strategies (MA, RSI, and easy to extend).

---

## ✨ Features
- **Modular design**: `Backtester`, `Portfolio`, `Strategy`, `Metrics`, `Costs`.
- **Realistic execution**: trade at **next day’s Open**, mark P&L at **Close**, no look-ahead.
- **Performance analytics**: CAGR, Sharpe (252), Max Drawdown, Win Rate, Profit Factor, Avg Duration.
- **Concurrency**:  
  - **Threading** for I/O (multi-CSV load)  
  - **Multiprocessing** for grid search / optimization
- **Visualization**: auto-saves equity & drawdown charts.
- **Tested**: Pytest coverage across engine, data I/O, metrics, and strategies.
- **Extensible**: drop new strategies in `backtester/strategies/` and plug in.

---

## ⚙️ Installation

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
pip install -r requirements.txt
# If activation is blocked:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt
```

---

## 🚀 Quick Start

Run a single backtest (10 tickers)

**Windows**
```powershell
python examples\simple_backtest.py
```

**macOS / Linux**
```bash
python examples/simple_backtest.py
```

Options:
```bash
# Reuse existing CSVs (offline)
python examples/simple_backtest.py --reuse

# Allow short positions
python examples/simple_backtest.py --reuse --allow-shorts
```

Outputs in `results/`:
- `equity_curve.csv`, `metrics.csv`, `drawdown.csv`, `trades.csv`
- `equity_curve.png`, `drawdown.png`

---

## 🧱 Design Highlights
- **Next-bar execution** → avoids look-ahead bias cleanly.  
- **Fixed per-symbol sizing** → balanced exposure across assets.  
- **Trade only on signal change** → avoids churn on noise.  
- **I/O vs CPU separation** → threading for data, multiprocessing for compute.  
- **Sanity checks** → cash ≥ 0, MTM consistent with closes.

---

## 🧩 Project Structure
<details>
<summary><b>Click to expand</b></summary>

```
backtester/
├─ engine.py            # core backtesting loop
├─ portfolio.py         # positions, cash & fills
├─ metrics.py           # performance analytics
├─ strategy.py          # base strategy class
├─ dataio.py            # threaded CSV loading
├─ utils.py             # timing, helpers
└─ strategies/
   ├─ ma_crossover.py
   └─ rsi.py

examples/
├─ simple_backtest.py
├─ threaded_data_load.py
├─ parallel_optimization.py
├─ strategy_rsi_demo.py
└─ make_summary.py

tests/
├─ test_engine.py
├─ test_portfolio.py
├─ test_metrics.py
├─ test_strategy.py
├─ test_dataio.py
└─ test_min_coverage.py

data/      # ignored by git
results/   # ignored by git
```
</details>

---

## 📚 API (Main Classes)

**Backtester**
```python
Backtester(
  data: dict[str, pd.DataFrame],
  strategy: Strategy,
  initial_capital: float = 100_000.0,
  costs: Costs = Costs(commission=0.001, slippage=0.0005),
  allow_shorts: bool = False
)
```
Runs the backtest and returns the equity curve + trade log.

**Strategy**
```python
class Strategy(Protocol):
    def generate_signals(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame: ...
```
Implement in `strategies/` (e.g., `ma_crossover.py`, `rsi.py`).

---

## 📈 Results (Sample)

**Portfolio-level metrics**
| Mode        | Total Return | CAGR  | Sharpe | Max DD | Win Rate | Profit Factor |
|-------------|--------------:|------:|------:|------:|---------:|--------------:|
| Long Only   | 103.05%       | 15.15% | 0.96  | -19.46% | 57.7%   | 8.09 |
| Long + Short| 83.73%        | 12.88% | 0.84  | -18.91% | 44.2%   | 2.38 |

**Takeaways**
- Long-only had smoother returns and higher Sharpe.  
- Shorts increased drawdowns and reduced win rate.  
- Sanity checks passed (no negative cash, no look-ahead).

> Charts are saved as `results/equity_curve.png` and `results/drawdown.png`.

---

## ⚡ Benchmarks

**Threading (I/O-bound)**
| Files | Latency/file | Workers | Sequential | Threaded | Speedup |
|------:|-------------:|--------:|-----------:|---------:|--------:|
| 40    | 30 ms        | 16      | 2.18 s     | 0.29 s   | **7.37×** |

**Multiprocessing (CPU-bound)**
| Grid Size | Best Combo | Cores | Sequential | Parallel | Speedup |
|----------:|------------|------:|-----------:|---------:|--------:|
| 8         | (50, 100)  | 8     | 2.87 s     | 3.55 s   | 0.81×   |
| 35        | (30, 100)  | 8     | 8.85 s     | 5.44 s   | **1.63×** |

Notes:
- Tiny grids under-utilize processes (startup & I/O dominate).  
- Real speedups (1.5–5×) appear once compute per task is meaningful.

---

## 🧪 Testing
Run all tests with coverage:
```bash
pytest -q --disable-warnings --maxfail=1 --cov=backtester
```
Covers engine semantics (next-bar), portfolio math, metrics, data I/O (threaded), and strategy alignment.

---

## 🔧 Useful Commands

**Threading demo**
```bash
python examples/threaded_data_load.py --n 40 --max-workers 16 --io-latency-ms 30
```

**Optimization (grid search)**
```bash
python examples/parallel_optimization.py
```

**Regenerate combined summary**
```bash
# Long-only
python examples/simple_backtest.py --reuse
mkdir -p results_long_only && cp results/* results_long_only/

# Long+short
python examples/simple_backtest.py --reuse --allow-shorts
mkdir -p results_long_short && cp results/* results_long_short/

# Merge summaries
python examples/make_summary.py
```

---

## 🧭 Extend It
Add a new strategy file under `backtester/strategies/`:
```python
class MyCoolStrategy(Strategy):
    def generate_signals(self, data):
        # return DataFrame of {-1,0,1}
        ...
```
Use it in `examples/simple_backtest.py` and re-run. No engine changes needed.

---

## 📝 License
MIT © 2025 Your Name
