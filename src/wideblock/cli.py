from __future__ import annotations

import sys
from pathlib import Path

from .registry import list_algorithms
from .testing.registry import run_algorithm_report
from .testing.report import generate_report


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python -m wideblock.cli <algorithm> [output_dir]")
        print(f"可用算法: {', '.join(list_algorithms())}")
        return 1

    algorithm = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("reports")

    if algorithm not in list_algorithms():
        print(f"错误: 未知算法 '{algorithm}'")
        print(f"可用算法: {', '.join(list_algorithms())}")
        return 1

    print(f"正在测试 {algorithm}...")
    report = run_algorithm_report(algorithm)

    output_path = output_dir / f"{algorithm}_report.md"
    generate_report(report, output_path)

    print(f"✓ 测试完成")
    print(f"  通过: {report.passed}")
    print(f"  警告: {report.warnings}")
    print(f"  失败: {report.failed}")
    print(f"  报告: {output_path}")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
