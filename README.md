# mojo-t1ha

`mojo-t1ha` is a standalone Mojo port of the portable t1ha2 fast non-cryptographic hash family. It provides a small Python package, `mojot1ha`, backed by one compiled Mojo shared library.

It is for checksums, fingerprints, and hash-table-style workloads; it is not a cryptographic hash.

## Coverage

The covered upstream [`t1ha`](https://pypi.org/project/t1ha/) 0.1.0 API is:

- `hash128(data, seed=0) -> (high, low)`, bit-for-bit compatible with upstream.
- `Hash(seed_x, seed_y)`, including `update(data)` and `final() -> (high, low)`, bit-for-bit compatible with upstream t1ha2 streaming.

`t1ha2_atonce(data, seed=0)` additionally exposes the portable upstream C primitive directly. Not included: t1ha0's CPU-dispatched `hash()` API, t1ha0 AES variants, and t1ha1. This package only implements portable t1ha2 output.

## Install and use

```bash
pixi install
pixi run build
```

```python
import sys
sys.path.insert(0, "python")

from mojot1ha import Hash, hash128, t1ha2_atonce

print(hash128(b"hello", 42))
print(t1ha2_atonce(b"hello", 42))

hasher = Hash(1, 2)
hasher.update(b"hello ")
hasher.update(b"world")
print(hasher.final())
```

Run the validation and the locked benchmark with:

```bash
pixi run test
pixi run bench
```

## Benchmark

Measured with `pixi run bench` on Linux 6.8.0-136-generic, x86_64, glibc 2.39. Each measurement is the best of five runs and hashes the same input 400 times.

| case | mojo-t1ha | upstream t1ha | upstream / Mojo | result |
|---|---:|---:|---:|---|
| hash128, 64 B x 400 | 1.87 ms | 0.21 ms | 0.11x | slower |
| hash128, 4,096 B x 400 | 2.06 ms | 0.37 ms | 0.18x | slower |
| hash128, 1,048,576 B x 400 | 46.87 ms | 35.29 ms | 0.75x | slower |

## How it works

All kernels live in one Mojo compilation unit, `src/capi.mojo`, to keep build cost fixed. Python passes contiguous byte-buffer addresses and lengths through `ctypes`; Mojo reconstructs typed pointers at the C ABI boundary, performs little-endian reads and 64-by-64-to-128 mixing, and writes the two 64-bit digest lanes into a caller-owned NumPy array.

The incremental hasher keeps its four `UInt64` state lanes, 32-byte partial block, and counters in NumPy-owned contiguous buffers. No Mojo-side allocation crosses the FFI boundary. The wrapper accepts only one-dimensional, C-contiguous byte buffers and retains the exported buffer through each native call. Tests compare `hash128` and streaming `Hash` directly with the installed upstream `t1ha` package, and test `t1ha2_atonce` against fixed vectors generated from the upstream C implementation.

The CPU kernel uses aligned native 64-bit reads, with a bytewise fallback for unaligned buffer views. Its 32-byte state transition depends on the preceding transition, so blocks cannot be safely SIMD-vectorized or parallelized within one hash. No GPU path is included.
