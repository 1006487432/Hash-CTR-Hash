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
from wideblock.algorithms.xcbv2 import XCB_VECTORS, xcb_aes_decrypt, xcb_aes_encrypt


def main() -> int:
    return run_vector_cases(
        vectors=XCB_VECTORS,
        encrypt_fn=xcb_aes_encrypt,
        decrypt_fn=xcb_aes_decrypt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
