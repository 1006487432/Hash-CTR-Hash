from __future__ import annotations

import json
from pathlib import Path

from ...common import CipherVector


_VECTOR_DIR = Path(__file__).resolve().parent / "test_vectors"
_VECTOR_FILES = ["HCTR2_AES128.json", "HCTR2_AES192.json", "HCTR2_AES256.json"]


def load_hctr2_vectors() -> list[CipherVector]:
    vectors: list[CipherVector] = []
    for filename in _VECTOR_FILES:
        raw_vectors = json.loads((_VECTOR_DIR / filename).read_text(encoding="utf-8"))
        for item in raw_vectors:
            key = bytes.fromhex(item["input"]["key_hex"])
            tweak = bytes.fromhex(item["input"]["tweak_hex"])
            plaintext = bytes.fromhex(item["plaintext_hex"])
            ciphertext = bytes.fromhex(item["ciphertext_hex"])
            vectors.append(
                CipherVector(
                    name=f"{filename}:{item['description']}",
                    key=key,
                    plaintext=plaintext,
                    associated_data=tweak,
                    ciphertext=ciphertext,
                )
            )
    return vectors
