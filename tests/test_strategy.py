# tests/test_strategy.py
from __future__ import annotations
import pandas as pd
from backtester.strategies.ma_crossover import MovingAverageCrossover

def _df_from_close(closes):
    """Build minimal OHLCV DataFrame indexed by business days."""
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    close = pd.Series(closes, index=idx, dtype="float")
    df = pd.DataFrame({
        "Open": close.values,
        "High": close.values,
        "Low":  close.values,
        "Close": close.values,
        "Adj Close": close.values,
        "Volume": 1_000_000,
    }, index=idx)
    return df

def test_ma_signals_and_shift():
    # Short MA (2) crosses above Long MA (3) around the 4th bar.
    # expected signals to become +1 *from the next bar* (shift(1)).
    px = [10, 10, 10, 12, 13, 14, 13, 12]
    df = _df_from_close(px)
    strat = MovingAverageCrossover(short_window=2, long_window=3)

    sig = strat.generate_signals({"AAA": df})["AAA"]

    # Before long MA is warm (first 2 bars), signals are 0
    assert sig.iloc[0] == 0 and sig.iloc[1] == 0

    # Compute raw condition without shift to confirm crossover timing
    s = pd.Series(px, index=df.index).rolling(2).mean()
    l = pd.Series(px, index=df.index).rolling(3).mean()
    raw = (s > l).astype(int) + (s < l).astype(int) * -1
    # The first day raw becomes +1…
    first_plus = raw.where(raw == 1).first_valid_index()
    # …shift(1) means the strategy's +1 appears one day later
    first_plus_shifted = sig.where(sig == 1).first_valid_index()
    assert first_plus_shifted == sig.index[sig.index.get_loc(first_plus) + 1]

    # Sanity: signal values are in {-1, 0, 1}
    assert set(sig.unique()).issubset({-1, 0, 1})
