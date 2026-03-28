from __future__ import annotations

import statistics
from hashlib import sha256

from .gbt32915 import run_gbt32915_suite
from ..registry import get_algorithm
from .models import TestCategory, TestMetric, TestResult, TestStatus


_AVALANCHE_SAMPLE_SIZE = 128
_AVALANCHE_TRIALS = 24
_FIXED_TWEAK_ALGORITHMS = {"hch_aes", "hch_sm4", "hctr1_aes", "hctr1_sm4"}


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


def _key_size_for_algorithm(algorithm: str) -> int:
    if algorithm in {"hctr1_aes", "hctr1_sm4", "hctr2"}:
        return 32
    return 16


def _associated_data(algorithm: str, case_id: str, length: int = 16) -> bytes:
    if algorithm in _FIXED_TWEAK_ALGORITHMS:
        return _sample_bytes(f"{algorithm}:{case_id}:tweak", 16)
    return _sample_bytes(f"{algorithm}:{case_id}:ad", length)


def _flip_bit(data: bytes, bit_index: int) -> bytes:
    mutable = bytearray(data)
    byte_index, offset = divmod(bit_index, 8)
    mutable[byte_index] ^= 1 << offset
    return bytes(mutable)


def _hamming_distance(left: bytes, right: bytes) -> int:
    return sum((a ^ b).bit_count() for a, b in zip(left, right))


def _avalanche_status(avg_ratio: float, min_ratio: float) -> TestStatus:
    if 0.45 <= avg_ratio <= 0.55 and min_ratio >= 0.30:
        return TestStatus.PASSED
    if 0.40 <= avg_ratio <= 0.60 and min_ratio >= 0.20:
        return TestStatus.WARNING
    return TestStatus.FAILED


def run_avalanche_test(algorithm: str) -> TestResult:
    encrypt = get_algorithm(algorithm)["encrypt"]
    ratios: list[float] = []

    for index in range(_AVALANCHE_TRIALS):
        key = _sample_bytes(f"{algorithm}:avalanche:key:{index}", _key_size_for_algorithm(algorithm))
        plaintext = _sample_bytes(f"{algorithm}:avalanche:pt:{index}", _AVALANCHE_SAMPLE_SIZE)
        tweak = _associated_data(algorithm, f"avalanche:{index}")
        flipped = _flip_bit(plaintext, index % (len(plaintext) * 8))
        ciphertext = encrypt(key, plaintext, tweak)
        flipped_ciphertext = encrypt(key, flipped, tweak)
        total_bits = min(len(ciphertext), len(flipped_ciphertext)) * 8
        if total_bits == 0:
            continue
        distance = _hamming_distance(ciphertext, flipped_ciphertext)
        ratios.append(distance / total_bits)

    if not ratios:
        return TestResult(
            category=TestCategory.SECURITY,
            name="雪崩效应测试",
            status=TestStatus.FAILED,
            summary="未生成有效样本。",
            details="加密输出为空或样本构造失败，无法评估明文单比特扰动后的扩散效果。",
            artifacts={"kind": "avalanche", "ratios": ()},
        )

    average_ratio = statistics.mean(ratios)
    min_ratio = min(ratios)
    max_ratio = max(ratios)
    stddev = statistics.pstdev(ratios) if len(ratios) > 1 else 0.0
    status = _avalanche_status(average_ratio, min_ratio)
    return TestResult(
        category=TestCategory.SECURITY,
        name="雪崩效应测试",
        status=status,
        summary=(
            "单比特扰动在密文中形成了良好的扩散。"
            if status == TestStatus.PASSED
            else "扩散程度接近预期，但仍有一定波动。"
            if status == TestStatus.WARNING
            else "扩散程度偏弱，建议复核结构实现与测试样本。"
        ),
        details="固定密钥和关联数据后翻转明文单比特，观察密文翻转比例是否接近 50%。",
        metrics=(
            TestMetric("试验组数", str(len(ratios))),
            TestMetric("平均翻转", f"{average_ratio * 100:.2f}%"),
            TestMetric("最小翻转", f"{min_ratio * 100:.2f}%"),
            TestMetric("最大翻转", f"{max_ratio * 100:.2f}%"),
            TestMetric("标准差", f"{stddev * 100:.2f}%"),
        ),
        artifacts={
            "kind": "avalanche",
            "ratios": tuple(ratios),
            "average_ratio": average_ratio,
            "min_ratio": min_ratio,
            "max_ratio": max_ratio,
            "stddev": stddev,
        },
    )


def run_security_suite(algorithm: str) -> list[TestResult]:
    results = [*run_gbt32915_suite(algorithm), run_avalanche_test(algorithm)]
    if algorithm.startswith("xcb"):
        results.append(
            TestResult(
                category=TestCategory.SECURITY,
                name="公开研究提示",
                status=TestStatus.WARNING,
                summary="该算法家族已有公开攻击研究，统计测试不能替代攻击复现。",
                details="建议后续补充对应论文中的结构性攻击或区分攻击复现实验。",
                metrics=(TestMetric("优先级", "高"),),
                artifacts={"kind": "note"},
            )
        )
    return results


def security_overview(results: list[TestResult]) -> str:
    security_results = [result for result in results if result.category == TestCategory.SECURITY]
    if not security_results:
        return "-"
    if any(result.status == TestStatus.FAILED for result in security_results):
        return "失败"
    if any(result.status == TestStatus.WARNING for result in security_results):
        return "警告"
    if all(result.status == TestStatus.PASSED for result in security_results):
        return "通过"
    return "信息"
