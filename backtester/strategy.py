# backtester/strategy.py
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd

class Strategy(ABC):
    """
    Base strategy interface.

    Implementations must return a pandas DataFrame (multi-symbol) or Series (single-symbol)
    of integer signals per date where:
      1  = bullish (go/stay long)
      0  = neutreal (hold cash)
     -1  = bearish (sell / go short; for now the engine will map -1 to 'flat' in long-only mode)

    Signals must be aligned to the data's Date index. To avoid lookahead, strategies should
    typically apply .shift(1) so today's signal executes on tomorrow's open.
    """

    @abstractmethod
    def generate_signals(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Parameters
        ----------
        data: dict[symbol -> DataFrame]
            Each DataFrame must be indexed by Date and include at least 'Adj Close' and 'Close'.

        Returns
        -------
        pandas.DataFrame of dtype int in {1, 0, -1} indexed by Date, columns = symbols.
        """
        raise NotImplementedError
