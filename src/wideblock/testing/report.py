from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import AlgorithmReport, ComparisonReport, TestCategory, TestStatus
from .registry import algorithm_label


def _status_badge(status: TestStatus) -> str:
    badges = {
        TestStatus.PASSED: "✅ 通过",
        TestStatus.WARNING: "⚠️ 警告",
        TestStatus.FAILED: "❌ 失败",
        TestStatus.INFO: "ℹ️ 信息",
    }
    return badges.get(status, str(status))


def _render_algorithm_report(report: AlgorithmReport) -> str:
    lines = [
        f"# {algorithm_label(report.algorithm)} 测试报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**总耗时**: {report.runtime_ms:.2f} ms",
        f"**测试结果**: 通过 {report.passed} / 警告 {report.warnings} / 失败 {report.failed}",
        "",
    ]

    for category in [TestCategory.CORRECTNESS, TestCategory.PERFORMANCE, TestCategory.SECURITY]:
        category_results = [r for r in report.results if r.category == category]
        if not category_results:
            continue

        category_names = {
            TestCategory.CORRECTNESS: "正确性测试",
            TestCategory.PERFORMANCE: "性能测试",
            TestCategory.SECURITY: "安全性测试",
        }
        lines.extend([f"## {category_names[category]}", ""])

        for result in category_results:
            lines.extend([
                f"### {result.name}",
                "",
                f"**状态**: {_status_badge(result.status)}",
                "",
                f"**概述**: {result.summary}",
                "",
            ])

            if result.details:
                lines.extend([f"**详情**: {result.details}", ""])

            if result.metrics:
                lines.append("**指标**:")
                for metric in result.metrics:
                    lines.append(f"- {metric.label}: {metric.value}")
                lines.append("")

    return "\n".join(lines)


