import pandas as pd
from backtester.metrics import total_return, cagr, max_drawdown, sharpe

def test_metrics_basic():
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    eq = pd.Series([100, 102, 101, 103, 104], index=idx)
    assert round(total_return(eq),4) == round(104/100-1,4)
    assert max_drawdown(eq) <= 0
    assert isinstance(sharpe(eq), float)
