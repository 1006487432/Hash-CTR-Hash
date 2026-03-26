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
from wideblock.algorithms.hctr1 import (
    hctr1_aes_decrypt,
    hctr1_aes_encrypt,
    hctr1_sm4_decrypt,
    hctr1_sm4_encrypt,
)


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


def _check_bytes(actual: bytes, expected: bytes, label: str) -> tuple[bool, str]:
    if actual == expected:
        return True, f"[PASS] {label}"
    return False, f"[FAIL] {label}\nexpected: {expected.hex()}\nactual:   {actual.hex()}"


SM4_KEY = bytes.fromhex(
    "2B7E151628AED2A6ABF7158809CF4F3C"
    "000102030405060708090A0B0C0D0E0F"
)
SM4_TWEAK = bytes.fromhex("F0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF")
SM4_PLAINTEXT = bytes.fromhex(
    "6BC1BEE22E409F96E93D7E117393172A"
    "AE2D8A571E03AC9C9EB76FAC45AF8E51"
    "30C81C46A35CE411E5FBC1191A0A52EF"
    "F69F2445DF4F9B17AD2B417BE66C3710"
)
SM4_CIPHERTEXT = bytes.fromhex(
    "9CD7481D3B7CA904B14B4084D9D4C83E"
    "D39EAC8E16747895FC2AE1EECD220276"
    "AF3D0D2F21CB3807561347C81AD13811"
    "7DD85C652AFE16A47DC68EB884068AE3"
)

AES_ROUNDTRIP_CASES = [
    RoundTripCase("aes0", _sample_bytes("ak0", 32), _sample_bytes("ap0", 16), _sample_bytes("at0", 16)),
    RoundTripCase("aes1", _sample_bytes("ak1", 32), _sample_bytes("ap1", 17), _sample_bytes("at1", 16)),
    RoundTripCase("aes2", _sample_bytes("ak2", 32), _sample_bytes("ap2", 31), _sample_bytes("at2", 16)),
    RoundTripCase("aes3", _sample_bytes("ak3", 32), _sample_bytes("ap3", 64), _sample_bytes("at3", 16)),
    RoundTripCase("aes4", _sample_bytes("ak4", 32), _sample_bytes("ap4", 127), _sample_bytes("at4", 16)),
]

SM4_ROUNDTRIP_CASES = [
    RoundTripCase("sm40", _sample_bytes("sk0", 32), _sample_bytes("sp0", 16), _sample_bytes("st0", 16)),
    RoundTripCase("sm41", _sample_bytes("sk1", 32), _sample_bytes("sp1", 17), _sample_bytes("st1", 16)),
    RoundTripCase("sm42", _sample_bytes("sk2", 32), _sample_bytes("sp2", 31), _sample_bytes("st2", 16)),
    RoundTripCase("sm43", _sample_bytes("sk3", 32), _sample_bytes("sp3", 64), _sample_bytes("st3", 16)),
    RoundTripCase("sm44", _sample_bytes("sk4", 32), _sample_bytes("sp4", 127), _sample_bytes("st4", 16)),
]


def _run_sm4_vector() -> int:
    failed = 0
    enc = hctr1_sm4_encrypt(SM4_KEY, SM4_PLAINTEXT, SM4_TWEAK)
    ok, message = _check_bytes(enc, SM4_CIPHERTEXT, "sm4 standard encrypt")
    print(message)
    failed += 0 if ok else 1

    dec = hctr1_sm4_decrypt(SM4_KEY, SM4_CIPHERTEXT, SM4_TWEAK)
    ok, message = _check_bytes(dec, SM4_PLAINTEXT, "sm4 standard decrypt")
    print(message)
    failed += 0 if ok else 1
    return failed


def main() -> int:
    failed = _run_sm4_vector()
    if run_roundtrip_cases(cases=AES_ROUNDTRIP_CASES, encrypt_fn=hctr1_aes_encrypt, decrypt_fn=hctr1_aes_decrypt) != 0:
        failed += 1
    if run_roundtrip_cases(cases=SM4_ROUNDTRIP_CASES, encrypt_fn=hctr1_sm4_encrypt, decrypt_fn=hctr1_sm4_decrypt) != 0:
        failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
