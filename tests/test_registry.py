from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from wideblock import get_algorithm, list_algorithms


def _check_registry_entry(name: str) -> int:
    failed = 0

    if name in list_algorithms():
        print(f"[PASS] registry contains {name}")
    else:
        failed += 1
        print(f"[FAIL] registry contains {name}")

    try:
        algorithm = get_algorithm(name)
    except KeyError as exc:
        failed += 1
        print(f"[FAIL] registry lookup {name}\nerror: {exc}")
        return failed

    if "encrypt" in algorithm:
        print(f"[PASS] {name} exposes encrypt")
    else:
        failed += 1
        print(f"[FAIL] {name} exposes encrypt")

    if "decrypt" in algorithm:
        print(f"[PASS] {name} exposes decrypt")
    else:
        failed += 1
        print(f"[FAIL] {name} exposes decrypt")

    return failed


def main() -> int:
    names = [
        "hch_aes",
        "hch_sm4",
        "hctr1_aes",
        "hctr1_sm4",
        "hctr2",
        "hctr2_sm4",
        "xcbstar",
        "xcbstar_sm4",
        "xcbv1",
        "xcbv1_sm4",
        "xcbv2",
        "xcbv2_sm4",
    ]
    failed = 0
    for name in names:
        failed += _check_registry_entry(name)

    total = len(names) * 3
    passed = total - failed
    print(f"\nSummary: total={total}, passed={passed}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
