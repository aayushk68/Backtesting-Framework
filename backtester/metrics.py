# backtester/metrics.py
from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict
from .portfolio import Fill

TRADING_DAYS = 252

# ---- equity-curve metrics ----

def total_return(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)

def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0)

def sharpe(equity: pd.Series, rf: float = 0.0) -> float:
    rets = equity.pct_change().dropna()
    if len(rets) == 0:
        return 0.0
    excess = rets - rf / TRADING_DAYS
    mu = float(excess.mean())
    sd = float(excess.std(ddof=1))
    if sd == 0:
        return 0.0
    return float((mu / sd) * np.sqrt(TRADING_DAYS))

def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return float(dd.min()) if len(dd) > 0 else 0.0

# ---- trade-level analytics (this hanldes flips) ----

@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    side: str          # "LONG" or "SHORT"
    qty: int
    entry_amount: float    # long: cost (+comm); short: proceeds (net of comm)
    exit_amount: float     # long: proceeds (net); short: cost (+comm)
    pnl: float
    duration_days: int

def round_trip_trades(fills: List[Fill]) -> List[Trade]:
    """
    Reconstruct round trips per symbol. Supports:
      - partial entries/exits
      - direct flips (long -> short, short -> long) within a single fill
    Conventions:
      LONG trade: entry_amount = Σ(buy cost + comm), exit_amount = Σ(sell proceeds - comm), pnl = exit - entry
      SHORT trade: entry_amount = Σ(sell proceeds - comm), exit_amount = Σ(buy cost + comm), pnl = entry - exit
    """
    trades: List[Trade] = []
    if not fills:
        return trades

    df = pd.DataFrame([{
        "date": pd.Timestamp(f.date),
        "symbol": str(f.symbol),
        "side": str(f.side).upper(),
        "qty": int(f.qty),
        "price": float(f.price),
        "commission": float(f.commission),
    } for f in fills]).sort_values(["symbol", "date"]).reset_index(drop=True)

    # state per symbol
    state: Dict[str, Dict] = {}
    for _, r in df.iterrows():
        sym = r["symbol"]; side = r["side"]; dt = r["date"]
        qty = int(r["qty"]); px = float(r["price"]); comm = float(r["commission"])
        per_share_comm = comm / qty if qty > 0 else 0.0

        s = state.get(sym, {
            "pos": 0,                # shares (can be negative)
            "entry_side": None,      # "LONG" or "SHORT"
            "entry_date": None,
            "entry_amt": 0.0,        # long: buy cost + comm; short: sell proceeds - comm
            "exit_amt": 0.0,         # accumulates against the open trade
        })

        def close_trade(exit_date: pd.Timestamp):
            # finalize open trade if any
            if s["entry_side"] is None or s["pos"] != 0:
                return
            side_ = s["entry_side"]
            entry_amt = float(s["entry_amt"])
            exit_amt = float(s["exit_amt"])
            if side_ == "LONG":
                pnl = exit_amt - entry_amt
                qty_closed = s.get("qty_total", 0)
            else:  # SHORT
                pnl = entry_amt - exit_amt
                qty_closed = s.get("qty_total", 0)
            duration = max(1, (exit_date - s["entry_date"]).days)
            trades.append(Trade(sym, s["entry_date"], exit_date, side_, int(qty_closed),
                                entry_amt, exit_amt, float(pnl), duration))
            # reset
            s["entry_side"] = None
            s["entry_date"] = None
            s["entry_amt"] = 0.0
            s["exit_amt"] = 0.0
            s["qty_total"] = 0

        # helpers to add legs
        def add_long_entry(q):
            s["entry_side"] = "LONG" if s["entry_side"] is None else s["entry_side"]
            if s["entry_date"] is None:
                s["entry_date"] = dt
            s["entry_amt"] += q * (px + per_share_comm)   # cost
            s["qty_total"] = s.get("qty_total", 0) + q

        def add_long_exit(q):
            s["exit_amt"] += q * (px - per_share_comm)    # proceeds

        def add_short_entry(q):
            s["entry_side"] = "SHORT" if s["entry_side"] is None else s["entry_side"]
            if s["entry_date"] is None:
                s["entry_date"] = dt
            s["entry_amt"] += q * (px - per_share_comm)   # proceeds from sell
            s["qty_total"] = s.get("qty_total", 0) + q

        def add_short_exit(q):
            s["exit_amt"] += q * (px + per_share_comm)    # cost to buy back

        if side == "BUY":
            if s["pos"] >= 0:
                # increasing/starting LONG
                add_long_entry(qty)
                s["pos"] += qty
            else:
                # covering SHORT (and maybe flipping to LONG)
                cover = min(qty, -s["pos"])
                if cover > 0:
                    add_short_exit(cover)
                    s["pos"] += cover
                    if s["pos"] == 0:
                        close_trade(dt)
                rem = qty - cover
                if rem > 0:
                    # start/increase LONG with remainder (flip)
                    add_long_entry(rem)
                    s["pos"] += rem

        else:  # SELL
            if s["pos"] <= 0:
                # increasing/starting SHORT
                add_short_entry(qty)
                s["pos"] -= qty
            else:
                # exiting LONG (and maybe flipping to SHORT)
                exitq = min(qty, s["pos"])
                if exitq > 0:
                    add_long_exit(exitq)
                    s["pos"] -= exitq
                    if s["pos"] == 0:
                        close_trade(dt)
                rem = qty - exitq
                if rem > 0:
                    # start/increase SHORT with remainder (flip)
                    add_short_entry(rem)
                    s["pos"] -= rem

        state[sym] = s

    # no forced liquidation at end (open trades remain open)
    return trades

def trade_statistics(trades: List[Trade]) -> Dict[str, float]:
    if not trades:
        return {"num_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "avg_duration_days": 0.0, "gross_profit": 0.0, "gross_loss": 0.0}
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]

    num = len(trades)
    win_rate = 100.0 * len(wins) / num if num else 0.0
    gross_profit = float(sum(wins)) if wins else 0.0
    gross_loss = float(sum(losses)) if losses else 0.0
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0
    avg_duration = float(np.mean([t.duration_days for t in trades])) if trades else 0.0

    return {
        "num_trades": float(num),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_duration_days": float(avg_duration),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
    }
