"""ctypes loader for the compiled Mojo t1ha2 kernels."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get("MOJOT1HA_LIB") or os.path.join(ROOT, "dist", "libmojo-t1ha.so")
I = ctypes.c_int64
U = ctypes.c_uint64
_PY_BYTES_AS_STRING = ctypes.pythonapi.PyBytes_AsString
_PY_BYTES_AS_STRING.argtypes = [ctypes.py_object]
_PY_BYTES_AS_STRING.restype = ctypes.c_void_p

_SIGNATURES = {
    "mt1_t1ha2_atonce": ([I, I, U], U),
    "mt1_t1ha2_atonce128": ([I, I, U, I], None),
    "mt1_stream_init": ([I, I, U, U], None),
    "mt1_stream_update": ([I, I, I, I, I], None),
    "mt1_stream_final": ([I, I, I, I], None),
}


class BuildError(RuntimeError):
    pass


def build(force: bool = False) -> str:
    """Build the shared library when it is missing or stale."""
    source = os.path.join(ROOT, "src", "capi.mojo")
    if os.environ.get("MOJOT1HA_LIB") and os.path.exists(LIB) and not force:
        return LIB
    if not force and os.path.exists(LIB) and os.path.getmtime(LIB) >= os.path.getmtime(source):
        return LIB
    pixi = shutil.which("pixi") or os.path.expanduser("~/.pixi/bin/pixi")
    cmd = [pixi, "run", "--manifest-path", os.path.join(ROOT, "pixi.toml"), "build"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode or not os.path.exists(LIB):
        raise BuildError((proc.stderr or proc.stdout).strip()[:4000])
    return LIB


_loaded: ctypes.CDLL | None = None


def lib() -> ctypes.CDLL:
    global _loaded
    if _loaded is None:
        _loaded = ctypes.CDLL(build())
        for name, (argtypes, restype) in _SIGNATURES.items():
            fn = getattr(_loaded, name)
            fn.argtypes = argtypes
            fn.restype = restype
    return _loaded


def bytes_view(data: bytes | bytearray | memoryview) -> np.ndarray:
    """Return a C-contiguous, one-dimensional unsigned-byte view of *data*.

    Keeping this validation here makes the address/length pair handed to Mojo
    describe precisely the bytes exposed by the Python object.  In particular,
    strided views cannot be represented by the C ABI used by the kernel.
    """
    try:
        view = memoryview(data)
    except TypeError as exc:
        raise TypeError("data must support the buffer protocol") from exc
    if view.ndim != 1 or not view.c_contiguous:
        raise ValueError("data must be a one-dimensional C-contiguous buffer")
    if view.format not in {"B", "b", "c"}:
        raise TypeError("data must be a byte buffer (format 'B', 'b', or 'c')")
    # Normalise signed and character byte views without copying; the view owns
    # a reference to its exporter for the entire native call.
    view = view.cast("B")
    return np.frombuffer(view, dtype=np.uint8)


def buffer_address_and_size(data: bytes | bytearray | memoryview) -> tuple[int, int]:
    if isinstance(data, bytes):
        return int(_PY_BYTES_AS_STRING(data)), len(data)
    source = bytes_view(data)
    # The caller retains its ``data`` argument through the following ctypes
    # call, so the exporter remains live while Mojo reads this address.
    return int(source.ctypes.data), int(source.size)


def main() -> int:
    print(build(force="--force" in sys.argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
