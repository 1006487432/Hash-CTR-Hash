from __future__ import annotations

import statistics
import time
from hashlib import sha256
from typing import Callable

from ..registry import get_algorithm, list_algorithms
from .models import AlgorithmReport, ComparisonReport, ComparisonRow, TestCategory, TestMetric, TestResult, TestStatus
from .security import run_security_suite, security_overview


_PERFORMANCE_SIZES = (16, 256, 4096, 16384)
_PERFORMANCE_WARMUP = 3
_PERFORMANCE_MIN_TOTAL_BYTES = 256 * 1024
_PERFORMANCE_MAX_ROUNDS = 80
_CORRECTNESS_SIZES = (16, 31, 128)
_FIXED_TWEAK_ALGORITHMS = {"hch_aes", "hch_sm4", "hctr1_aes", "hctr1_sm4"}


_ALGORITHM_LABELS = {
    "hch_aes": "HCH (AES)",
    "hch_sm4": "HCH (SM4)",
    "hctr1_aes": "HCTR1 (AES)",
    "hctr1_sm4": "HCTR1 (SM4)",
    "hctr2": "HCTR2 (AES)",
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
    for _ in range(rounds):
        started = time.perf_counter_ns()
        operation()
        samples.append(time.perf_counter_ns() - started)
    return samples


def _summarize_samples(samples_ns: list[int], size: int) -> dict[str, float]:
    mean_ns = statistics.mean(samples_ns)
    median_ns = statistics.median(samples_ns)
    min_ns = min(samples_ns)
    max_ns = max(samples_ns)
    throughput_mib_s = (size / (1024 * 1024)) / (mean_ns / 1_000_000_000)
    return {
        "avg_us": mean_ns / 1000.0,
        "median_us": median_ns / 1000.0,
        "min_us": min_ns / 1000.0,
        "max_us": max_ns / 1000.0,
        "throughput_mib_s": throughput_mib_s,
    }


def _performance_rounds(size: int) -> int:
    by_volume = max(8, _PERFORMANCE_MIN_TOTAL_BYTES // max(size, 1))
    return min(_PERFORMANCE_MAX_ROUNDS, by_volume)


def run_performance_suite(
    algorithm: str,
    progress_callback: ProgressCallback | None = None,
    item_callback: Callable[[list[TestResult]], None] | None = None,
) -> list[TestResult]:
    cipher = get_algorithm(algorithm)
    encrypt = cipher["encrypt"]
    decrypt = cipher["decrypt"]
    key = _sample_bytes(f"{algorithm}:perf:key", _key_size_for_algorithm(algorithm))
    tweak = _associated_data(algorithm, "performance")

    results: list[TestResult] = []
    total_steps = len(_PERFORMANCE_SIZES)
    for step_index, size in enumerate(_PERFORMANCE_SIZES, start=1):
        if progress_callback is not None:
            progress_callback(step_index, total_steps, f"正在执行性能测试: {size} 字节")

        plaintext = _sample_bytes(f"{algorithm}:perf:{size}", size)
        ciphertext = encrypt(key, plaintext, tweak)
        rounds = _performance_rounds(size)

        encrypt_call = lambda: encrypt(key, plaintext, tweak)
        decrypt_call = lambda: decrypt(key, ciphertext, tweak)
        for _ in range(_PERFORMANCE_WARMUP):
            encrypt_call()
            decrypt_call()

        encrypt_samples = _benchmark_operation(encrypt_call, rounds)
        decrypt_samples = _benchmark_operation(decrypt_call, rounds)
        encrypt_stats = _summarize_samples(encrypt_samples, size)
        decrypt_stats = _summarize_samples(decrypt_samples, size)

        chunk = [
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"加密速度测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计单次加密耗时。",
                metrics=(
                    TestMetric("平均耗时", f"{encrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("中位耗时", f"{encrypt_stats['median_us']:.2f} 微秒/次"),
                    TestMetric("最小耗时", f"{encrypt_stats['min_us']:.2f} 微秒/次"),
                    TestMetric("最大耗时", f"{encrypt_stats['max_us']:.2f} 微秒/次"),
                    TestMetric("轮数", str(rounds)),
                ),
                artifacts={"kind": "performance", "operation": "encrypt", "size": size, "rounds": rounds, **encrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"解密速度测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计单次解密耗时。",
                metrics=(
                    TestMetric("平均耗时", f"{decrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("中位耗时", f"{decrypt_stats['median_us']:.2f} 微秒/次"),
                    TestMetric("最小耗时", f"{decrypt_stats['min_us']:.2f} 微秒/次"),
                    TestMetric("最大耗时", f"{decrypt_stats['max_us']:.2f} 微秒/次"),
                    TestMetric("轮数", str(rounds)),
                ),
                artifacts={"kind": "performance", "operation": "decrypt", "size": size, "rounds": rounds, **decrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"加密吞吐量测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计连续加密的数据处理吞吐量。",
                metrics=(
                    TestMetric("吞吐量", f"{encrypt_stats['throughput_mib_s']:.4f} MiB/s"),
                    TestMetric("平均耗时", f"{encrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("总数据量", f"{size * rounds} 字节"),
                ),
                artifacts={"kind": "performance_throughput", "operation": "encrypt", "size": size, "rounds": rounds, **encrypt_stats},
            ),
            TestResult(
                category=TestCategory.PERFORMANCE,
                name=f"解密吞吐量测试 {size} 字节",
                status=TestStatus.INFO,
                summary="统计连续解密的数据处理吞吐量。",
                metrics=(
                    TestMetric("吞吐量", f"{decrypt_stats['throughput_mib_s']:.4f} MiB/s"),
                    TestMetric("平均耗时", f"{decrypt_stats['avg_us']:.2f} 微秒/次"),
                    TestMetric("总数据量", f"{size * rounds} 字节"),
                ),
                artifacts={"kind": "performance_throughput", "operation": "decrypt", "size": size, "rounds": rounds, **decrypt_stats},
            ),
        ]
        results.extend(chunk)
        if item_callback is not None:
            item_callback(chunk)
    return results


def run_algorithm_report(algorithm: str) -> AlgorithmReport:
    started = time.perf_counter()
    results = [
        *run_correctness_suite(algorithm),
        *run_performance_suite(algorithm),
        *run_security_suite(algorithm),
    ]
    return _build_algorithm_report(algorithm, results, started)


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


def run_comparison_report(algorithms: list[str]) -> ComparisonReport:
    rows: list[ComparisonRow] = []
    reports: list[AlgorithmReport] = []
    notes = [
        "交叉对比页当前展示统一基准下的往返正确性、平均加解密速度、平均加解密吞吐量，以及随机性/雪崩效应测试结论。",
        "统计随机性与雪崩效应只能作为补充指标，不能替代正式安全证明或论文攻击复现实验。",
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
        "交叉对比页当前展示统一基准下的往返正确性、平均加解密速度、平均加解密吞吐量，以及随机性/雪崩效应测试结论。",
        "统计随机性与雪崩效应只能作为补充指标，不能替代正式安全证明或论文攻击复现实验。",
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
