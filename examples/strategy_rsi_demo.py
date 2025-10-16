from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from backtester.dataio import download_to_csv, load_many_csv
from backtester.engine import Backtester, Costs
from backtester.metrics import total_return, cagr, sharpe, max_drawdown, round_trip_trades, trade_statistics
from backtester.strategies.rsi import RSICross

def main():
    tickers = ["AAPL","MSFT","GOOGL"]
    end = date.today(); start = end - timedelta(days=365*3)
    out = Path("data"); out.mkdir(exist_ok=True)
    download_to_csv(tickers, start.isoformat(), end.isoformat(), str(out))
    data = load_many_csv([str(out / f"{t}.csv") for t in tickers], max_workers=4)

    strat = RSICross(period=14, lower=30, upper=70)
    bt = Backtester(data, strat, initial_capital=100_000.0, costs=Costs(0.001, 0.0005))
    equity = bt.run()["Equity"]

    trades = round_trip_trades(bt.portfolio.fills)
    stats = {
        "Total Return %": total_return(equity)*100,
        "CAGR %": cagr(equity)*100,
        "Sharpe (ann)": sharpe(equity),
        "Max Drawdown %": max_drawdown(equity)*100,
        "# Trades": trade_statistics(trades)["num_trades"],
    }
    print(stats)

if __name__ == "__main__":
    main()