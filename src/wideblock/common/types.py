from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CipherVector:
    name: str
    key: bytes
    plaintext: bytes
    associated_data: bytes
    ciphertext: bytes
