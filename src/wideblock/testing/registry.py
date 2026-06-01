from __future__ import annotations

import gc
import statistics
import time

try:
    import psutil
except ImportError:
    psutil = None
from hashlib import sha256
from typing import Callable

from ..registry import get_algorithm, list_algorithms
from .analysis import run_analysis_suite
from .models import AlgorithmReport, ComparisonReport, ComparisonRow, TestCategory, TestMetric, TestResult, TestStatus
from .security import run_security_suite, security_overview


_PERFORMANCE_SIZES = (16, 256, 4096, 16384)
_PERFORMANCE_ANALYSIS_STEPS = 2
_PERFORMANCE_WARMUP = 5
_PERFORMANCE_REPETITIONS = 3
_PERFORMANCE_MIN_TOTAL_BYTES = 512 * 1024
_PERFORMANCE_MAX_ROUNDS = 120
_CORRECTNESS_SIZES = (16, 31, 128)
_FIXED_TWEAK_ALGORITHMS = {"hch_aes", "hch_sm4", "hctr1_aes", "hctr1_sm4"}


_ALGORITHM_LABELS = {
    "hch_aes": "HCH (AES)",
    "hch_sm4": "HCH (SM4)",
    "hctr1_aes": "HCTR1 (AES)",
    "hctr1_sm4": "HCTR1 (SM4)",
    "hctr2": "HCTR2 (AES)",
    "hctr2_sm4": "HCTR2 (SM4)",
    "xcbstar": "XCB* (AES)",
    "xcbstar_sm4": "XCB* (SM4)",
    "xcbv1": "XCBv1 (AES)",
    "xcbv1_sm4": "XCBv1 (SM4)",
    "xcbv2": "XCBv2 (AES)",
    "xcbv2_sm4": "XCBv2 (SM4)",
}


ProgressCallback = Callable[[int, int, str], None]
PartialAlgorithmCallback = Callable[[AlgorithmReport, TestCategory], None]
PartialComparisonCallback = Callable[[ComparisonReport], None]


def algorithm_label(name: str) -> str:
    return _ALGORITHM_LABELS.get(name, name)


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


def _associated_data(algorithm: str, case_id: str, length: int = 16) -> bytes:
    if algorithm in _FIXED_TWEAK_ALGORITHMS:
        return _sample_bytes(f"{algorithm}:{case_id}:tweak", 16)
    return _sample_bytes(f"{algorithm}:{case_id}:ad", length)


def _key_size_for_algorithm(algorithm: str) -> int:
    if algorithm in {"hctr1_aes", "hctr1_sm4", "hctr2"}:
        return 32
    if algorithm == "hctr2_sm4":
        return 16
    return 16


def _build_algorithm_report(algorithm: str, results: list[TestResult], started: float) -> AlgorithmReport:
    runtime_ms = (time.perf_counter() - started) * 1000
    return AlgorithmReport(algorithm=algorithm, results=tuple(results), runtime_ms=runtime_ms)


def run_correctness_suite(algorithm: str) -> list[TestResult]:
    cipher = get_algorithm(algorithm)
    encrypt = cipher["encrypt"]
    decrypt = cipher["decrypt"]
    results: list[TestResult] = []

    for index, size in enumerate(_CORRECTNESS_SIZES):
        key = _sample_bytes(f"{algorithm}:key:{index}", _key_size_for_algorithm(algorithm))
        plaintext = _sample_bytes(f"{algorithm}:pt:{index}", size)
        tweak = _associated_data(algorithm, f"correctness:{index}")

        started = time.perf_counter()
        ciphertext = encrypt(key, plaintext, tweak)
        recovered = decrypt(key, ciphertext, tweak)
        elapsed_ms = (time.perf_counter() - started) * 1000

        status = TestStatus.PASSED if recovered == plaintext else TestStatus.FAILED
        details = "" if status == TestStatus.PASSED else f"期望值: {plaintext.hex()}\n实际值: {recovered.hex()}"
        results.append(
            TestResult(
                category=TestCategory.CORRECTNESS,
                name=f"往返测试 {size} 字节",
                status=status,
                summary="加密后再解密可以恢复原文" if status == TestStatus.PASSED else "往返结果不一致",
                details=details,
                metrics=(TestMetric("耗时", f"{elapsed_ms:.2f} ms"), TestMetric("密文长度", f"{len(ciphertext)} 字节")),
            )
        )
    return results


