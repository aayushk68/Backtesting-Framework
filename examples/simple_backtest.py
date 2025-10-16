# examples/simple_backtest.py
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from backtester.dataio import download_to_csv, load_many_csv
from backtester.engine import Backtester, Costs
from backtester.metrics import (
    total_return,
    cagr,
    sharpe,
    max_drawdown,
    round_trip_trades,
    trade_statistics,
)

from backtester.strategies.ma_crossover import MovingAverageCrossover


# --------------------------- helpers ---------------------------

def compute_core_metrics(equity: pd.Series) -> dict[str, float]:
    return {
        "Total Return %": total_return(equity) * 100.0,
        "CAGR %": cagr(equity) * 100.0,
        "Sharpe (ann)": sharpe(equity),
        "Max Drawdown %": max_drawdown(equity) * 100.0,
    }


def trades_to_dataframe(trades) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["symbol","entry_date","exit_date","side","qty","entry_amount","exit_amount","pnl","duration_days"])
    rows = []
    for t in trades:
        rows.append({
            "symbol": t.symbol,
            "entry_date": pd.Timestamp(t.entry_date),
            "exit_date": pd.Timestamp(t.exit_date),
            "side": t.side,
            "qty": int(t.qty),
            "entry_amount": float(t.entry_amount),
            "exit_amount": float(t.exit_amount),
            "pnl": float(t.pnl),
            "duration_days": int(t.duration_days),
        })
    df = pd.DataFrame(rows).sort_values(["entry_date","symbol"]).reset_index(drop=True)
    return df


def print_trade_tables(trades_df: pd.DataFrame, max_rows: int = 5) -> None:
    if trades_df.empty:
        print("\nNo completed round-trip trades to display.")
        return

    winners = trades_df.sort_values("pnl", ascending=False).head(max_rows)
    losers = trades_df.sort_values("pnl", ascending=True).head(max_rows)

    def _fmt(df):
        out = df.copy()
        out["entry_date"] = out["entry_date"].dt.date
        out["exit_date"] = out["exit_date"].dt.date
        return out[["symbol","side","entry_date","exit_date","qty","duration_days","pnl"]]

    print("\nTop Winners (by PnL):")
    print(_fmt(winners).to_string(index=False))
    print("\nTop Losers (by PnL):")
    print(_fmt(losers).to_string(index=False))