def _render_performance_table(reports: tuple[AlgorithmReport, ...]) -> list[str]:
    sizes = (16, 256, 4096, 16384)
    lines = [
        "## 性能对比",
        "",
        "### 加密中位平均耗时 (微秒/次)",
        "",
        "| 算法 | " + " | ".join(f"{s}B" for s in sizes) + " |",
        "| --- | " + " | ".join("---:" for _ in sizes) + " |",
    ]
    for report in reports:
        label = algorithm_label(report.algorithm)
        row_values = []
        for size in sizes:
            artifact = next(
                (r.artifacts for r in report.results
                 if r.artifacts.get("kind") == "performance" and r.artifacts.get("operation") == "encrypt" and r.artifacts.get("size") == size),
                None,
            )
            row_values.append(f"{artifact['avg_us']:.2f}" if artifact else "-")
        lines.append(f"| {label} | " + " | ".join(row_values) + " |")
    lines.append("")

    lines.extend([
        "### 解密中位平均耗时 (微秒/次)",
        "",
        "| 算法 | " + " | ".join(f"{s}B" for s in sizes) + " |",
        "| --- | " + " | ".join("---:" for _ in sizes) + " |",
    ])
    for report in reports:
        label = algorithm_label(report.algorithm)
        row_values = []
        for size in sizes:
            artifact = next(
                (r.artifacts for r in report.results
                 if r.artifacts.get("kind") == "performance" and r.artifacts.get("operation") == "decrypt" and r.artifacts.get("size") == size),
                None,
            )
            row_values.append(f"{artifact['avg_us']:.2f}" if artifact else "-")
        lines.append(f"| {label} | " + " | ".join(row_values) + " |")
    lines.append("")

    lines.extend([
        "### 加密吞吐量 (MiB/s)",
        "",
        "| 算法 | " + " | ".join(f"{s}B" for s in sizes) + " |",
        "| --- | " + " | ".join("---:" for _ in sizes) + " |",
    ])
    for report in reports:
        label = algorithm_label(report.algorithm)
        row_values = []
        for size in sizes:
            artifact = next(
                (r.artifacts for r in report.results
                 if r.artifacts.get("kind") == "performance_throughput" and r.artifacts.get("operation") == "encrypt" and r.artifacts.get("size") == size),
                None,
            )
            row_values.append(f"{artifact['throughput_mib_s']:.4f}" if artifact else "-")
        lines.append(f"| {label} | " + " | ".join(row_values) + " |")
    lines.append("")

    lines.extend([
        "### 解密吞吐量 (MiB/s)",
        "",
        "| 算法 | " + " | ".join(f"{s}B" for s in sizes) + " |",
        "| --- | " + " | ".join("---:" for _ in sizes) + " |",
    ])
    for report in reports:
        label = algorithm_label(report.algorithm)
        row_values = []
        for size in sizes:
            artifact = next(
                (r.artifacts for r in report.results
                 if r.artifacts.get("kind") == "performance_throughput" and r.artifacts.get("operation") == "decrypt" and r.artifacts.get("size") == size),
                None,
            )
            row_values.append(f"{artifact['throughput_mib_s']:.4f}" if artifact else "-")
        lines.append(f"| {label} | " + " | ".join(row_values) + " |")
    lines.append("")

    has_cpb = any(
        r.artifacts.get("kind") == "performance_cpb" and r.artifacts.get("cpb") is not None
        for report in reports for r in report.results
    )
    if has_cpb:
        lines.extend([
            "### Cycles/Byte (加密)",
            "",
            "| 算法 | " + " | ".join(f"{s}B" for s in sizes) + " |",
            "| --- | " + " | ".join("---:" for _ in sizes) + " |",
        ])
        for report in reports:
            label = algorithm_label(report.algorithm)
            row_values = []
            for size in sizes:
                artifact = next(
                    (r.artifacts for r in report.results
                     if r.artifacts.get("kind") == "performance_cpb" and r.artifacts.get("operation") == "encrypt" and r.artifacts.get("size") == size),
                    None,
                )
                cpb = artifact.get("cpb") if artifact else None
                row_values.append(f"{cpb:.2f}" if cpb is not None else "-")
            lines.append(f"| {label} | " + " | ".join(row_values) + " |")
        lines.append("")

    lines.extend([
        "### 内存与密钥扩展",
        "",
        "| 算法 | 峰值内存 | 密钥扩展复杂度 | 总耗时 |",
        "| --- | --- | --- | ---: |",
    ])
    for report in reports:
        label = algorithm_label(report.algorithm)
        mem_result = next((r for r in report.results if "内存占用" in r.name), None)
        key_result = next((r for r in report.results if "密钥扩展" in r.name), None)
        mem_text = next((m.value for m in mem_result.metrics if "峰值" in m.label), "-") if mem_result else "-"
        key_text = next((m.value for m in key_result.metrics if "复杂度" in m.label or "子密钥" in m.label), key_result.summary if key_result else "-") if key_result else "-"
        lines.append(f"| {label} | {mem_text} | {key_text} | {report.runtime_ms:.0f} ms |")
    lines.append("")

    return lines


