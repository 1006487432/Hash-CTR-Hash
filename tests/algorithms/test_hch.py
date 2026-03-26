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
from wideblock.algorithms.hch import hch_aes_decrypt, hch_aes_encrypt, hch_sm4_decrypt, hch_sm4_encrypt


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


AES_CASES = [
    RoundTripCase("aes128_16", _sample_bytes("ak0", 16), _sample_bytes("ap0", 16), _sample_bytes("at0", 16)),
    RoundTripCase("aes128_17", _sample_bytes("ak1", 16), _sample_bytes("ap1", 17), _sample_bytes("at1", 16)),
    RoundTripCase("aes192_31", _sample_bytes("ak2", 24), _sample_bytes("ap2", 31), _sample_bytes("at2", 16)),
    RoundTripCase("aes256_32", _sample_bytes("ak3", 32), _sample_bytes("ap3", 32), _sample_bytes("at3", 16)),
    RoundTripCase("aes128_48", _sample_bytes("ak4", 16), _sample_bytes("ap4", 48), _sample_bytes("at4", 16)),
    RoundTripCase("aes192_64", _sample_bytes("ak5", 24), _sample_bytes("ap5", 64), _sample_bytes("at5", 16)),
    RoundTripCase("aes256_127", _sample_bytes("ak6", 32), _sample_bytes("ap6", 127), _sample_bytes("at6", 16)),
    RoundTripCase("aes128_128", _sample_bytes("ak7", 16), _sample_bytes("ap7", 128), _sample_bytes("at7", 16)),
    RoundTripCase("aes256_255", _sample_bytes("ak8", 32), _sample_bytes("ap8", 255), _sample_bytes("at8", 16)),
]

SM4_CASES = [
    RoundTripCase("sm4_16", _sample_bytes("sk0", 16), _sample_bytes("sp0", 16), _sample_bytes("st0", 16)),
    RoundTripCase("sm4_17", _sample_bytes("sk1", 16), _sample_bytes("sp1", 17), _sample_bytes("st1", 16)),
    RoundTripCase("sm4_31", _sample_bytes("sk2", 16), _sample_bytes("sp2", 31), _sample_bytes("st2", 16)),
    RoundTripCase("sm4_32", _sample_bytes("sk3", 16), _sample_bytes("sp3", 32), _sample_bytes("st3", 16)),
    RoundTripCase("sm4_64", _sample_bytes("sk4", 16), _sample_bytes("sp4", 64), _sample_bytes("st4", 16)),
    RoundTripCase("sm4_127", _sample_bytes("sk5", 16), _sample_bytes("sp5", 127), _sample_bytes("st5", 16)),
    RoundTripCase("sm4_255", _sample_bytes("sk6", 16), _sample_bytes("sp6", 255), _sample_bytes("st6", 16)),
]


def main() -> int:
    failed = 0
    if run_roundtrip_cases(cases=AES_CASES, encrypt_fn=hch_aes_encrypt, decrypt_fn=hch_aes_decrypt) != 0:
        failed += 1
    if run_roundtrip_cases(cases=SM4_CASES, encrypt_fn=hch_sm4_encrypt, decrypt_fn=hch_sm4_decrypt) != 0:
        failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
