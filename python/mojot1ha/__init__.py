"""Portable, Mojo-accelerated t1ha2 hashing.

The upstream package's ``hash128`` and ``Hash`` APIs are implemented exactly.
``t1ha2_atonce`` exposes the upstream C library's portable 64-bit primitive.
"""

from __future__ import annotations

import threading

import numpy as np

from ._lib import buffer_address_and_size, lib

MASK64 = (1 << 64) - 1
_RESULTS = threading.local()


def _seed(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError("seed must be an integer")
    if not 0 <= value <= MASK64:
        raise OverflowError("seed must fit in an unsigned 64-bit integer")
    return value


def _result_buffer() -> np.ndarray:
    result = getattr(_RESULTS, "buffer", None)
    if result is None:
        result = np.empty(2, dtype=np.uint64)
        _RESULTS.buffer = result
    return result


def t1ha2_atonce(data: bytes | bytearray | memoryview, seed: int = 0) -> int:
    """Return t1ha2's portable 64-bit at-once hash."""
    data_addr, length = buffer_address_and_size(data)
    return int(lib().mt1_t1ha2_atonce(data_addr, length, _seed(seed)))


def hash128(data: bytes | bytearray | memoryview, seed: int = 0) -> tuple[int, int]:
    """Return the upstream-compatible ``(high, low)`` t1ha2-128 digest."""
    data_addr, length = buffer_address_and_size(data)
    result = _result_buffer()
    lib().mt1_t1ha2_atonce128(data_addr, length, _seed(seed), result.ctypes.data)
    return int(result[0]), int(result[1])


class Hash:
    """Incremental upstream-compatible t1ha2-128 hasher."""

    def __init__(self, seed_x: int, seed_y: int):
        self._state = np.zeros(4, dtype=np.uint64)
        self._buffer = np.zeros(32, dtype=np.uint8)
        self._meta = np.zeros(2, dtype=np.uint64)
        self._finalized = False
        lib().mt1_stream_init(
            self._state.ctypes.data, self._meta.ctypes.data, _seed(seed_x), _seed(seed_y)
        )

    def update(self, data: bytes | bytearray | memoryview) -> None:
        if self._finalized:
            raise ValueError("cannot update a finalized Hash")
        data_addr, length = buffer_address_and_size(data)
        if length:
            lib().mt1_stream_update(
                self._state.ctypes.data,
                self._buffer.ctypes.data,
                self._meta.ctypes.data,
                data_addr,
                length,
            )

    def final(self) -> tuple[int, int]:
        if self._finalized:
            raise ValueError("Hash.final() may only be called once")
        result = _result_buffer()
        lib().mt1_stream_final(
            self._state.ctypes.data,
            self._buffer.ctypes.data,
            self._meta.ctypes.data,
            result.ctypes.data,
        )
        self._finalized = True
        return int(result[0]), int(result[1])


__all__ = ["Hash", "hash128", "t1ha2_atonce"]
