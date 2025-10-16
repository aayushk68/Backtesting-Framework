from __future__ import annotations
import pandas as pd
from backtester.metrics import (
    total_return, cagr, sharpe, max_drawdown,
    round_trip_trades, trade_statistics,
)
from backtester.portfolio import Portfolio, Fill

def test_equity_metrics_and_trades_and_portfolio():
    # ---- Equity curve: exercise total_return/cagr/sharpe/max_drawdown
    idx = pd.date_range("2022-01-01", periods=6, freq="D")
    eq = pd.Series([100_000, 101_000, 102_000, 99_000, 100_500, 101_500], index=idx, name="Equity")
    assert round(total_return(eq), 6) == round((101_500/100_000) - 1, 6)
    assert cagr(eq) >= -1.0
    assert max_drawdown(eq) <= 0.0
    _ = sharpe(eq)  # value depends on data; just ensure it runs

    # ---- Trades: one long round-trip (BUY then SELL)
    fills = [
        Fill(date=idx[0], symbol="XYZ", side="BUY",  qty=100, price=100.0, commission=1.0, cash_after=0.0, equity_after=0.0),
        Fill(date=idx[2], symbol="XYZ", side="SELL", qty=100, price=110.0, commission=1.0, cash_after=0.0, equity_after=0.0),
    ]
    trades = round_trip_trades(fills)
    stats = trade_statistics(trades)
    assert stats["num_trades"] == 1.0
    assert stats["gross_profit"] > 0.0
    assert 0.0 <= stats["win_rate"] <= 100.0

    # ---- Portfolio: exercise _apply_fill (buy -> partial sell -> flat)
    p = Portfolio(cash=10_000.0)
    prices = {"XYZ": 0.0}

    p._apply_fill(idx[0], "XYZ", "BUY", 10, 100.0, 1.0, prices_now=prices)   # buy 10
    assert p.positions["XYZ"].qty == 10
    assert p.cash == 10_000.0 - (10*100.0 + 1.0)

    p._apply_fill(idx[1], "XYZ", "SELL", 4, 110.0, 1.0, prices_now=prices)   # sell 4
    assert p.positions["XYZ"].qty == 6

    p._apply_fill(idx[2], "XYZ", "SELL", 6, 120.0, 1.0, prices_now=prices)   # sell 6 (flat)
    assert p.positions["XYZ"].qty == 0
    assert p.positions["XYZ"].avg_cost == 0.0
