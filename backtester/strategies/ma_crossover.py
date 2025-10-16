# backtester/strategies/ma_crossover.py
from __future__ import annotations
import pandas as pd
from ..strategy import Strategy

class MovingAverageCrossover(Strategy):
    def __init__(self, short_window: int = 50, long_window: int = 200):
        if short_window >= long_window:
            raise ValueError("short_window must be < long_window")
        self.short_window = short_window
        self.long_window = long_window

    def _signal_one(self, df: pd.DataFrame) -> pd.Series:
        px = df["Adj Close"].astype(float)
        s = px.rolling(self.short_window).mean()
        l = px.rolling(self.long_window).mean()
        # 1 when short>long, -1 when short<long, else 0; then shift(1) to trade next bar
        sig = pd.Series(0, index=px.index, dtype="int8")
        sig = sig.mask(s > l, 1).mask(s < l, -1)
        return sig.shift(1).fillna(0).astype("int8")

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        signals = {sym: self._signal_one(df) for sym, df in data.items()}
        return pd.DataFrame(signals).fillna(0).astype("int8")
