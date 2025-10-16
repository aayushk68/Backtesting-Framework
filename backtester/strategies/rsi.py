from __future__ import annotations
import pandas as pd
from ..strategy import Strategy

class RSICross(Strategy):
    """
    Long when RSI crosses up through lower; flat when RSI crosses down through upper.
    (Keeps signals in {-1,0,1}; here we use {1,0} for long-only style.)
    """
    def __init__(self, period: int = 14, lower: float = 30.0, upper: float = 70.0):
        self.period = int(period)
        self.lower = float(lower)
        self.upper = float(upper)

    def _rsi(self, series: pd.Series) -> pd.Series:
        delta = series.diff()
        up = delta.clip(lower=0.0)
        down = -delta.clip(upper=0.0)
        roll_up = up.ewm(alpha=1/self.period, adjust=False).mean()
        roll_down = down.ewm(alpha=1/self.period, adjust=False).mean()
        rs = roll_up / roll_down.replace(0, 1e-12)
        return 100 - (100 / (1 + rs))

    def _signal_one(self, df: pd.DataFrame) -> pd.Series:
        px = df["Adj Close"].astype(float)
        rsi = self._rsi(px)
        sig = pd.Series(0, index=px.index, dtype="int8")
        # cross up: go long; cross down: flat (for simplicity)
        sig = sig.mask((rsi.shift(1) < self.lower) & (rsi >= self.lower), 1)
        sig = sig.mask((rsi.shift(1) > self.upper) & (rsi <= self.upper), 0)
        return sig.shift(1).fillna(0).astype("int8")

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        return pd.DataFrame({sym: self._signal_one(df) for sym, df in data.items()}).fillna(0).astype("int8")
