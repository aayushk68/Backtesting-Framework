# backtester/dataio.py
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable
import pandas as pd
import yfinance as yf
from pathlib import Path

COLS = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Symbol"]

def download_to_csv(tickers: Iterable[str], start: str, end: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for t in tickers:
        df = yf.download(t, start=start, end=end, auto_adjust=False)
        if df.empty:
            raise ValueError(f"No data for {t}")
        df = df.reset_index()
        df["Symbol"] = t
        df = df[COLS]
        df.to_csv(out / f"{t}.csv", index=False)

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"])
    # This ensures expected colunms
    expected = set(COLS)
    if not expected.issubset(df.columns):
        missing = list(expected - set(df.columns))
        raise ValueError(f"Missing columns in {path}: {missing}")

    # sorting all teh row in ascending date order and removing duplicate dataa entries
    df = df.sort_values("Date").drop_duplicates(subset=["Date"])
    df.set_index("Date", inplace=True)

    # force numeric columns, coerce junk values to NaN
    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # This drop rows that cannot support indicators
    df = df.dropna(subset=["Adj Close"])

    # symbol as clean string using backward and fwd fill
    df["Symbol"] = df["Symbol"].astype(str).ffill().bfill()
    return df

def load_many_csv(paths: Iterable[str], max_workers: int = 4) -> Dict[str, pd.DataFrame]:
    results: Dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(load_csv, p): p for p in paths}
        for fut in as_completed(futs):
            p = futs[fut]
            df = fut.result()
            sym = str(df["Symbol"].iloc[0])
            results[sym] = df
    return results
