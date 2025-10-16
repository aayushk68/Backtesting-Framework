from __future__ import annotations
from dataclasses import dataclass
import time
from contextlib import contextmanager

@contextmanager
def timed(section: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        dur = time.perf_counter() - start
        print(f"[timed] {section}: {dur:.3f}s")
