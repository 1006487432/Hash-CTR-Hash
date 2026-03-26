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
from wideblock.algorithms.xcbstar import (
    xcbstar_aes_decrypt,
    xcbstar_aes_encrypt,
    xcbstar_sm4_decrypt,
    xcbstar_sm4_encrypt,
)


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


AES_CASES = [
    RoundTripCase("aes0", _sample_bytes("ak0", 16), _sample_bytes("ap0", 16), b""),
    RoundTripCase("aes1", _sample_bytes("ak1", 16), _sample_bytes("ap1", 17), _sample_bytes("at1", 1)),
    RoundTripCase("aes2", _sample_bytes("ak2", 16), _sample_bytes("ap2", 31), _sample_bytes("at2", 16)),
    RoundTripCase("aes3", _sample_bytes("ak3", 16), _sample_bytes("ap3", 48), _sample_bytes("at3", 31)),
    RoundTripCase("aes4", _sample_bytes("ak4", 16), _sample_bytes("ap4", 64), _sample_bytes("at4", 48)),
    RoundTripCase("aes5", _sample_bytes("ak5", 16), _sample_bytes("ap5", 127), _sample_bytes("at5", 7)),
    RoundTripCase("aes6", _sample_bytes("ak6", 16), _sample_bytes("ap6", 255), _sample_bytes("at6", 33)),
]

SM4_CASES = [
    RoundTripCase("sm40", _sample_bytes("sk0", 16), _sample_bytes("sp0", 16), b""),
    RoundTripCase("sm41", _sample_bytes("sk1", 16), _sample_bytes("sp1", 17), _sample_bytes("st1", 1)),
    RoundTripCase("sm42", _sample_bytes("sk2", 16), _sample_bytes("sp2", 31), _sample_bytes("st2", 16)),
    RoundTripCase("sm43", _sample_bytes("sk3", 16), _sample_bytes("sp3", 48), _sample_bytes("st3", 31)),
    RoundTripCase("sm44", _sample_bytes("sk4", 16), _sample_bytes("sp4", 64), _sample_bytes("st4", 48)),
    RoundTripCase("sm45", _sample_bytes("sk5", 16), _sample_bytes("sp5", 127), _sample_bytes("st5", 7)),
    RoundTripCase("sm46", _sample_bytes("sk6", 16), _sample_bytes("sp6", 255), _sample_bytes("st6", 33)),
]


def main() -> int:
    failed = 0
    if run_roundtrip_cases(cases=AES_CASES, encrypt_fn=xcbstar_aes_encrypt, decrypt_fn=xcbstar_aes_decrypt) != 0:
        failed += 1
    if run_roundtrip_cases(cases=SM4_CASES, encrypt_fn=xcbstar_sm4_encrypt, decrypt_fn=xcbstar_sm4_decrypt) != 0:
        failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
