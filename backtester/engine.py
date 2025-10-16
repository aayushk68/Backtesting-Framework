# backtester/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .portfolio import Fill


@dataclass
class Costs:
    commission_rate: float = 0.001   # 0.1%
    slippage_rate: float = 0.0005    # 0.05%


class Backtester:
    """
    Next-bar execution backtester.

    - Signals are integers in {-1, 0, 1} per symbol per day.
    - execute at the *next day's Open* (no look-ahead).
    - Equity is marked daily at Close.
    - No daily rebalancing:  only trase when the signal CHANGES.
    - Shorts are optional (allow_shorts=False by default).
    - Fixed per-symbol budget based on initial capital (stable sizing).
    """

    def __init__(
        self,
        data: Dict[str, pd.DataFrame],
        strategy,
        initial_capital: float = 100_000.0,
        costs: Costs = Costs(),
        allow_shorts: bool = False,   # <--- default is long-only
    ):
        self.data = data
        self.strategy = strategy
        self.initial_capital = float(initial_capital)
        self.costs = costs
        self.allow_shorts = bool(allow_shorts)

        # Portfolio state
        self.cash: float = float(initial_capital)
        self.positions: Dict[str, int] = {sym: 0 for sym in data.keys()}
        self.fills: List[Fill] = []

        # Common trading calendar (intersection of all symbol)
        idx = None
        for df in self.data.values():
            idx = df.index if idx is None else idx.intersection(df.index)
        self.calendar = idx.sort_values()

        # Fixed per-symbol budget (simple & stable)
        n_symbols = max(1, len(self.positions))
        self.per_symbol_budget = (self.initial_capital * 0.95) / n_symbols

    # ----- helpers -----

    def _exec_price(self, side: str, px: float) -> float:
        """Apply slippage against it."""
        if side == "BUY":
            return px * (1.0 + self.costs.slippage_rate)
        else:
            return px * (1.0 - self.costs.slippage_rate)

    def _commission(self, notional: float) -> float:
        return abs(notional) * self.costs.commission_rate

    def _mark_to_market(self, dt: pd.Timestamp) -> float:
        mv = 0.0
        for sym, df in self.data.items():
            close_px = float(df.loc[dt, "Close"])
            mv += self.positions.get(sym, 0) * close_px
        return float(self.cash + mv)

    # ----- core run -----

    def run(self) -> pd.DataFrame:
        # Generate signals and align
        raw = self.strategy.generate_signals(self.data)           # {-1,0,1}
        signals = raw.reindex(self.calendar).fillna(0).astype(int)

        # Track previous day's target per symbol to detect changes
        prev_target: Dict[str, int] = {sym: 0 for sym in signals.columns}

        equity_curve = []
        dates = list(self.calendar)

        # trade at next day's open, so stop at second-to-last date
        for i in range(len(dates) - 1):
            dt = dates[i]
            next_dt = dates[i + 1]

            today = signals.loc[dt]  # Series per symbol for today

            for sym in signals.columns:
                # Map -1 to flat if shorts are disabled
                tgt_raw = int(today[sym])           # -1/0/1 from strategy
                if not self.allow_shorts:
                    target = 1 if tgt_raw == 1 else 0
                else:
                    target = tgt_raw                # real shorts enabled

                # Did the target change vs previous day?
                if target == prev_target[sym]:
                    continue  # no trade unless the signal changed

                #will trade at next session's Open
                open_px = float(self.data[sym].loc[next_dt, "Open"])
                fill_side = None
                fill_qty = 0

                # Current position
                cur_qty = int(self.positions.get(sym, 0))

                #If need to EXIT existing position first (including flips):
                if cur_qty != 0 and target == 0:
                    # close to zero
                    side = "SELL" if cur_qty > 0 else "BUY"
                    price = self._exec_price(side, open_px)
                    qty = abs(cur_qty)

                    # BUY needs cash guard (covers shorts or opens long). SELL provides cash.
                    if side == "BUY":
                        per_share_total = price * (1.0 + self.costs.commission_rate)
                        max_afford = int(max(0.0, self.cash // per_share_total))
                        qty = min(qty, max_afford)
                        if qty == 0:
                            # can't afford to cover now (unlikely with given sizing); skip
                            pass

                    notional = qty * price
                    comm = self._commission(notional)
                    if side == "BUY":
                        self.cash -= (notional + comm)
                        self.positions[sym] = cur_qty + qty
                    else:
                        self.cash += (notional - comm)
                        self.positions[sym] = cur_qty - qty

                    self.fills.append(Fill(
                        date=pd.Timestamp(next_dt), symbol=sym, side=side, qty=qty,
                        price=price, commission=comm, cash_after=self.cash,
                        equity_after=self._mark_to_market(dt)
                    ))
                    cur_qty = int(self.positions[sym])  # update

                elif cur_qty != 0 and target != 0 and (target > 0 > cur_qty or target < 0 < cur_qty):
                    # flip through zero in one session: close first
                    side = "SELL" if cur_qty > 0 else "BUY"
                    price = self._exec_price(side, open_px)
                    qty = abs(cur_qty)
                    if side == "BUY":
                        per_share_total = price * (1.0 + self.costs.commission_rate)
                        max_afford = int(max(0.0, self.cash // per_share_total))
                        qty = min(qty, max_afford)
                        if qty == 0:
                            pass
                    notional = qty * price
                    comm = self._commission(notional)
                    if side == "BUY":
                        self.cash -= (notional + comm)
                        self.positions[sym] = cur_qty + qty
                    else:
                        self.cash += (notional - comm)
                        self.positions[sym] = cur_qty - qty
                    self.fills.append(Fill(
                        date=pd.Timestamp(next_dt), symbol=sym, side=side, qty=qty,
                        price=price, commission=comm, cash_after=self.cash,
                        equity_after=self._mark_to_market(dt)
                    ))
                    cur_qty = int(self.positions[sym])

                #If need to ENTER a new position (target != 0 and it is flat)
                if target != 0 and self.positions[sym] == 0:
                    # fixed per-symbol notional from initial capital
                    price = self._exec_price("BUY" if target > 0 else "SELL", open_px)
                    shares = int(self.per_symbol_budget // price)
                    if shares <= 0:
                        prev_target[sym] = target
                        continue

                    side = "BUY" if target > 0 else "SELL"

                    # BUY needs cash guard
                    if side == "BUY":
                        per_share_total = price * (1.0 + self.costs.commission_rate)
                        max_afford = int(max(0.0, self.cash // per_share_total))
                        shares = min(shares, max_afford)
                        if shares == 0:
                            prev_target[sym] = target
                            continue

                    notional = shares * price
                    comm = self._commission(notional)
                    if side == "BUY":
                        self.cash -= (notional + comm)
                        self.positions[sym] = shares
                    else:
                        self.cash += (notional - comm)
                        self.positions[sym] = -shares

                    self.fills.append(Fill(
                        date=pd.Timestamp(next_dt), symbol=sym, side=side, qty=shares,
                        price=price, commission=comm, cash_after=self.cash,
                        equity_after=self._mark_to_market(dt)
                    ))

                # update prev target for this symbol
                prev_target[sym] = target

            # end-of-day mark on dt
            equity_curve.append((dt, self._mark_to_market(dt)))

        # final day EOD mark
        last_dt = dates[-1]
        equity_curve.append((last_dt, self._mark_to_market(last_dt)))

        eq_df = pd.DataFrame(equity_curve, columns=["Date", "Equity"]).set_index("Date")

        # expose pseudo-portfolio for compatibility with examples
        class _PP: pass
        self.portfolio = _PP()
        self.portfolio.cash = self.cash
        self.portfolio.positions = {sym: type("P", (), {"qty": q}) for sym, q in self.positions.items()}
        self.portfolio.fills = self.fills

        return eq_df
