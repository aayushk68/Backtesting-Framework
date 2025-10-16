# tests/test_dataio.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
import pandas.testing as pdt
import types

from backtester.dataio import load_csv, load_many_csv, download_to_csv

def _make_csv(path: Path, symbol: str = "SYN"):
    df = pd.DataFrame({
        "Date": pd.date_range("2022-01-01", periods=5, freq="D"),
        "Open": [1,2,3,4,5],
        "High": [2,3,4,5,6],
        "Low":  [0,1,2,3,4],
        "Close":[1.5,2.5,3.5,4.5,5.5],
        "Adj Close":[1.5,2.5,3.5,4.5,5.5],
        "Volume":[100,200,300,400,500],
        "Symbol":[symbol]*5,
    })
    df.to_csv(path, index=False)

def test_load_csv_and_many(tmp_path: Path):
    d = tmp_path / "data"; d.mkdir()
    a = d / "A.csv"; b = d / "B.csv"
    _make_csv(a, "AAA"); _make_csv(b, "BBB")

    df_a = load_csv(str(a))
    df_b = load_csv(str(b))
    assert df_a.index.is_monotonic_increasing
    assert df_a.shape[0] == 5
    assert df_a.loc[df_a.index[0], "Symbol"] == "AAA"

    res = load_many_csv([str(a), str(b)], max_workers=2)
    assert set(res.keys()) == {"AAA", "BBB"}
    pdt.assert_frame_equal(res["AAA"], df_a)
    pdt.assert_frame_equal(res["BBB"], df_b)

def test_download_to_csv_mocked(tmp_path: Path, monkeypatch):
    # Mock yfinance.download → return a deterministic frame
    import backtester.dataio as dataio
    def fake_download(ticker, start=None, end=None, auto_adjust=False):
        idx = pd.date_range("2022-01-01", periods=3, freq="D")
        df = pd.DataFrame({
            "Open":[1,2,3], "High":[2,3,4], "Low":[0,1,2],
            "Close":[1.1,2.1,3.1], "Adj Close":[1.1,2.1,3.1], "Volume":[10,20,30],
        }, index=idx)
        df.index.name = "Date"
        return df
    monkeypatch.setattr(dataio.yf, "download", fake_download)

    out = tmp_path / "d"; out.mkdir()
    dataio.download_to_csv(["XYZ","QRS"], "2022-01-01", "2022-01-03", str(out))
    for t in ["XYZ","QRS"]:
        p = out / f"{t}.csv"
        assert p.exists()
        df = pd.read_csv(p)
        assert (df["Symbol"] == t).all()
        assert set(["Date","Open","High","Low","Close","Adj Close","Volume","Symbol"]).issubset(df.columns)
