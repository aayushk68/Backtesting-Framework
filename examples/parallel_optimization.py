# examples/parallel_optimization.py
from __future__ import annotations

import itertools
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List

import pandas as pd

from backtester.dataio import load_many_csv
from backtester.engine import Backtester, Costs
from backtester.metrics import total_return, cagr, sharpe, max_drawdown
from backtester.strategies.ma_crossover import MovingAverageCrossover


@dataclass(frozen=True)
class Params:
    short: int
    long: int


def run_one(params: Params, data_paths: List[str],
            initial_capital: float, commission: float, slippage: float) -> Tuple[Params, Dict[str, float]]:
    # Load data inside each process (avoid pickling large dataframes)
    data = load_many_csv(data_paths, max_workers=1)

    strat = MovingAverageCrossover(params.short, params.long)
    bt = Backtester(data, strat, initial_capital=initial_capital, costs=Costs(commission, slippage))
    equity_df = bt.run()
    equity = equity_df["Equity"]

    metrics = {
        "short": params.short,
        "long": params.long,
        "Total Return %": total_return(equity) * 100.0,
        "CAGR %": cagr(equity) * 100.0,
        "Sharpe (ann)": sharpe(equity),
        "Max Drawdown %": max_drawdown(equity) * 100.0,
    }
    return params, metrics


def run_grid_sequential(grid: List[Params], data_paths: List[str],
                        initial_capital: float, commission: float, slippage: float) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for p in grid:
        _, res = run_one(p, data_paths, initial_capital, commission, slippage)
        rows.append(res)
    return rows


def run_grid_parallel(grid: List[Params], data_paths: List[str],
                      initial_capital: float, commission: float, slippage: float) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with ProcessPoolExecutor() as ex:
        futs = {ex.submit(run_one, p, data_paths, initial_capital, commission, slippage): p for p in grid}
        for fut in as_completed(futs):
            _, res = fut.result()
            rows.append(res)
    return rows


def main():
    # ===== Grid =====
    short_list = [10, 20, 30, 50, 75, 100]
    long_list = [100, 150, 200, 250, 300, 350]
    grid = [Params(s, l) for s, l in itertools.product(short_list, long_list) if s < l]

    # ===== Tickers (10) =====
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "XOM", "UNH"]
    data_dir = Path("data")
    data_paths = [str(data_dir / f"{t}.csv") for t in tickers]

    # ===== Auto initial capital to preserve per-symbol budget from the 3-ticker/100k baseline =====
    # Baseline per-symbol budget with 3 tickers at 100k is: 0.95 * 100_000 / 3.
    # To keep that same per-symbol sizing for N tickers: initial_capital = 100_000 * (N / 3).
    n = len(tickers)
    initial_capital = round(100_000 * (n / 3.0))  # ≈ 333,333 for 10 tickers
    print(f"[INFO] Auto initial capital set to ${initial_capital:,.0f} for {n} tickers.")

    commission = 0.001
    slippage = 0.0005

    # ===== Sequential timing =====
    t0 = time.perf_counter()
    rows_seq = run_grid_sequential(grid, data_paths, initial_capital, commission, slippage)
    t1 = time.perf_counter()
    seq_time = t1 - t0

    # ===== Parallel timing =====
    t2 = time.perf_counter()
    rows_par = run_grid_parallel(grid, data_paths, initial_capital, commission, slippage)
    t3 = time.perf_counter()
    par_time = t3 - t2

    # Use the parallel results for ranking (same computations)
    df = pd.DataFrame(rows_par).sort_values("Sharpe (ann)", ascending=False)
    Path("results").mkdir(exist_ok=True, parents=True)
    out_csv = Path("results/opt_results.csv")
    df.to_csv(out_csv, index=False)

    # Save timing JSON for the summary script
    timing = {
        "cores": multiprocessing.cpu_count(),
        "grid_size": len(grid),
        "sequential_time_sec": seq_time,
        "parallel_time_sec": par_time,
        "speedup": (seq_time / par_time) if par_time > 0 else None,
    }
    with open(Path("results/opt_timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, indent=2)

    
    print("\n=== Parallel Optimization Results (ranked by Sharpe) ===")
    print(df.to_string(index=False))
    print(f"\nSaved: {out_csv}")

    print("\n=== Timing Summary ===")
    print(f"CPU cores (detected) : {timing['cores']}")
    print(f"Grid size            : {timing['grid_size']}")
    print(f"Sequential time      : {seq_time:.2f}s")
    print(f"Parallel time        : {par_time:.2f}s")
    sp = (seq_time / par_time) if par_time > 0 else 0.0
    print(f"Speedup              : {sp:.2f}x")

if __name__ == "__main__":
    main()
