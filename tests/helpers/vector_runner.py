from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence

from wideblock.common import CipherVector


CipherFn = Callable[[bytes, bytes, bytes], bytes]


@dataclass(frozen=True)
class RoundTripCase:
    name: str
    key: bytes
    plaintext: bytes
    associated_data: bytes


def _check_bytes(actual: bytes, expected: bytes, *, label: str) -> tuple[bool, str]:
    if actual == expected:
        return True, f"[PASS] {label}"
    return (
        False,
        f"[FAIL] {label}\n"
        f"expected: {expected.hex()}\n"
        f"actual:   {actual.hex()}",
    )


def run_vector_cases(
    *,
    vectors: Sequence[CipherVector],
    encrypt_fn: CipherFn,
    decrypt_fn: CipherFn,
) -> int:
    passed = 0
    failed = 0

    for vector in vectors:
        ok, message = _check_bytes(
            encrypt_fn(vector.key, vector.plaintext, vector.associated_data),
            vector.ciphertext,
            label=f"{vector.name} encrypt",
        )
        print(message)
        if ok:
            passed += 1
        else:
            failed += 1

        ok, message = _check_bytes(
            decrypt_fn(vector.key, vector.ciphertext, vector.associated_data),
            vector.plaintext,
            label=f"{vector.name} decrypt",
        )
        print(message)
        if ok:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    print(f"\nSummary: total={total}, passed={passed}, failed={failed}")
    return 0 if failed == 0 else 1


def run_roundtrip_cases(
    *,
    cases: Sequence[RoundTripCase],
    encrypt_fn: CipherFn,
    decrypt_fn: CipherFn,
) -> int:
    passed = 0
    failed = 0

    for case in cases:
        ciphertext = encrypt_fn(case.key, case.plaintext, case.associated_data)
        ok, message = _check_bytes(
            decrypt_fn(case.key, ciphertext, case.associated_data),
            case.plaintext,
            label=f"{case.name} roundtrip",
        )
        print(message)
        if ok:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    print(f"\nSummary: total={total}, passed={passed}, failed={failed}")
    return 0 if failed == 0 else 1