def plot_equity_curve(equity: pd.Series, outpath: Path) -> None:
    outpath.parent.mkdir(exist_ok=True, parents=True)
    plt.figure(figsize=(10, 4.5))
    plt.plot(equity.index, equity.values)
    plt.title("Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return dd


def plot_drawdown(drawdown: pd.Series, outpath: Path) -> None:
    outpath.parent.mkdir(exist_ok=True, parents=True)
    plt.figure(figsize=(10, 3.5))
    plt.plot(drawdown.index, drawdown.values)
    plt.title("Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (fraction)")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


def run_sanity_checks(data, bt, equity_df):
    print("\n=== Sanity Checks ===")
    equity = equity_df["Equity"]
    start_equity = float(equity.iloc[0])
    changed = equity[equity != start_equity]
    first_equity_change = changed.index.min() if not changed.empty else None
    print(f"First equity value: {start_equity:,.2f}")
    print("First equity change date:", first_equity_change)

    fills_df = pd.DataFrame([vars(f) for f in bt.portfolio.fills]).sort_values("date").reset_index(drop=True)
    if fills_df.empty:
        print("No fills recorded (strategy may have stayed flat).")
        return

    print("\nFirst 5 fills:")
    print(fills_df.head())

    neg_cash = (fills_df["cash_after"] < 0).any()
    print("Negative cash observed?", bool(neg_cash))
    any_short = any(qty < 0 for qty in [getattr(p, "qty", 0) for p in bt.portfolio.positions.values()])
    print("Any short positions (negative qty)?", bool(any_short))

    last_day = equity_df.index[-1]
    close_prices = {sym: float(data[sym].loc[last_day, "Close"]) for sym in data}
    cash = float(bt.portfolio.cash)
    mv = sum((bt.portfolio.positions.get(sym).qty if bt.portfolio.positions.get(sym) else 0) * close_prices[sym] for sym in data)
    equity_recomputed = cash + mv
    print(f"Final day equity (engine): {float(equity_df.iloc[-1]['Equity']):,.2f}")
    print(f"Final day equity (recalc) : {equity_recomputed:,.2f}")
    diff = abs(float(equity_df.iloc[-1]['Equity']) - equity_recomputed)
    print(f"Equity difference (engine vs recalc): {diff:.6f}")


# --------------------------- main ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Run a simple backtest with metrics, trades, sanity checks, and SPY benchmark.")
    parser.add_argument("--reuse", action="store_true", help="Reuse existing CSVs in data/ (skip download).")
    parser.add_argument("--short", type=int, default=50)
    parser.add_argument("--long", type=int, default=200)
    parser.add_argument("--capital", type=float, default=None,
                        help="Initial capital. If not provided, auto-scales with number of tickers.")
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--allow-shorts", action="store_true", help="Enable short trades.")
    args = parser.parse_args()

    # === Ticker list (10 symbols) ===
    tickers = ["AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA","JPM","XOM","UNH"]

    # === Auto-capital logic ===
    TARGET_PER_SYMBOL = 31667.0  # ~ per-symbol allocation (did it earlier for 3-ticker and took $100k capital, so allocating same amt for all the tickers added)
    if args.capital is None:
        args.capital = (TARGET_PER_SYMBOL * len(tickers)) / 0.95
        print(f"[INFO] Auto initial capital set to ${args.capital:,.0f} for {len(tickers)} tickers.")

    end = date.today()
    start = end - timedelta(days=365 * 5 + 10)
    start_iso, end_iso = start.isoformat(), end.isoformat()
    out = Path("data"); out.mkdir(exist_ok=True)

    if not args.reuse:
        download_to_csv(tickers, start_iso, end_iso, str(out))

    paths = [str(out / f"{t}.csv") for t in tickers]
    data = load_many_csv(paths, max_workers=4)

    strat = MovingAverageCrossover(args.short, args.long)
    bt = Backtester(
        data,
        strat,
        initial_capital=args.capital,
        costs=Costs(args.commission, args.slippage),
        allow_shorts=args.allow_shorts,
    )

    equity_df = bt.run()
    equity = equity_df["Equity"]

    metrics = compute_core_metrics(equity)
    trades = round_trip_trades(bt.portfolio.fills)
    tstats = trade_statistics(trades)
    metrics.update({
        "Number of Trades": tstats["num_trades"],
        "Win Rate %": tstats["win_rate"],
        "Profit Factor": tstats["profit_factor"],
        "Avg Trade Duration (days)": tstats["avg_duration_days"],
    })

    Path("results").mkdir(exist_ok=True)
    equity_df.to_csv("results/equity_curve.csv", index=True)

    trades_df = trades_to_dataframe(trades)
    trades_df.to_csv("results/trades.csv", index=False)
    pd.DataFrame([metrics]).to_csv("results/metrics.csv", index=False)

    plot_equity_curve(equity, Path("results/equity_curve.png"))

    dd = compute_drawdown_series(equity)
    pd.DataFrame({"Drawdown": dd}).to_csv("results/drawdown.csv", index=True)
    plot_drawdown(dd, Path("results/drawdown.png"))

    mode = "MA ±1 signals: long/flat/short" if args.allow_shorts else "MA long-only"
    print(f"\n=== Backtest Summary ({mode}) ===")
    print(f"Params: short={args.short}, long={args.long}, capital={args.capital:,.0f}, commission={args.commission}, slippage={args.slippage}")
    for k in [
        "Total Return %","CAGR %","Sharpe (ann)","Max Drawdown %",
        "Number of Trades","Win Rate %","Profit Factor","Avg Trade Duration (days)"
    ]:
        v = metrics.get(k, None)
        if v is None: continue
        if isinstance(v, float):
            if "Sharpe" in k or "Factor" in k:
                print(f"{k:>28}: {v:,.4f}")
            else:
                print(f"{k:>28}: {v:,.2f}")
        else:
            print(f"{k:>28}: {v}")

    print("\nLast 5 days of Equity:")
    print(equity_df.tail())

    print_trade_tables(trades_df, max_rows=5)
    run_sanity_checks(data, bt, equity_df)

    print("\nSaved:")
    print(" - results/equity_curve.csv")
    print(" - results/metrics.csv")
    print(" - results/trades.csv")
    print(" - results/drawdown.csv")
    print(" - results/equity_curve.png")
    print(" - results/drawdown.png")


if __name__ == "__main__":
    main()
