from __future__ import annotations

import sys
from pathlib import Path
from hashlib import sha256

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.helpers.vector_runner import RoundTripCase, run_roundtrip_cases, run_vector_cases
from wideblock.algorithms.hctr2 import hctr2_aes_decrypt, hctr2_aes_encrypt, hctr2_sm4_decrypt, hctr2_sm4_encrypt
from wideblock.algorithms.hctr2.vectors import load_hctr2_vectors


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


SM4_ROUNDTRIP_CASES = [
    RoundTripCase("sm4_16", _sample_bytes("sk0", 16), _sample_bytes("sp0", 16), _sample_bytes("st0", 0)),
    RoundTripCase("sm4_17", _sample_bytes("sk1", 16), _sample_bytes("sp1", 17), _sample_bytes("st1", 7)),
    RoundTripCase("sm4_31", _sample_bytes("sk2", 16), _sample_bytes("sp2", 31), _sample_bytes("st2", 16)),
    RoundTripCase("sm4_32", _sample_bytes("sk3", 16), _sample_bytes("sp3", 32), _sample_bytes("st3", 31)),
    RoundTripCase("sm4_64", _sample_bytes("sk4", 16), _sample_bytes("sp4", 64), _sample_bytes("st4", 48)),
    RoundTripCase("sm4_127", _sample_bytes("sk5", 16), _sample_bytes("sp5", 127), _sample_bytes("st5", 3)),
]


def main() -> int:
    failed = run_vector_cases(
        vectors=load_hctr2_vectors(),
        encrypt_fn=hctr2_aes_encrypt,
        decrypt_fn=hctr2_aes_decrypt,
    )
    if run_roundtrip_cases(
        cases=SM4_ROUNDTRIP_CASES,
        encrypt_fn=hctr2_sm4_encrypt,
        decrypt_fn=hctr2_sm4_decrypt,
    ) != 0:
        failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
