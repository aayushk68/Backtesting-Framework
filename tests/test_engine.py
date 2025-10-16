# tests/test_engine.py
from __future__ import annotations
import pandas as pd
from backtester.engine import Backtester, Costs
from backtester.strategies.ma_crossover import MovingAverageCrossover

def _mk_df(closes):
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    c = pd.Series(closes, index=idx, dtype="float")
    df = pd.DataFrame({
        "Open": c.values, "High": c.values, "Low": c.values,
        "Close": c.values, "Adj Close": c.values, "Volume": 1_000_000,
    }, index=idx)
    return df

def test_engine_next_bar_and_fills_long_only():
    # Two assets, small windows so  don’t need 200 days of warmup.
    # AAA trends up (will go long); BBB trends down then up → some exits/entries.
    data = {
        "AAA": _mk_df([10, 10, 10, 12, 13, 14, 15, 15, 16, 17]),
        "BBB": _mk_df([20, 20, 19, 18, 18, 19, 20, 21, 21, 22]),
    }
    strat = MovingAverageCrossover(short_window=2, long_window=3)
    bt = Backtester(data, strat, initial_capital=100_000.0, costs=Costs(0.001, 0.0005), allow_shorts=False)
    equity_df = bt.run()

    # Equity produced, aligned to the common calendar
    assert not equity_df.empty and equity_df["Equity"].notna().all()

    #should have recorded some fills (buys/sells) and no negative cash
    fills = bt.portfolio.fills
    assert len(fills) > 0
    assert min(f.cash_after for f in fills) >= 0.0

    # Next-bar execution: the first BUY for AAA should occur **the session after** the crossover.
    # Find the first +1 signal day for AAA (raw), then +1 shows in signals next day.
    sig = strat.generate_signals(data)["AAA"]
    first_sig_plus = sig.where(sig == 1).first_valid_index()
    # We filled at next day's Open, so there must be a BUY fill on first_sig_plus (or soon after),
    # because our code trades only when signal changes.
    first_buy_dates = [f.date for f in fills if f.symbol == "AAA" and f.side == "BUY"]
    assert first_buy_dates and first_buy_dates[0] >= first_sig_plus  # on / after the target day

def test_engine_allows_shorts_when_enabled():
    data = {
        "AAA": _mk_df([10, 9, 8, 7, 8, 9, 10, 9, 8, 7]),
        "BBB": _mk_df([12, 12, 12, 12, 11, 10, 9, 8, 8, 7]),
    }
    strat = MovingAverageCrossover(short_window=2, long_window=3)
    bt = Backtester(data, strat, initial_capital=50_000.0, costs=Costs(0.001, 0.0005), allow_shorts=True)
    _ = bt.run()

    # With shorts allowed , expected at least one SELL (entry for short) or negative qty at some point.
    any_short_fill = any(f.side == "SELL" for f in bt.portfolio.fills)
    any_neg_qty = any(getattr(p, "qty", 0) < 0 for p in bt.portfolio.positions.values())
    assert any_short_fill or any_neg_qty
