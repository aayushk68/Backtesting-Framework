# examples/threaded_data_load.py
from __future__ import annotations
import argparse, os, time, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

"""
Threaded CSV loader demo (I/O-bound).

- Duplicates one existing CSV into N files in a temp folder (to control workload).
- Adds optional per-file latency (--io-latency-ms) to simulate network/disk delay.
- Compares sequential vs threaded load time and prints speedup.

This demonstrates that for I/O-bound tasks, threads can overlap waiting time and
achieve >= 2x speedup under realistic latency and enough files.
"""

DATA_DIR = Path("data")
DUP_DIR = DATA_DIR / "_dup_demo"

def make_dataset(n: int) -> list[Path]:
    DUP_DIR.mkdir(parents=True, exist_ok=True)

    # pick any existing CSV (AAPL/MSFT/GOOGL); fall back to creating a tiny one
    candidates = [p for p in DATA_DIR.glob("*.csv")]
    if not candidates:
        tiny = DATA_DIR / "SYNTH.csv"
        DATA_DIR.mkdir(exist_ok=True)
        pd.DataFrame({
            "Date": pd.date_range("2021-01-01", periods=100, freq="D"),
            "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Adj Close": 100.5, "Volume": 1000000
        }).to_csv(tiny, index=False)
        candidates = [tiny]

    src = candidates[0]
    paths = []
    # clean dup dir
    for p in DUP_DIR.glob("*.csv"):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    # duplicate into N files
    for i in range(n):
        dst = DUP_DIR / f"demo_{i:03d}.csv"
        shutil.copyfile(src, dst)
        paths.append(dst)
    return paths

def load_one(path: Path, io_latency_ms: int = 0) -> pd.DataFrame:
    # simulate network/disk latency (only for demo reproducibility)
    if io_latency_ms > 0:
        time.sleep(io_latency_ms / 1000.0)
    df = pd.read_csv(path)
    # light cleaning 
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    return df

def load_sequential(paths: list[Path], io_latency_ms: int) -> tuple[list[pd.DataFrame], float]:
    t0 = time.perf_counter()
    out = [load_one(p, io_latency_ms) for p in paths]
    dt = time.perf_counter() - t0
    return out, dt

def load_threaded(paths: list[Path], max_workers: int, io_latency_ms: int) -> tuple[list[pd.DataFrame], float]:
    t0 = time.perf_counter()
    out = [None] * len(paths)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(load_one, p, io_latency_ms): i for i, p in enumerate(paths)}
        for fut in as_completed(futs):
            i = futs[fut]
            out[i] = fut.result()
    dt = time.perf_counter() - t0
    return out, dt

def main():
    ap = argparse.ArgumentParser(description="Threaded CSV loading demo with controllable I/O latency.")
    ap.add_argument("--n", type=int, default=40, help="Number of files to load (duplicates of an existing CSV).")
    ap.add_argument("--max-workers", type=int, default=16, help="Thread pool size.")
    ap.add_argument("--io-latency-ms", type=int, default=30, help="Per-file artificial latency (ms) to simulate I/O.")
    args = ap.parse_args()

    paths = make_dataset(args.n)

    # Sequential
    seq_out, seq_t = load_sequential(paths, args.io_latency_ms)

    # Threaded
    thr_out, thr_t = load_threaded(paths, args.max_workers, args.io_latency_ms)

    # Results
    print("\n=== Threaded Loader Demo ===")
    print(f"Files     : {len(paths)}")
    print(f"Latency   : {args.io_latency_ms} ms per file (simulated)")
    print(f"Workers   : {args.max_workers}")
    print(f"Sequential: {seq_t:.3f}s")
    print(f"Threaded  : {thr_t:.3f}s")
    speedup = seq_t / max(thr_t, 1e-9)
    print(f"Speedup   : {speedup:.2f}x")
    print(f"Loaded (seq,thr): {len(seq_out)}, {len(thr_out)}")

if __name__ == "__main__":
    main()
