"""Benchmark Mojo t1ha2 against the upstream Cython extension."""

from __future__ import annotations

import os
import platform
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import mojot1ha as mojo
import t1ha


def best_time(fn, repeat: int = 5) -> float:
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def run_many(fn, data: bytes, count: int = 400) -> None:
    for seed in range(count):
        fn(data, seed)


def main() -> None:
    print(f"Machine: {platform.platform()} ({platform.machine()})")
    print("| case | mojo-t1ha | upstream t1ha | upstream / Mojo | result |")
    print("|---|---:|---:|---:|---|")
    for size in (64, 4096, 1_048_576):
        data = bytes((i * 29 + 3) & 0xFF for i in range(size))
        mojo.hash128(data, 0)
        t1ha.hash128(data, 0)
        ours = best_time(lambda: run_many(mojo.hash128, data))
        upstream = best_time(lambda: run_many(t1ha.hash128, data))
        ratio = upstream / ours
        result = "faster" if ratio > 1 else "slower"
        print(
            f"| hash128, {size:,} B x 400 | {ours * 1e3:.2f} ms | "
            f"{upstream * 1e3:.2f} ms | {ratio:.2f}x | {result} |"
        )


if __name__ == "__main__":
    main()
