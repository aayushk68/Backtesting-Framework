# tests/test_portfolio.py
from __future__ import annotations
import pandas as pd
from backtester.portfolio import Portfolio

def test_buy_sell_flow_and_equity():
    # Start with $100k cash, no positions
    pf = Portfolio(cash=100_000.0)

    # Price environment used for equity marks
    idx = pd.bdate_range("2024-01-01", periods=3)
    prices_day1 = {"AAA": 100.0}
    prices_day2 = {"AAA": 105.0}
    prices_day3 = {"AAA": 95.0}

    # BUY 500 AAA @ 100, commission 10
    pf._apply_fill(idx[0], "AAA", "BUY", 500, 100.0, commission=10.0, prices_now=prices_day1)
    assert pf.cash == 100_000.0 - (500*100.0 + 10.0)
    assert pf.positions["AAA"].qty == 500
    assert abs(pf.positions["AAA"].avg_cost - 100.0) < 1e-9
    # Equity after day1
    assert abs(pf.equity(prices_day1) - (pf.cash + 500*100.0)) < 1e-9

    # SELL 200 AAA @ 105, commission 8
    pf._apply_fill(idx[1], "AAA", "SELL", 200, 105.0, commission=8.0, prices_now=prices_day2)
    assert pf.positions["AAA"].qty == 300  # partial exit
    # Cash added: 200*105 - 8
    expected_cash = 100_000.0 - (500*100 + 10) + (200*105 - 8)
    assert abs(pf.cash - expected_cash) < 1e-9
    # Equity at day2 (mark remaining 300 @ 105)
    assert abs(pf.equity(prices_day2) - (pf.cash + 300*105.0)) < 1e-9

    # SELL remaining 300 @ 95, commission 6 -> position closes
    pf._apply_fill(idx[2], "AAA", "SELL", 300, 95.0, commission=6.0, prices_now=prices_day3)
    assert pf.positions["AAA"].qty == 0
    assert pf.positions["AAA"].avg_cost == 0.0
    # Equity equals cash (no positions)
    assert abs(pf.equity(prices_day3) - pf.cash) < 1e-9
