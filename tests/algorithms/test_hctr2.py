from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.helpers.vector_runner import run_vector_cases
from wideblock.algorithms.hctr2 import hctr2_aes_decrypt, hctr2_aes_encrypt
from wideblock.algorithms.hctr2.vectors import load_hctr2_vectors


def main() -> int:
    return run_vector_cases(
        vectors=load_hctr2_vectors(),
        encrypt_fn=hctr2_aes_encrypt,
        decrypt_fn=hctr2_aes_decrypt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
