from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.helpers.vector_runner import RoundTripCase, run_roundtrip_cases
from wideblock.algorithms.xcbv2 import xcb_sm4_decrypt, xcb_sm4_encrypt


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


ROUNDTRIP_CASES = [
    RoundTripCase("case0", b"\x00" * 16, _sample_bytes("p0", 16), b""),
    RoundTripCase("case1", _sample_bytes("k1", 16), _sample_bytes("p1", 17), b""),
    RoundTripCase("case2", _sample_bytes("k2", 16), _sample_bytes("p2", 31), _sample_bytes("a2", 1)),
    RoundTripCase("case3", _sample_bytes("k3", 16), _sample_bytes("p3", 32), _sample_bytes("a3", 16)),
    RoundTripCase("case4", _sample_bytes("k4", 16), _sample_bytes("p4", 48), _sample_bytes("a4", 31)),
    RoundTripCase("case5", _sample_bytes("k5", 16), _sample_bytes("p5", 64), _sample_bytes("a5", 48)),
    RoundTripCase("case6", _sample_bytes("k6", 16), _sample_bytes("p6", 127), _sample_bytes("a6", 7)),
    RoundTripCase("case7", _sample_bytes("k7", 16), _sample_bytes("p7", 128), _sample_bytes("a7", 64)),
]


def main() -> int:
    return run_roundtrip_cases(
        cases=ROUNDTRIP_CASES,
        encrypt_fn=xcb_sm4_encrypt,
        decrypt_fn=xcb_sm4_decrypt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