def _benchmark_operation(operation, rounds: int) -> list[int]:
    samples: list[int] = []
    gc.collect()
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        for _ in range(rounds):
            started = time.perf_counter_ns()
            operation()
            samples.append(time.perf_counter_ns() - started)
    finally:
        if was_enabled:
            gc.enable()
    return samples


def _cpu_frequency_ghz() -> float | None:
    # cpb 需要一个当前主频估计值；若平台或依赖不支持，就退化为不输出该指标。
    if psutil is None:
        return None
    try:
        freq = psutil.cpu_freq()
    except Exception:
        return None
    if freq is None:
        return None
    mhz = freq.current or freq.max or freq.min
    if not mhz:
        return None
    return float(mhz) / 1000.0


def _summarize_samples(samples_ns: list[int], size: int) -> dict[str, float | None]:
    mean_ns = statistics.mean(samples_ns)
    median_ns = statistics.median(samples_ns)
    min_ns = min(samples_ns)
    max_ns = max(samples_ns)
    stdev_ns = statistics.stdev(samples_ns) if len(samples_ns) > 1 else 0.0
    relative_stdev = stdev_ns / mean_ns if mean_ns else 0.0
    throughput_mib_s = (size / (1024 * 1024)) / (mean_ns / 1_000_000_000)
    freq_ghz = _cpu_frequency_ghz()
    # GHz * ns 可以近似换算成时钟周期数，再除以消息长度得到 cycles per byte。
    cpb = None if freq_ghz is None or size <= 0 else (mean_ns * freq_ghz) / float(size)
    return {
        "avg_us": mean_ns / 1000.0,
        "median_us": median_ns / 1000.0,
        "min_us": min_ns / 1000.0,
        "max_us": max_ns / 1000.0,
        "stdev_us": stdev_ns / 1000.0,
        "relative_stdev": relative_stdev,
        "throughput_mib_s": throughput_mib_s,
        "cpu_freq_ghz": freq_ghz,
        "cpb": cpb,
    }


