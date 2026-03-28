from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.wideblock.testing.registry import available_algorithms, run_performance_suite


def _format_result(name: str, metrics: tuple[tuple[str, str], ...]) -> list[str]:
    lines = [f"[{name}]"]
    for label, value in metrics:
        lines.append(f"  {label}: {value}")
    return lines


def main(argv: list[str]) -> int:
    algorithms = argv or available_algorithms()
    total = 0
    for algorithm in algorithms:
        print(f"=== {algorithm} ===")
        try:
            results = run_performance_suite(algorithm)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue
        for result in results:
            metric_pairs = tuple((metric.label, metric.value) for metric in result.metrics)
            for line in _format_result(result.name, metric_pairs):
                print(line)
        total += len(results)
        print()
    print(f"Summary: total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
