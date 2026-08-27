"""Portable, Mojo-accelerated t1ha2 hashing.

The upstream package's ``hash128`` and ``Hash`` APIs are implemented exactly.
``t1ha2_atonce`` exposes the upstream C library's portable 64-bit primitive.
"""

from __future__ import annotations

import ctypes
import threading

import numpy as np

from ._lib import buffer_address_and_size, lib

MASK64 = (1 << 64) - 1
_RESULTS = threading.local()
_LIB = lib()
_T1HA2_ATONCE = _LIB.mt1_t1ha2_atonce
_T1HA2_ATONCE128 = _LIB.mt1_t1ha2_atonce128
_STREAM_INIT = _LIB.mt1_stream_init
_STREAM_UPDATE = _LIB.mt1_stream_update
_STREAM_FINAL = _LIB.mt1_stream_final


def _seed(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError("seed must be an integer")
    if not 0 <= value <= MASK64:
        raise OverflowError("seed must fit in an unsigned 64-bit integer")
    return value


def _result_buffer() -> tuple[ctypes.Array[ctypes.c_uint64], int]:
    cached = getattr(_RESULTS, "buffer", None)
    if cached is None:
        result = (ctypes.c_uint64 * 2)()
        cached = result, ctypes.addressof(result)
        _RESULTS.buffer = cached
    return cached


def t1ha2_atonce(data: bytes | bytearray | memoryview, seed: int = 0) -> int:
    """Return t1ha2's portable 64-bit at-once hash."""
    data_addr, length = buffer_address_and_size(data)
    return int(_T1HA2_ATONCE(data_addr, length, _seed(seed)))


def hash128(data: bytes | bytearray | memoryview, seed: int = 0) -> tuple[int, int]:
    """Return the upstream-compatible ``(high, low)`` t1ha2-128 digest."""
    data_addr, length = buffer_address_and_size(data)
    result, result_addr = _result_buffer()
    _T1HA2_ATONCE128(data_addr, length, _seed(seed), result_addr)
    return result[0], result[1]


class Hash:
    """Incremental upstream-compatible t1ha2-128 hasher."""

    def __init__(self, seed_x: int, seed_y: int):
        self._state = np.zeros(4, dtype=np.uint64)
        self._buffer = np.zeros(32, dtype=np.uint8)
        self._meta = np.zeros(2, dtype=np.uint64)
        self._finalized = False
        _STREAM_INIT(
            self._state.ctypes.data, self._meta.ctypes.data, _seed(seed_x), _seed(seed_y)
        )

    def update(self, data: bytes | bytearray | memoryview) -> None:
        if self._finalized:
            raise ValueError("cannot update a finalized Hash")
        data_addr, length = buffer_address_and_size(data)
        if length:
            _STREAM_UPDATE(
                self._state.ctypes.data,
                self._buffer.ctypes.data,
                self._meta.ctypes.data,
                data_addr,
                length,
            )

    def final(self) -> tuple[int, int]:
        if self._finalized:
            raise ValueError("Hash.final() may only be called once")
        result, result_addr = _result_buffer()
        _STREAM_FINAL(
            self._state.ctypes.data,
            self._buffer.ctypes.data,
            self._meta.ctypes.data,
            result_addr,
        )
        self._finalized = True
        return result[0], result[1]


__all__ = ["Hash", "hash128", "t1ha2_atonce"]