def _median_or_none(values: list[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return float(statistics.median(filtered))


def _aggregate_stats(runs: list[dict[str, float | None]]) -> dict[str, float | None]:
    return {
        "avg_us": _median_or_none([item["avg_us"] for item in runs]),
        "median_us": _median_or_none([item["median_us"] for item in runs]),
        "min_us": _median_or_none([item["min_us"] for item in runs]),
        "max_us": _median_or_none([item["max_us"] for item in runs]),
        "stdev_us": _median_or_none([item["stdev_us"] for item in runs]),
        "relative_stdev": _median_or_none([item["relative_stdev"] for item in runs]),
        "throughput_mib_s": _median_or_none([item["throughput_mib_s"] for item in runs]),
        "cpu_freq_ghz": _median_or_none([item["cpu_freq_ghz"] for item in runs]),
        "cpb": _median_or_none([item["cpb"] for item in runs]),
        "repeat_count": float(len(runs)),
    }


def _performance_rounds(size: int) -> int:
    by_volume = max(8, _PERFORMANCE_MIN_TOTAL_BYTES // max(size, 1))
    return min(_PERFORMANCE_MAX_ROUNDS, by_volume)


def run_performance_suite(
    algorithm: str,
    progress_callback: ProgressCallback | None = None,
    item_callback: Callable[[list[TestResult]], None] | None = None,
) -> list[TestResult]:
    # 性能测试按消息长度逐段产出结果，便于 GUI 做流式刷新而不是整套完成后一次性展示。
    # 每个消息长度会重复执行多轮，再用中位数降低偶发抖动对报告的影响。
    cipher = get_algorithm(algorithm)
    encrypt = cipher["encrypt"]
    decrypt = cipher["decrypt"]
    key = _sample_bytes(f"{algorithm}:perf:key", _key_size_for_algorithm(algorithm))
    tweak = _associated_data(algorithm, "performance")

    results: list[TestResult] = []
    total_steps = len(_PERFORMANCE_SIZES) + _PERFORMANCE_ANALYSIS_STEPS
    for step_index, size in enumerate(_PERFORMANCE_SIZES, start=1):
        if progress_callback is not None:
            progress_callback(step_index, total_steps, f"正在执行性能测试: {size} 字节（{_PERFORMANCE_REPETITIONS} 轮）")

        plaintext = _sample_bytes(f"{algorithm}:perf:{size}", size)
        ciphertext = encrypt(key, plaintext, tweak)
        rounds = _performance_rounds(size)

        encrypt_call = lambda: encrypt(key, plaintext, tweak)
        decrypt_call = lambda: decrypt(key, ciphertext, tweak)
        for _ in range(_PERFORMANCE_WARMUP):
            encrypt_call()
            decrypt_call()

        encrypt_runs = [_summarize_samples(_benchmark_operation(encrypt_call, rounds), size) for _ in range(_PERFORMANCE_REPETITIONS)]
        decrypt_runs = [_summarize_samples(_benchmark_operation(decrypt_call, rounds), size) for _ in range(_PERFORMANCE_REPETITIONS)]
        encrypt_stats = _aggregate_stats(encrypt_runs)
        decrypt_stats = _aggregate_stats(decrypt_runs)

        chunk = [
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"加密速度测试 {size} 字节",
                status=TestStatus.INFO,
                summary=f"统计 {_PERFORMANCE_REPETITIONS} 轮加密耗时的中位数。",
                metrics=(
                    TestMetric("中位平均耗时", f"{encrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("中位耗时", f"{encrypt_stats['median_us']:.2f} 微秒/次"),
                    TestMetric("最小耗时", f"{encrypt_stats['min_us']:.2f} 微秒/次"),
                    TestMetric("最大耗时", f"{encrypt_stats['max_us']:.2f} 微秒/次"),
                    TestMetric("相对标准差", f"{encrypt_stats['relative_stdev'] * 100:.2f}%"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                    TestMetric("轮数", str(rounds)),
                ),
                artifacts={"kind": "performance", "operation": "encrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **encrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"解密速度测试 {size} 字节",
                status=TestStatus.INFO,
                summary=f"统计 {_PERFORMANCE_REPETITIONS} 轮解密耗时的中位数。",
                metrics=(
                    TestMetric("中位平均耗时", f"{decrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("中位耗时", f"{decrypt_stats['median_us']:.2f} 微秒/次"),
                    TestMetric("最小耗时", f"{decrypt_stats['min_us']:.2f} 微秒/次"),
                    TestMetric("最大耗时", f"{decrypt_stats['max_us']:.2f} 微秒/次"),
                    TestMetric("相对标准差", f"{decrypt_stats['relative_stdev'] * 100:.2f}%"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                    TestMetric("轮数", str(rounds)),
                ),
                artifacts={"kind": "performance", "operation": "decrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **decrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"加密吞吐量测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计连续加密的数据处理吞吐量。",
                metrics=(
                    TestMetric("吞吐量", f"{encrypt_stats['throughput_mib_s']:.4f} MiB/s"),
                    TestMetric("中位平均耗时", f"{encrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("总数据量", f"{size * rounds} 字节"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                ),
                artifacts={"kind": "performance_throughput", "operation": "encrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **encrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"解密吞吐量测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计连续解密的数据处理吞吐量。",
                metrics=(
                    TestMetric("吞吐量", f"{decrypt_stats['throughput_mib_s']:.4f} MiB/s"),
                    TestMetric("中位平均耗时", f"{decrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("总数据量", f"{size * rounds} 字节"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                ),
                artifacts={"kind": "performance_throughput", "operation": "decrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **decrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"周期/字节测试 {size} 字节（加密）",
                status=TestStatus.INFO,
                summary="基于 CPU 主频估算每字节平均消耗的 CPU 时钟周期数。",
                metrics=(
                    TestMetric("cpb", f"{encrypt_stats['cpb']:.4f}" if encrypt_stats['cpb'] is not None else "不可用"),
                    TestMetric("CPU 频率", f"{encrypt_stats['cpu_freq_ghz']:.3f} GHz" if encrypt_stats['cpu_freq_ghz'] is not None else "不可用"),
                    TestMetric("中位平均耗时", f"{encrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                ),
                artifacts={"kind": "performance_cpb", "operation": "encrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **encrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"周期/字节测试 {size} 字节（解密）",
                status=TestStatus.INFO,
                summary="基于 CPU 主频估算每字节平均消耗的 CPU 时钟周期数。",
                metrics=(
                    TestMetric("cpb", f"{decrypt_stats['cpb']:.4f}" if decrypt_stats['cpb'] is not None else "不可用"),
                    TestMetric("CPU 频率", f"{decrypt_stats['cpu_freq_ghz']:.3f} GHz" if decrypt_stats['cpu_freq_ghz'] is not None else "不可用"),
                    TestMetric("中位平均耗时", f"{decrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("重复轮数", str(_PERFORMANCE_REPETITIONS)),
                ),
                artifacts={"kind": "performance_cpb", "operation": "decrypt", "size": size, "rounds": rounds, "repetitions": _PERFORMANCE_REPETITIONS, **decrypt_stats},
            ),
        ]
        results.extend(chunk)
        if item_callback is not None:
            item_callback(chunk)

    analysis_steps = [
        ("正在执行内存占用分析", 0),
        ("正在执行密钥扩展复杂度分析", 1),
    ]
    analysis_results = run_analysis_suite(algorithm)
    for offset, (label, index_in_analysis) in enumerate(analysis_steps, start=1):
        if progress_callback is not None:
            progress_callback(len(_PERFORMANCE_SIZES) + offset, total_steps, label)
        chunk = [analysis_results[index_in_analysis]]
        results.extend(chunk)
        if item_callback is not None:
            item_callback(chunk)
    return results


def run_category_report(algorithm: str, category: TestCategory) -> AlgorithmReport:
    # 分类报告用于“单项测试”模式，只返回当前类别的结果，避免性能和安全性相互捆绑。
    started = time.perf_counter()
    if category == TestCategory.CORRECTNESS:
        results = run_correctness_suite(algorithm)
    elif category == TestCategory.PERFORMANCE:
        results = run_performance_suite(algorithm)
    elif category == TestCategory.SECURITY:
        results = run_security_suite(algorithm)
    else:
        raise ValueError(f"unsupported category: {category}")
    return _build_algorithm_report(algorithm, list(results), started)


def run_algorithm_report(algorithm: str) -> AlgorithmReport:
    started = time.perf_counter()
    results = [
        *run_correctness_suite(algorithm),
        *run_performance_suite(algorithm),
        *run_security_suite(algorithm),
    ]
    return _build_algorithm_report(algorithm, results, started)


def run_category_report_stream(
    algorithm: str,
    category: TestCategory,
    progress_callback: ProgressCallback | None = None,
    partial_callback: PartialAlgorithmCallback | None = None,
) -> AlgorithmReport:
    # 流式版本会在每个阶段或每个性能分块完成后回传局部报告，供 GUI 更新进度和图表。
    started = time.perf_counter()
    results: list[TestResult] = []

    if category == TestCategory.CORRECTNESS:
        if progress_callback is not None:
            progress_callback(0, 1, "准备执行正确性测试")
        results.extend(run_correctness_suite(algorithm))
        report = _build_algorithm_report(algorithm, results, started)
        if partial_callback is not None:
            partial_callback((report, category))
        if progress_callback is not None:
            progress_callback(1, 1, "正确性测试已完成")
        return report

    if category == TestCategory.PERFORMANCE:
        if progress_callback is not None:
            progress_callback(0, 1, "准备执行性能测试")

        def on_perf_chunk(chunk: list[TestResult]) -> None:
            results.extend(chunk)
            if partial_callback is not None:
                partial_callback((_build_algorithm_report(algorithm, results, started), category))

        run_performance_suite(
            algorithm,
            progress_callback=lambda step, total, text: progress_callback(step, total, text) if progress_callback else None,
            item_callback=on_perf_chunk,
        )
        report = _build_algorithm_report(algorithm, results, started)
        if progress_callback is not None:
            progress_callback(1, 1, "性能测试已完成")
        return report

    if category == TestCategory.SECURITY:
        if progress_callback is not None:
            progress_callback(0, 1, "准备执行安全性测试")
        results.extend(run_security_suite(algorithm))
        report = _build_algorithm_report(algorithm, results, started)
        if partial_callback is not None:
            partial_callback((report, category))
        if progress_callback is not None:
            progress_callback(1, 1, "安全性测试已完成")
        return report

    raise ValueError(f"unsupported category: {category}")


def run_algorithm_report_stream(
    algorithm: str,
    progress_callback: ProgressCallback | None = None,
    partial_callback: PartialAlgorithmCallback | None = None,
) -> AlgorithmReport:
    started = time.perf_counter()
    results: list[TestResult] = []

    if progress_callback is not None:
        progress_callback(0, 3, "准备开始测试")

    correctness = run_correctness_suite(algorithm)
    results.extend(correctness)
    if partial_callback is not None:
        partial_callback((_build_algorithm_report(algorithm, results, started), TestCategory.CORRECTNESS))
    if progress_callback is not None:
        progress_callback(1, 3, "正确性测试已完成")

    def on_perf_chunk(chunk: list[TestResult]) -> None:
        results.extend(chunk)
        if partial_callback is not None:
            partial_callback((_build_algorithm_report(algorithm, results, started), TestCategory.PERFORMANCE))

    run_performance_suite(
        algorithm,
        progress_callback=lambda step, total, text: progress_callback(1 + step / max(total, 1), 3, text) if progress_callback else None,
        item_callback=on_perf_chunk,
    )
    if partial_callback is not None:
        partial_callback((_build_algorithm_report(algorithm, results, started), TestCategory.PERFORMANCE))
    if progress_callback is not None:
        progress_callback(2, 3, "性能测试已完成")

    security = run_security_suite(algorithm)
    results.extend(security)
    if partial_callback is not None:
        partial_callback((_build_algorithm_report(algorithm, results, started), TestCategory.SECURITY))
    if progress_callback is not None:
        progress_callback(3, 3, "全部测试已完成")

    return _build_algorithm_report(algorithm, results, started)


def _performance_artifacts(report: AlgorithmReport, operation: str) -> list[dict[str, float]]:
    artifacts: list[dict[str, float]] = []
    for result in report.results:
        if result.category != TestCategory.PERFORMANCE:
            continue
        if result.artifacts.get("kind") != "performance":
            continue
        if result.artifacts.get("operation") != operation:
            continue
        artifacts.append(result.artifacts)
    return artifacts


def _build_comparison_row(report: AlgorithmReport, category: TestCategory) -> ComparisonRow:
    if category == TestCategory.PERFORMANCE:
        enc_artifacts = _performance_artifacts(report, "encrypt")
        dec_artifacts = _performance_artifacts(report, "decrypt")
        enc_avg = statistics.mean(item["avg_us"] for item in enc_artifacts) if enc_artifacts else None
        dec_avg = statistics.mean(item["avg_us"] for item in dec_artifacts) if dec_artifacts else None
        enc_tp = statistics.mean(item["throughput_mib_s"] for item in enc_artifacts) if enc_artifacts else None
        dec_tp = statistics.mean(item["throughput_mib_s"] for item in dec_artifacts) if dec_artifacts else None
        note_parts = [f"总耗时 {report.runtime_ms:.1f} ms"]
        if enc_tp is not None:
            note_parts.append(f"加密吞吐 {enc_tp:.4f} MiB/s")
        if dec_tp is not None:
            note_parts.append(f"解密吞吐 {dec_tp:.4f} MiB/s")
        return ComparisonRow(
            algorithm=algorithm_label(report.algorithm),
            correctness="-",
            encrypt_speed=f"{enc_avg:.2f} 微秒/次" if enc_avg is not None else "-",
            decrypt_speed=f"{dec_avg:.2f} 微秒/次" if dec_avg is not None else "-",
            security="-",
            notes="，".join(note_parts),
        )

    if category == TestCategory.SECURITY:
        return ComparisonRow(
            algorithm=algorithm_label(report.algorithm),
            correctness="-",
            encrypt_speed="-",
            decrypt_speed="-",
            security=security_overview(list(report.results)),
            notes=f"总耗时 {report.runtime_ms:.1f} ms",
        )

    correctness_failed = sum(1 for result in report.results if result.category == TestCategory.CORRECTNESS and result.status == TestStatus.FAILED)
    return ComparisonRow(
        algorithm=algorithm_label(report.algorithm),
        correctness="通过" if correctness_failed == 0 else f"失败 ({correctness_failed})",
        encrypt_speed="-",
        decrypt_speed="-",
        security="-",
        notes=f"总耗时 {report.runtime_ms:.1f} ms",
    )


def run_comparison_report_for_category(algorithms: list[str], category: TestCategory) -> ComparisonReport:
    rows: list[ComparisonRow] = []
    reports: list[AlgorithmReport] = []
    if category == TestCategory.PERFORMANCE:
        notes = [f"性能耗时使用 {_PERFORMANCE_REPETITIONS} 轮中位数作为稳定值；总耗时包含内存分析等附加步骤，不等同于纯加解密耗时。"]
    elif category == TestCategory.SECURITY:
        notes = ["随机性与雪崩效应结果用于统计比较，不能替代正式安全证明。"]
    else:
        notes = []

    for algorithm in algorithms:
        report = run_category_report(algorithm, category)
        reports.append(report)
        rows.append(_build_comparison_row(report, category))
    return ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))


def run_comparison_report_stream_for_category(
    algorithms: list[str],
    category: TestCategory,
    progress_callback: ProgressCallback | None = None,
    partial_callback: PartialComparisonCallback | None = None,
) -> ComparisonReport:
    rows: list[ComparisonRow] = []
    reports: list[AlgorithmReport] = []
    if category == TestCategory.PERFORMANCE:
        notes = [f"性能耗时使用 {_PERFORMANCE_REPETITIONS} 轮中位数作为稳定值；总耗时包含内存分析等附加步骤，不等同于纯加解密耗时。"]
    elif category == TestCategory.SECURITY:
        notes = ["随机性与雪崩效应结果用于统计比较，不能替代正式安全证明。"]
    else:
        notes = []

    total = len(algorithms)
    for index, algorithm in enumerate(algorithms, start=1):
        if progress_callback is not None:
            progress_callback(index - 1, total, f"正在测试 {algorithm_label(algorithm)}")
        report = run_category_report(algorithm, category)
        reports.append(report)
        rows.append(_build_comparison_row(report, category))
        partial = ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))
        if partial_callback is not None:
            partial_callback(partial)
        if progress_callback is not None:
            progress_callback(index, total, f"已完成 {index}/{total} 个算法")
    return ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))


def run_comparison_report(algorithms: list[str]) -> ComparisonReport:
    rows: list[ComparisonRow] = []
    reports: list[AlgorithmReport] = []
    notes = [
        f"性能耗时使用 {_PERFORMANCE_REPETITIONS} 轮中位数作为稳定值；总耗时包含内存分析和安全性测试等附加步骤，不等同于纯加解密耗时。",
        "统计随机性与雪崩效应只能作为补充指标，不能替代正式安全证明。",
    ]
    for algorithm in algorithms:
        report = run_algorithm_report(algorithm)
        reports.append(report)
        correctness_failed = sum(1 for result in report.results if result.category == TestCategory.CORRECTNESS and result.status == TestStatus.FAILED)
        enc_artifacts = _performance_artifacts(report, "encrypt")
        dec_artifacts = _performance_artifacts(report, "decrypt")
        enc_avg = statistics.mean(item["avg_us"] for item in enc_artifacts) if enc_artifacts else None
        dec_avg = statistics.mean(item["avg_us"] for item in dec_artifacts) if dec_artifacts else None
        enc_tp = statistics.mean(item["throughput_mib_s"] for item in enc_artifacts) if enc_artifacts else None
        dec_tp = statistics.mean(item["throughput_mib_s"] for item in dec_artifacts) if dec_artifacts else None
        note_parts = [f"总耗时 {report.runtime_ms:.1f} ms"]
        if enc_tp is not None:
            note_parts.append(f"加密吞吐 {enc_tp:.4f} MiB/s")
        if dec_tp is not None:
            note_parts.append(f"解密吞吐 {dec_tp:.4f} MiB/s")
        rows.append(
            ComparisonRow(
                algorithm=algorithm_label(algorithm),
                correctness="通过" if correctness_failed == 0 else f"失败 ({correctness_failed})",
                encrypt_speed=f"{enc_avg:.2f} 微秒/次" if enc_avg is not None else "-",
                decrypt_speed=f"{dec_avg:.2f} 微秒/次" if dec_avg is not None else "-",
                security=security_overview(list(report.results)),
                notes="，".join(note_parts),
            )
        )
    return ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))


def run_comparison_report_stream(
    algorithms: list[str],
    progress_callback: ProgressCallback | None = None,
    partial_callback: PartialComparisonCallback | None = None,
) -> ComparisonReport:
    rows: list[ComparisonRow] = []
    reports: list[AlgorithmReport] = []
    notes = [
        f"性能耗时使用 {_PERFORMANCE_REPETITIONS} 轮中位数作为稳定值；总耗时包含内存分析和安全性测试等附加步骤，不等同于纯加解密耗时。",
        "统计随机性与雪崩效应只能作为补充指标，不能替代正式安全证明。",
    ]
    total = len(algorithms)
    for index, algorithm in enumerate(algorithms, start=1):
        if progress_callback is not None:
            progress_callback(index - 1, total, f"正在测试 {algorithm_label(algorithm)}")
        report = run_algorithm_report(algorithm)
        reports.append(report)
        correctness_failed = sum(1 for result in report.results if result.category == TestCategory.CORRECTNESS and result.status == TestStatus.FAILED)
        enc_artifacts = _performance_artifacts(report, "encrypt")
        dec_artifacts = _performance_artifacts(report, "decrypt")
        enc_avg = statistics.mean(item["avg_us"] for item in enc_artifacts) if enc_artifacts else None
        dec_avg = statistics.mean(item["avg_us"] for item in dec_artifacts) if dec_artifacts else None
        enc_tp = statistics.mean(item["throughput_mib_s"] for item in enc_artifacts) if enc_artifacts else None
        dec_tp = statistics.mean(item["throughput_mib_s"] for item in dec_artifacts) if dec_artifacts else None
        note_parts = [f"总耗时 {report.runtime_ms:.1f} ms"]
        if enc_tp is not None:
            note_parts.append(f"加密吞吐 {enc_tp:.4f} MiB/s")
        if dec_tp is not None:
            note_parts.append(f"解密吞吐 {dec_tp:.4f} MiB/s")
        rows.append(
            ComparisonRow(
                algorithm=algorithm_label(algorithm),
                correctness="通过" if correctness_failed == 0 else f"失败 ({correctness_failed})",
                encrypt_speed=f"{enc_avg:.2f} 微秒/次" if enc_avg is not None else "-",
                decrypt_speed=f"{dec_avg:.2f} 微秒/次" if dec_avg is not None else "-",
                security=security_overview(list(report.results)),
                notes="，".join(note_parts),
            )
        )
        partial = ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))
        if partial_callback is not None:
            partial_callback(partial)
        if progress_callback is not None:
            progress_callback(index, total, f"已完成 {index}/{total} 个算法")
    return ComparisonReport(rows=tuple(rows), notes=tuple(notes), reports=tuple(reports))


def available_algorithms() -> list[str]:
    return list_algorithms()