def _render_security_table(reports: tuple[AlgorithmReport, ...]) -> list[str]:
    lines = [
        "## 安全性对比",
        "",
        "### GB/T 32915 随机性检测总览",
        "",
        "| 算法 | 结论 | 通过项 | 失败项 | 1比例 | 字节卡方 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for report in reports:
        label = algorithm_label(report.algorithm)
        summary_result = next(
            (r for r in report.results if r.category == TestCategory.SECURITY and "总览" in r.name),
            None,
        )
        if summary_result:
            status = _status_badge(summary_result.status)
            passed = next((m.value for m in summary_result.metrics if "通过" in m.label), "-")
            failed = next((m.value for m in summary_result.metrics if "失败" in m.label), "-")
            ones = next((m.value for m in summary_result.metrics if "1 比例" in m.label), "-")
            chi = next((m.value for m in summary_result.metrics if "卡方" in m.label), "-")
            lines.append(f"| {label} | {status} | {passed} | {failed} | {ones} | {chi} |")
        else:
            lines.append(f"| {label} | - | - | - | - | - |")
    lines.append("")

    lines.extend([
        "### GB/T 32915 各项检测 P 值",
        "",
    ])
    test_names: list[str] = []
    for report in reports:
        for r in report.results:
            if r.category == TestCategory.SECURITY and r.artifacts.get("kind") == "gbt32915_item":
                short_name = r.name.replace("GB/T 32915 ", "")
                if short_name not in test_names:
                    test_names.append(short_name)
    if test_names:
        algo_labels = [algorithm_label(rpt.algorithm) for rpt in reports]
        lines.append("| 检测项 | " + " | ".join(algo_labels) + " |")
        lines.append("| --- | " + " | ".join("---:" for _ in reports) + " |")
        for test_name in test_names:
            row_values = []
            for report in reports:
                matched = next(
                    (r for r in report.results
                     if r.category == TestCategory.SECURITY and r.artifacts.get("kind") == "gbt32915_item" and test_name in r.name),
                    None,
                )
                if matched:
                    p_val = matched.artifacts.get("p_value")
                    status_mark = "✓" if matched.status == TestStatus.PASSED else "✗"
                    row_values.append(f"{status_mark} {p_val:.4f}" if p_val is not None else _status_badge(matched.status))
                else:
                    row_values.append("-")
            lines.append(f"| {test_name} | " + " | ".join(row_values) + " |")
        lines.append("")

    lines.extend([
        "### 雪崩效应",
        "",
        "| 算法 | 状态 | 平均翻转 | 最小翻转 | 标准差 |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    for report in reports:
        label = algorithm_label(report.algorithm)
        avalanche = next(
            (r for r in report.results if r.category == TestCategory.SECURITY and "雪崩" in r.name),
            None,
        )
        if avalanche:
            status = _status_badge(avalanche.status)
            avg = next((m.value for m in avalanche.metrics if "平均" in m.label), "-")
            min_val = next((m.value for m in avalanche.metrics if "最小" in m.label), "-")
            std = next((m.value for m in avalanche.metrics if "标准差" in m.label), "-")
            lines.append(f"| {label} | {status} | {avg} | {min_val} | {std} |")
        else:
            lines.append(f"| {label} | - | - | - | - |")
    lines.append("")

    return lines


def _render_comparison_report(report: ComparisonReport) -> str:
    lines = [
        "# 算法对比测试报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**参与算法**: {len(report.rows)} 个",
        "",
    ]

    if report.notes:
        lines.extend(["## 说明", ""])
        for note in report.notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.extend([
        "## 综合对比总览",
        "",
        "| 算法 | 正确性 | 加密速度 | 解密速度 | 安全性 | 备注 |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ])
    for row in report.rows:
        lines.append(f"| {row.algorithm} | {row.correctness} | {row.encrypt_speed} | {row.decrypt_speed} | {row.security} | {row.notes} |")
    lines.append("")

    if report.reports:
        perf_reports = tuple(r for r in report.reports if any(res.category == TestCategory.PERFORMANCE for res in r.results))
        if perf_reports:
            lines.extend(_render_performance_table(perf_reports))

        sec_reports = tuple(r for r in report.reports if any(res.category == TestCategory.SECURITY for res in r.results))
        if sec_reports:
            lines.extend(_render_security_table(sec_reports))

        lines.extend(["## 正确性验证", "", "| 算法 | 16B 往返 | 31B 往返 | 128B 往返 |", "| --- | --- | --- | --- |"])
        for algo_report in report.reports:
            label = algorithm_label(algo_report.algorithm)
            correctness_results = [r for r in algo_report.results if r.category == TestCategory.CORRECTNESS]
            cells = []
            for r in correctness_results:
                cells.append(_status_badge(r.status))
            while len(cells) < 3:
                cells.append("-")
            lines.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")
        lines.append("")

    return "\n".join(lines)


def generate_report(report: AlgorithmReport | ComparisonReport, output_path: Path | str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(report, ComparisonReport):
        content = _render_comparison_report(report)
    else:
        content = _render_algorithm_report(report)
    output_path.write_text(content, encoding="utf-8")


__all__ = ["generate_report"]
