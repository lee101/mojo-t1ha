"""Parity checks against the published ``t1ha`` Python package."""

import numpy as np
import pytest

import mojot1ha as mojo

t1ha = pytest.importorskip("t1ha")


@pytest.mark.parametrize("seed", [0, 1, 0x0123456789ABCDEF, (1 << 64) - 1])
@pytest.mark.parametrize("size", [0, 1, 7, 8, 9, 31, 32, 33, 63, 64, 65, 511, 4099])
def test_hash128_matches_upstream(seed, size):
    data = bytes((i * 37 + 11) & 0xFF for i in range(size))
    assert mojo.hash128(data, seed) == t1ha.hash128(data, seed)


@pytest.mark.parametrize("size", [0, 1, 31, 32, 33, 127, 1025])
def test_incremental_hash_matches_upstream(size):
    data = bytes((i * 19 + 7) & 0xFF for i in range(size))
    ours = mojo.Hash(0x0123456789ABCDEF, 0xF0E1D2C3B4A59687)
    upstream = t1ha.Hash(0x0123456789ABCDEF, 0xF0E1D2C3B4A59687)
    for start in range(0, size, 13):
        part = data[start : start + 13]
        if part:
            ours.update(part)
            upstream.update(part)
    assert ours.final() == upstream.final()


@pytest.mark.parametrize(
    ("data", "seed", "expected"),
    [
        (b"", 0, 0x0000000000000000),
        (b"a", 0, 0xE6CC7BB0D4E43351),
        (b"hello world", 42, 0xE61EC36513D5E8A1),
        (bytes(range(64)), 0x0123456789ABCDEF, 0x152FF81F02EDF32B),
        (bytes(range(255)), (1 << 64) - 1, 0x4349F6829731A3C0),
    ],
)
def test_t1ha2_atonce_reference_vectors(data, seed, expected):
    assert mojo.t1ha2_atonce(data, seed) == expected


def test_buffer_inputs_and_lifecycle():
    payload = bytearray(range(80))
    assert mojo.hash128(memoryview(payload), 9) == t1ha.hash128(payload, 9)
    hasher = mojo.Hash(1, 2)
    hasher.update(payload)
    hasher.final()
    with pytest.raises(ValueError):
        hasher.update(b"x")
    with pytest.raises(ValueError):
        hasher.final()


def test_rejects_non_byte_and_strided_buffers():
    with pytest.raises(TypeError, match="byte buffer"):
        mojo.hash128(memoryview(np.array([1, 2], dtype=np.uint16)))
    with pytest.raises(ValueError, match="C-contiguous"):
        mojo.hash128(memoryview(bytearray(range(16)))[::2])


@pytest.mark.parametrize("size", range(0, 97))
def test_streaming_all_split_points_match_upstream(size):
    data = bytes((i * 53 + 17) & 0xFF for i in range(size))
    reference = t1ha.Hash(3, 5)
    reference.update(data)
    expected = reference.final()
    for split in range(size + 1):
        actual = mojo.Hash(3, 5)
        actual.update(data[:split])
        actual.update(data[split:])
        assert actual.final() == expected


@pytest.mark.parametrize(
    "chunks",
    [(5, 27, 17), (17, 15, 33), (24,), (25,), (31,)],
)
def test_streaming_simd_copy_tails_and_final_wrap(chunks):
    size = sum(chunks)
    data = bytes((i * 41 + 9) & 0xFF for i in range(size))
    expected = t1ha.Hash(7, 11)
    expected.update(data)
    actual = mojo.Hash(7, 11)
    start = 0
    for length in chunks:
        actual.update(data[start : start + length])
        start += length
    assert actual.final() == expected.final()


@pytest.mark.parametrize("size", [8, 32, 33, 4099])
def test_misaligned_buffer_matches_upstream(size):
    payload = bytearray(size + 1)
    for index in range(size + 1):
        payload[index] = (index * 23 + 5) & 0xFF
    data = memoryview(payload)[1:]
    assert mojo.hash128(data, 9) == t1ha.hash128(data, 9)


def test_seed_validation():
    with pytest.raises(OverflowError):
        mojo.hash128(b"x", -1)
    with pytest.raises(OverflowError):
        mojo.t1ha2_atonce(b"x", 1 << 64)
    with pytest.raises(TypeError):
        mojo.hash128(b"x", 1.0)
