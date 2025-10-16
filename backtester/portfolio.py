from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import pandas as pd
import math

@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_cost: float = 0.0

@dataclass
class Fill:
    date: pd.Timestamp
    symbol: str
    side: str  # BUY/SELL
    qty: int
    price: float
    commission: float
    cash_after: float
    equity_after: float

@dataclass
class Portfolio:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    fills: List[Fill] = field(default_factory=list)

    def market_value(self, prices: Dict[str, float]) -> float:
        mv = 0.0
        for sym, pos in self.positions.items():
            mv += pos.qty * prices.get(sym, 0.0)
        return mv

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def _apply_fill(self, date, symbol, side, qty, price, commission, prices_now: Dict[str, float]):
        pos = self.positions.setdefault(symbol, Position(symbol))
        notional = qty * price
        if side == "BUY":
            self.cash -= notional + commission
            new_qty = pos.qty + qty
            pos.avg_cost = (pos.avg_cost * pos.qty + notional) / new_qty if new_qty else 0.0
            pos.qty = new_qty
        else:
            self.cash += notional - commission
            pos.qty -= qty
            if pos.qty == 0:
                pos.avg_cost = 0.0
        self.fills.append(Fill(date, symbol, side, qty, price, commission, self.cash, self.equity(prices_now)))
