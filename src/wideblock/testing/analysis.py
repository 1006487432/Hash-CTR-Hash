from __future__ import annotations

import statistics
import tracemalloc
from dataclasses import dataclass
from hashlib import sha256

from ..registry import get_algorithm
from .models import TestCategory, TestMetric, TestResult, TestStatus

_ANALYSIS_SIZES = (16, 256, 4096, 16384)
_FIXED_TWEAK_ALGORITHMS = {"hch_aes", "hch_sm4", "hctr1_aes", "hctr1_sm4"}


@dataclass(frozen=True)
class KeyScheduleProfile:
    primitive: str
    user_key_bytes: int
    primitive_key_bytes: int
    derived_key_count: int
    schedule_rounds: int
    schedule_mode: str
    complexity_score: int
    complexity_level: str
    note: str


# 这里给出的是“结构复杂度画像”，用于横向比较不同方案的密钥调度负担，
# 不等同于底层密码库内部真实执行的每一步指令数。
_KEY_SCHEDULE_PROFILES: dict[str, KeyScheduleProfile] = {
    "hch_aes": KeyScheduleProfile("AES", 16, 16, 1, 10, "single", 10, "低", "直接复用单个 AES-128 密钥调度。"),
    "hch_sm4": KeyScheduleProfile("SM4", 16, 16, 1, 32, "single", 32, "中", "直接复用单个 SM4 轮密钥。"),
    "hctr1_aes": KeyScheduleProfile("AES", 32, 16, 2, 20, "split", 20, "中", "32 字节输入被拆成 K1||K2，两组 AES-128 调度分别承担数据层和哈希层。"),
    "hctr1_sm4": KeyScheduleProfile("SM4", 32, 16, 2, 64, "split", 64, "高", "32 字节输入被拆成 K1||K2，两组 SM4 轮密钥分别承担数据层和哈希层。"),
    "hctr2": KeyScheduleProfile("AES", 32, 32, 1, 14, "single_with_derived_masks", 14, "中", "单个 AES-256 调度后，通过加密常量块导出 hash key 与 L 值。"),
    "xcbstar": KeyScheduleProfile("AES", 16, 16, 5, 50, "derived_subkeys", 50, "高", "基于主密钥派生 5 个子密钥，左右两层都参与变换。"),
    "xcbstar_sm4": KeyScheduleProfile("SM4", 16, 16, 5, 160, "derived_subkeys", 160, "高", "基于主密钥派生 5 个 SM4 子密钥，左右两层都参与变换。"),
    "xcbv1": KeyScheduleProfile("AES", 16, 16, 5, 50, "derived_subkeys", 50, "高", "基于主密钥派生 5 个子密钥，内部轮函数多次复用。"),
    "xcbv1_sm4": KeyScheduleProfile("SM4", 16, 16, 5, 160, "derived_subkeys", 160, "高", "基于主密钥派生 5 个 SM4 子密钥，内部轮函数多次复用。"),
    "xcbv2": KeyScheduleProfile("AES", 16, 16, 4, 40, "derived_subkeys", 40, "中", "基于主密钥派生 hash / enc / dec / ctr 四组子密钥。"),
    "xcbv2_sm4": KeyScheduleProfile("SM4", 16, 16, 4, 128, "derived_subkeys", 128, "高", "基于主密钥派生 hash / enc / dec / ctr 四组 SM4 子密钥。"),
}


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(sha256(f"{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


def _key_size_for_algorithm(algorithm: str) -> int:
    profile = _KEY_SCHEDULE_PROFILES[algorithm]
    return profile.user_key_bytes


def _associated_data(algorithm: str, case_id: str, length: int = 16) -> bytes:
    if algorithm in _FIXED_TWEAK_ALGORITHMS:
        return _sample_bytes(f"{algorithm}:{case_id}:tweak", 16)
    return _sample_bytes(f"{algorithm}:{case_id}:ad", length)


def _measure_peak_bytes(operation) -> tuple[int, int]:
    # 只观测 Python 层分配行为，适合比较实现开销，不适合当作底层原生内存的精确计量。
    tracemalloc.start()
    try:
        operation()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return current, peak


def run_memory_analysis(algorithm: str) -> TestResult:
    # 使用固定样本和多档消息长度，得到更稳定的峰值内存曲线。
    cipher = get_algorithm(algorithm)
    encrypt = cipher["encrypt"]
    decrypt = cipher["decrypt"]
    key = _sample_bytes(f"{algorithm}:memory:key", _key_size_for_algorithm(algorithm))
    tweak = _associated_data(algorithm, "memory")

    encrypt_current_kib: list[float] = []
    encrypt_peak_kib: list[float] = []
    decrypt_current_kib: list[float] = []
    decrypt_peak_kib: list[float] = []

    for size in _ANALYSIS_SIZES:
        plaintext = _sample_bytes(f"{algorithm}:memory:{size}", size)
        ciphertext = encrypt(key, plaintext, tweak)
        current, peak = _measure_peak_bytes(lambda: encrypt(key, plaintext, tweak))
        encrypt_current_kib.append(current / 1024.0)
        encrypt_peak_kib.append(peak / 1024.0)
        current, peak = _measure_peak_bytes(lambda: decrypt(key, ciphertext, tweak))
        decrypt_current_kib.append(current / 1024.0)
        decrypt_peak_kib.append(peak / 1024.0)

    encrypt_peak_max = max(encrypt_peak_kib)
    decrypt_peak_max = max(decrypt_peak_kib)
    summary = "基于 tracemalloc 统计不同消息长度下的单次加解密峰值内存占用。"
    details = "峰值内存反映 Python 层临时对象与字节串分配，不等同于底层密码库的全部原生内存。"
    return TestResult(
        category=TestCategory.PERFORMANCE,
        name="内存占用分析",
        status=TestStatus.INFO,
        summary=summary,
        details=details,
        metrics=(
            TestMetric("加密峰值", f"{encrypt_peak_max:.2f} KiB"),
            TestMetric("解密峰值", f"{decrypt_peak_max:.2f} KiB"),
            TestMetric("加密均值", f"{statistics.mean(encrypt_peak_kib):.2f} KiB"),
            TestMetric("解密均值", f"{statistics.mean(decrypt_peak_kib):.2f} KiB"),
            TestMetric("样本点", str(len(_ANALYSIS_SIZES))),
        ),
        artifacts={
            "kind": "memory",
            "sizes": list(_ANALYSIS_SIZES),
            "encrypt_current_kib": encrypt_current_kib,
            "encrypt_peak_kib": encrypt_peak_kib,
            "decrypt_current_kib": decrypt_current_kib,
            "decrypt_peak_kib": decrypt_peak_kib,
            "encrypt_peak_max_kib": encrypt_peak_max,
            "decrypt_peak_max_kib": decrypt_peak_max,
        },
    )


def run_key_schedule_analysis(algorithm: str) -> TestResult:
    # 这项分析来自算法结构本身，而不是运行期采样，因此更适合做报告型说明。
    profile = _KEY_SCHEDULE_PROFILES[algorithm]
    details = (
        f"底层原语: {profile.primitive}\n"
        f"用户密钥长度: {profile.user_key_bytes} 字节\n"
        f"单组原语密钥长度: {profile.primitive_key_bytes} 字节\n"
        f"派生/复用密钥组数: {profile.derived_key_count}\n"
        f"名义调度轮数: {profile.schedule_rounds}\n"
        f"调度模式: {profile.schedule_mode}\n"
        f"说明: {profile.note}"
    )
    return TestResult(
        category=TestCategory.PERFORMANCE,
        name="密钥扩展复杂度分析",
        status=TestStatus.INFO,
        summary="基于算法结构分析密钥调度负担、子密钥派生数量与复用方式。",
        details=details,
        metrics=(
            TestMetric("底层原语", profile.primitive),
            TestMetric("用户密钥", f"{profile.user_key_bytes} 字节"),
            TestMetric("子密钥组数", str(profile.derived_key_count)),
            TestMetric("调度轮数", str(profile.schedule_rounds)),
            TestMetric("复杂度级别", profile.complexity_level),
        ),
        artifacts={
            "kind": "key_schedule",
            "primitive": profile.primitive,
            "user_key_bytes": profile.user_key_bytes,
            "primitive_key_bytes": profile.primitive_key_bytes,
            "derived_key_count": profile.derived_key_count,
            "schedule_rounds": profile.schedule_rounds,
            "schedule_mode": profile.schedule_mode,
            "complexity_score": profile.complexity_score,
            "complexity_level": profile.complexity_level,
            "note": profile.note,
        },
    )


def run_analysis_suite(algorithm: str) -> list[TestResult]:
    return [run_memory_analysis(algorithm), run_key_schedule_analysis(algorithm)]
