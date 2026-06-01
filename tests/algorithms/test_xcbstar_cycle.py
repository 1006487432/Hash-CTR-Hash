from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT_DIR / "src" / "wideblock" / "testing" / "xcbstar_cycle.py"
spec = importlib.util.spec_from_file_location("xcbstar_cycle", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load xcbstar_cycle module")
xcbstar_cycle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = xcbstar_cycle
spec.loader.exec_module(xcbstar_cycle)
run_xcbstar_cycle_attack_poc = xcbstar_cycle.run_xcbstar_cycle_attack_poc


def main() -> int:
    transcript = run_xcbstar_cycle_attack_poc()
    checks = [
        (transcript.forged_plaintext != transcript.plaintext, "forged plaintext differs from original"),
        (transcript.forged_ciphertext != transcript.ciphertext, "forged ciphertext differs from original"),
        (transcript.decrypted_forgery == transcript.forged_plaintext, "forged ciphertext decrypts to forged plaintext"),
    ]

    failed = 0
    for ok, label in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failed += 1

    print(f"\nSummary: total={len(checks)}, passed={len(checks) - failed}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
