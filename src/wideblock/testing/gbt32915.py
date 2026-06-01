from __future__ import annotations

import math
from functools import lru_cache
from hashlib import sha256

import numpy as np
from scipy.special import erfc, gammaincc, ndtr

from ..registry import get_algorithm
from .models import TestCategory, TestMetric, TestResult, TestStatus

_ALPHA = 0.01
_SEQUENCE_BITS = 1_000_000
_SEQUENCE_BYTES = _SEQUENCE_BITS // 8
_FIXED_TWEAK_ALGORITHMS = {"hch_aes", "hch_sm4", "hctr1_aes", "hctr1_sm4"}

_POKER_M = (4, 8)
_OVERLAPPING_M = (2, 5)
_BINARY_DERIVATIVE_K = (3, 7)
_AUTOCORRELATION_D = (1, 2, 8, 16)
_BLOCK_FREQUENCY_M = 100
_APPROXIMATE_ENTROPY_M = 5
_LINEAR_COMPLEXITY_M = 500
_LONGEST_RUN_M = 10_000
_MATRIX_ROWS = 32
_MATRIX_COLS = 32

_DEFAULT_SAMPLE_COUNT = 5
_PASS_RATE_THRESHOLD = 0.6

_LONGEST_RUN_TABLE = {
    8: {
        "thresholds": ((-math.inf, 1), (2, 2), (3, 3), (4, math.inf)),
        "pi": (0.2148, 0.3672, 0.2305, 0.1875),
    },
    128: {
        "thresholds": ((-math.inf, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, math.inf)),
        "pi": (0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124),
    },
    10_000: {
        "thresholds": ((-math.inf, 10), (11, 11), (12, 12), (13, 13), (14, 14), (15, 15), (16, math.inf)),
        "pi": (0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727),
    },
}

_LINEAR_COMPLEXITY_PI = (0.010417, 0.03125, 0.12500, 0.50000, 0.25000, 0.06250, 0.020833)


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
    if algorithm == "hctr2_sm4":
        return 16
    return 16


def _associated_data(algorithm: str, case_id: str, length: int = 16) -> bytes:
    if algorithm in _FIXED_TWEAK_ALGORITHMS:
        return _sample_bytes(f"{algorithm}:{case_id}:tweak", 16)
    return _sample_bytes(f"{algorithm}:{case_id}:ad", length)


def _status_from_p_value(p_value: float) -> TestStatus:
    return TestStatus.PASSED if p_value >= _ALPHA else TestStatus.FAILED


def _build_result(
    name: str,
    p_value: float,
    summary_ok: str,
    summary_bad: str,
    details: str,
    metrics: tuple[TestMetric, ...],
    artifacts: dict[str, object] | None = None,
) -> TestResult:
    status = _status_from_p_value(p_value)
    return TestResult(
        category=TestCategory.SECURITY,
        name=name,
        status=status,
        summary=summary_ok if status == TestStatus.PASSED else summary_bad,
        details=details,
        metrics=metrics + (TestMetric("P 值", f"{p_value:.6f}"), TestMetric("显著性水平", f"{_ALPHA:.2f}")),
        artifacts=artifacts or {},
    )


@lru_cache(maxsize=None)
def _ciphertext_sample(algorithm: str) -> bytes:
    encrypt = get_algorithm(algorithm)["encrypt"]
    key = _sample_bytes(f"{algorithm}:gbt32915:key", _key_size_for_algorithm(algorithm))
    plaintext = _sample_bytes(f"{algorithm}:gbt32915:pt", _SEQUENCE_BYTES)
    tweak = _associated_data(algorithm, "gbt32915")
    return encrypt(key, plaintext, tweak)


@lru_cache(maxsize=None)
def _bit_sequence(algorithm: str) -> np.ndarray:
    ciphertext = _ciphertext_sample(algorithm)
    return np.unpackbits(np.frombuffer(ciphertext, dtype=np.uint8))


@lru_cache(maxsize=None)
def _byte_histogram(algorithm: str) -> tuple[tuple[int, ...], tuple[float, ...]]:
    ciphertext = _ciphertext_sample(algorithm)
    counts = np.bincount(np.frombuffer(ciphertext, dtype=np.uint8), minlength=256)
    history = []
    progressive = np.zeros(256, dtype=np.int64)
    chunks = np.array_split(np.frombuffer(ciphertext, dtype=np.uint8), 24)
    for chunk in chunks:
        progressive += np.bincount(chunk, minlength=256)
        expected = progressive.sum() / 256.0
        chi = float(np.sum(((progressive - expected) ** 2) / expected)) if expected else 0.0
        history.append(chi)
    return tuple(int(v) for v in counts), tuple(history)


def _norm_cdf(value: float) -> float:
    return float(ndtr(value))


def _count_ones(bits: np.ndarray) -> int:
    return int(bits.sum())


def _window_counts(bits: np.ndarray, m: int, *, circular: bool) -> np.ndarray:
    if circular:
        source = np.concatenate((bits, bits[: m - 1])) if m > 1 else bits
        count = len(bits)
    else:
        if len(bits) < m:
            return np.zeros(1 << m, dtype=np.int64)
        source = bits
        count = len(bits) - m + 1
    counts = np.zeros(1 << m, dtype=np.int64)
    if count <= 0:
        return counts
    value = 0
    mask = (1 << m) - 1
    for bit in source[:m]:
        value = ((value << 1) | int(bit)) & mask
    counts[value] += 1
    for bit in source[m : m + count - 1]:
        value = ((value << 1) | int(bit)) & mask
        counts[value] += 1
    return counts


def _psi_square(bits: np.ndarray, m: int) -> float:
    if m <= 0:
        return 0.0
    counts = _window_counts(bits, m, circular=True)
    n = len(bits)
    return float((1 << m) / n * np.sum(counts.astype(np.float64) ** 2) - n)


def _run_length_counts(bits: np.ndarray, limit: int) -> tuple[list[int], list[int]]:
    ones = [0] * limit
    zeros = [0] * limit
    if len(bits) == 0:
        return ones, zeros
    current = int(bits[0])
    length = 1
    for bit in bits[1:]:
        value = int(bit)
        if value == current:
            length += 1
            continue
        if length <= limit:
            (ones if current else zeros)[length - 1] += 1
        current = value
        length = 1
    if length <= limit:
        (ones if current else zeros)[length - 1] += 1
    return ones, zeros


def _longest_one_run(block: np.ndarray) -> int:
    best = 0
    current = 0
    for bit in block:
        if bit:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _gf2_rank(matrix: np.ndarray) -> int:
    work = matrix.copy().astype(np.uint8)
    rows, cols = work.shape
    rank = 0
    col = 0
    while rank < rows and col < cols:
        pivot = None
        for row in range(rank, rows):
            if work[row, col]:
                pivot = row
                break
        if pivot is None:
            col += 1
            continue
        if pivot != rank:
            work[[rank, pivot]] = work[[pivot, rank]]
        for row in range(rows):
            if row != rank and work[row, col]:
                work[row] ^= work[rank]
        rank += 1
        col += 1
    return rank


def _berlekamp_massey(block: np.ndarray) -> int:
    n = len(block)
    c = [0] * n
    b = [0] * n
    c[0] = 1
    b[0] = 1
    l = 0
    m = -1
    for index in range(n):
        discrepancy = int(block[index])
        for j in range(1, l + 1):
            discrepancy ^= c[j] & int(block[index - j])
        if discrepancy == 0:
            continue
        t = c[:]
        shift = index - m
        for j in range(n - shift):
            c[j + shift] ^= b[j]
        if l <= index / 2:
            l = index + 1 - l
            m = index
            b = t
    return l


def _select_maurer_l(n: int) -> tuple[int, int, int]:
    selected = None
    for l_value in range(16, 5, -1):
        q = 10 * (1 << l_value)
        k = n // l_value - q
        if q >= 10 * (1 << l_value) and k >= 1000 * (1 << l_value):
            selected = (l_value, q, k)
            break
    if selected is None:
        l_value = 6
        q = 10 * (1 << l_value)
        k = max(n // l_value - q, 1)
        selected = (l_value, q, k)
    return selected


def _maurer_stats(l_value: int, k: int) -> tuple[float, float]:
    p = 2.0 ** (-l_value)
    max_index = max(int(80 / p), 200_000)
    indices = np.arange(1, max_index + 1, dtype=np.float64)
    probs = np.power(1.0 - p, indices - 1) * p
    logs = np.log2(indices)
    mean = float(np.sum(probs * logs))
    second = float(np.sum(probs * logs * logs))
    variance = max(second - mean * mean, 1e-12)
    c = 0.7 - 0.8 / l_value + (4.0 + 32.0 / l_value) * (k ** (-3.0 / l_value)) / 15.0
    sigma = math.sqrt(max(c * variance / k, 1e-12))
    return mean, sigma


def _frequency_test(bits: np.ndarray) -> TestResult:
    n = len(bits)
    ones = _count_ones(bits)
    s_obs = abs(2 * ones - n) / math.sqrt(n)
    p_value = float(erfc(s_obs / math.sqrt(2.0)))
    return _build_result(
        "GB/T 32915 单比特频数检测",
        p_value,
        "0/1 总体比例满足标准要求。",
        "0/1 总体比例偏离标准要求。",
        "按照标准 4.1 对整条二元序列的 0/1 平衡性进行检测。",
        (
            TestMetric("样本长度", f"{n} 比特"),
            TestMetric("1 的数量", str(ones)),
            TestMetric("统计量", f"{s_obs:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.1", "p_value": p_value},
    )


def _block_frequency_test(bits: np.ndarray, m: int) -> TestResult:
    n = len(bits)
    block_count = n // m
    blocks = bits[: block_count * m].reshape(block_count, m)
    pis = blocks.mean(axis=1)
    statistic = float(4.0 * m * np.sum((pis - 0.5) ** 2))
    p_value = float(gammaincc(block_count / 2.0, statistic / 2.0))
    return _build_result(
        f"GB/T 32915 块内频数检测 (m={m})",
        p_value,
        "各块内的 1 比例分布满足标准要求。",
        "各块内的 1 比例分布偏离标准要求。",
        "按照标准 4.2 检测固定块长子序列中的 1 比例是否接近 1/2。",
        (
            TestMetric("块长 m", str(m)),
            TestMetric("块数 N", str(block_count)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.2", "m": m, "p_value": p_value},
    )


def _poker_test(bits: np.ndarray, m: int) -> TestResult:
    n = len(bits)
    block_count = n // m
    blocks = bits[: block_count * m].reshape(block_count, m)
    weights = (1 << np.arange(m - 1, -1, -1, dtype=np.int64))
    values = blocks.dot(weights)
    counts = np.bincount(values, minlength=1 << m)
    statistic = float((1 << m) / block_count * np.sum(counts.astype(np.float64) ** 2) - block_count)
    p_value = float(gammaincc(((1 << m) - 1) / 2.0, statistic / 2.0))
    return _build_result(
        f"GB/T 32915 扑克检测 (m={m})",
        p_value,
        "非重叠 m 位模式频数满足标准要求。",
        "非重叠 m 位模式频数偏离标准要求。",
        "按照标准 4.3 比较 2^m 种非重叠模式的出现次数是否接近均匀。",
        (
            TestMetric("模式长度 m", str(m)),
            TestMetric("块数 N", str(block_count)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.3", "m": m, "p_value": p_value},
    )


def _overlapping_template_test(bits: np.ndarray, m: int) -> TestResult:
    psi_m = _psi_square(bits, m)
    psi_m1 = _psi_square(bits, m - 1)
    psi_m2 = _psi_square(bits, m - 2)
    delta2 = psi_m - 2.0 * psi_m1 + psi_m2
    p_value = float(gammaincc(2 ** (m - 2), delta2 / 2.0))
    return _build_result(
        f"GB/T 32915 重叠子序列检测 (m={m})",
        p_value,
        "可重叠模式频数差分满足标准要求。",
        "可重叠模式频数差分偏离标准要求。",
        "按照标准 4.4 基于 Ψ² 差分统计量检测可重叠子序列模式分布。",
        (
            TestMetric("模式长度 m", str(m)),
            TestMetric("Ψ²(m)", f"{psi_m:.4f}"),
            TestMetric("Δ²Ψ²", f"{delta2:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.4", "m": m, "p_value": p_value},
    )


def _runs_total_test(bits: np.ndarray) -> TestResult:
    n = len(bits)
    pi = bits.mean()
    v_obs = int(1 + np.count_nonzero(bits[1:] != bits[:-1]))
    if abs(pi - 0.5) >= 2.0 / math.sqrt(n):
        p_value = 0.0
        statistic = math.inf
    else:
        statistic = abs(v_obs - 2.0 * n * pi * (1.0 - pi)) / (2.0 * math.sqrt(2.0 * n) * pi * (1.0 - pi))
        p_value = float(erfc(statistic))
    return _build_result(
        "GB/T 32915 游程总数检测",
        p_value,
        "游程总数满足标准要求。",
        "游程总数偏离标准要求。",
        "按照标准 4.5 检测整条序列中的游程总数是否与随机序列相符。",
        (
            TestMetric("π", f"{pi:.6f}"),
            TestMetric("游程总数", str(v_obs)),
            TestMetric("统计量", "∞" if math.isinf(statistic) else f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.5", "p_value": p_value},
    )


def _runs_distribution_test(bits: np.ndarray) -> TestResult:
    n = len(bits)
    k = 0
    while (n - (k + 1) + 3) / (2 ** ((k + 1) + 2)) >= 5:
        k += 1
    ones, zeros = _run_length_counts(bits, k)
    expected = [((n - i + 2) / (2 ** (i + 2))) for i in range(1, k + 1)]
    statistic = 0.0
    for index in range(k):
        statistic += (ones[index] - expected[index]) ** 2 / expected[index]
        statistic += (zeros[index] - expected[index]) ** 2 / expected[index]
    p_value = float(gammaincc(k - 1, statistic / 2.0))
    return _build_result(
        "GB/T 32915 游程分布检测",
        p_value,
        "不同长度游程的分布满足标准要求。",
        "不同长度游程的分布偏离标准要求。",
        "按照标准 4.6 检测不同长度的 0/1 游程数量分布。",
        (
            TestMetric("k", str(k)),
            TestMetric("统计量", f"{statistic:.4f}"),
            TestMetric("e1", f"{expected[0]:.2f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.6", "p_value": p_value},
    )


def _longest_run_test(bits: np.ndarray, m: int) -> TestResult:
    table = _LONGEST_RUN_TABLE[m]
    block_count = len(bits) // m
    blocks = bits[: block_count * m].reshape(block_count, m)
    counts = [0] * len(table["pi"])
    for block in blocks:
        longest = _longest_one_run(block)
        for index, (lower, upper) in enumerate(table["thresholds"]):
            if lower <= longest <= upper:
                counts[index] += 1
                break
    statistic = 0.0
    for observed, probability in zip(counts, table["pi"]):
        expected = block_count * probability
        statistic += (observed - expected) ** 2 / expected
    p_value = float(gammaincc((len(table["pi"]) - 1) / 2.0, statistic / 2.0))
    return _build_result(
        f"GB/T 32915 块内最大 1 游程检测 (m={m})",
        p_value,
        "各块最长 1 游程分布满足标准要求。",
        "各块最长 1 游程分布偏离标准要求。",
        "按照标准 4.7 检测每个固定块内最大 1 游程长度的分布。",
        (
            TestMetric("块长 m", str(m)),
            TestMetric("块数 N", str(block_count)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.7", "m": m, "counts": tuple(counts), "p_value": p_value},
    )


def _binary_derivative_test(bits: np.ndarray, k: int) -> TestResult:
    derived = bits.copy()
    for _ in range(k):
        derived = np.bitwise_xor(derived[:-1], derived[1:])
    n_k = len(derived)
    s_nk = int(np.sum(derived.astype(np.int64) * 2 - 1))
    statistic = abs(s_nk) / math.sqrt(n_k)
    p_value = float(erfc(statistic / math.sqrt(2.0)))
    return _build_result(
        f"GB/T 32915 二元推导检测 (k={k})",
        p_value,
        "推导序列的 0/1 平衡性满足标准要求。",
        "推导序列的 0/1 平衡性偏离标准要求。",
        "按照标准 4.8 对第 k 次二元推导结果进行平衡性检测。",
        (
            TestMetric("推导次数 k", str(k)),
            TestMetric("序列长度", str(n_k)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.8", "k": k, "p_value": p_value},
    )


def _autocorrelation_test(bits: np.ndarray, d: int) -> TestResult:
    n = len(bits)
    mismatch = int(np.count_nonzero(bits[:-d] != bits[d:]))
    statistic = abs(2.0 * (mismatch - (n - d) / 2.0) / math.sqrt(n - d))
    p_value = float(erfc(statistic / math.sqrt(2.0)))
    return _build_result(
        f"GB/T 32915 自相关检测 (d={d})",
        p_value,
        "位移自相关满足标准要求。",
        "位移自相关偏离标准要求。",
        "按照标准 4.9 检测序列与其左移 d 位后的相关程度。",
        (
            TestMetric("时延 d", str(d)),
            TestMetric("不同位数", str(mismatch)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.9", "d": d, "p_value": p_value},
    )


def _matrix_rank_test(bits: np.ndarray) -> TestResult:
    block_bits = _MATRIX_ROWS * _MATRIX_COLS
    matrix_count = len(bits) // block_bits
    matrices = bits[: matrix_count * block_bits].reshape(matrix_count, _MATRIX_ROWS, _MATRIX_COLS)
    full_rank = 0
    rank_minus_one = 0
    for matrix in matrices:
        rank = _gf2_rank(matrix)
        if rank == _MATRIX_ROWS:
            full_rank += 1
        elif rank == _MATRIX_ROWS - 1:
            rank_minus_one += 1
    remainder = matrix_count - full_rank - rank_minus_one
    statistic = (
        (full_rank - 0.2888 * matrix_count) ** 2 / (0.2888 * matrix_count)
        + (rank_minus_one - 0.5776 * matrix_count) ** 2 / (0.5776 * matrix_count)
        + (remainder - 0.1336 * matrix_count) ** 2 / (0.1336 * matrix_count)
    )
    p_value = float(gammaincc(1.0, statistic / 2.0))
    return _build_result(
        "GB/T 32915 矩阵秩检测",
        p_value,
        "32×32 矩阵秩分布满足标准要求。",
        "32×32 矩阵秩分布偏离标准要求。",
        "按照标准 4.10 将序列组装为 32×32 二元矩阵后进行 GF(2) 秩分布检测。",
        (
            TestMetric("矩阵数 N", str(matrix_count)),
            TestMetric("满秩数", str(full_rank)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.10", "p_value": p_value},
    )


def _cumulative_sums_test(bits: np.ndarray) -> TestResult:
    transformed = 2 * bits.astype(np.int64) - 1
    sums = np.cumsum(transformed)
    z = int(np.max(sums))
    n = len(bits)
    if z <= 0:
        p_value = 1.0
    else:
        start_1 = math.floor((-(n / z) + 1.0) / 4.0)
        end_1 = math.floor((n / z - 1.0) / 4.0)
        start_2 = math.floor((-(n / z) - 3.0) / 4.0)
        end_2 = math.floor((n / z - 1.0) / 4.0)
        sum_1 = sum(_norm_cdf((4 * i + 1) * z / math.sqrt(n)) - _norm_cdf((4 * i - 1) * z / math.sqrt(n)) for i in range(start_1, end_1 + 1))
        sum_2 = sum(_norm_cdf((4 * i + 3) * z / math.sqrt(n)) - _norm_cdf((4 * i + 1) * z / math.sqrt(n)) for i in range(start_2, end_2 + 1))
        p_value = 1.0 - sum_1 + sum_2
        p_value = max(0.0, min(1.0, p_value))
    return _build_result(
        "GB/T 32915 累加和检测",
        p_value,
        "累加和最大偏移满足标准要求。",
        "累加和最大偏移偏离标准要求。",
        "按照标准 4.11 对二元序列映射后的累加和最大偏移进行检测。",
        (
            TestMetric("最大偏移 Z", str(z)),
            TestMetric("样本长度", f"{n} 比特"),
        ),
        {"kind": "gbt32915_item", "section": "4.11", "p_value": p_value},
    )


def _approximate_entropy_test(bits: np.ndarray, m: int) -> TestResult:
    phi_values = []
    for block_size in (m, m + 1):
        counts = _window_counts(bits, block_size, circular=True)
        probs = counts[counts > 0] / len(bits)
        phi_values.append(float(np.sum(probs * np.log(probs))))
    ap_en = phi_values[0] - phi_values[1]
    statistic = 2.0 * len(bits) * (math.log(2.0) - ap_en)
    p_value = float(gammaincc(2 ** (m - 1), statistic / 2.0))
    return _build_result(
        f"GB/T 32915 近似熵检测 (m={m})",
        p_value,
        "相邻模式长度的近似熵满足标准要求。",
        "相邻模式长度的近似熵偏离标准要求。",
        "按照标准 4.12 比较 m 位与 m+1 位可重叠模式频率之间的差异。",
        (
            TestMetric("模式长度 m", str(m)),
            TestMetric("ApEn", f"{ap_en:.6f}"),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.12", "m": m, "p_value": p_value},
    )


def _linear_complexity_test(bits: np.ndarray, m: int) -> TestResult:
    block_count = len(bits) // m
    blocks = bits[: block_count * m].reshape(block_count, m)
    mu = m / 2.0 + (9.0 + (-1.0) ** (m + 1)) / 36.0 - ((m / 3.0) + 2.0 / 9.0) / (2.0 ** m)
    buckets = [0] * 7
    for block in blocks:
        complexity = _berlekamp_massey(block)
        t_value = ((-1) ** m) * (complexity - mu) + 2.0 / 9.0
        if t_value <= -2.5:
            buckets[0] += 1
        elif t_value <= -1.5:
            buckets[1] += 1
        elif t_value <= -0.5:
            buckets[2] += 1
        elif t_value <= 0.5:
            buckets[3] += 1
        elif t_value <= 1.5:
            buckets[4] += 1
        elif t_value <= 2.5:
            buckets[5] += 1
        else:
            buckets[6] += 1
    statistic = 0.0
    for observed, probability in zip(buckets, _LINEAR_COMPLEXITY_PI):
        expected = block_count * probability
        statistic += (observed - expected) ** 2 / expected
    p_value = float(gammaincc(3.0, statistic / 2.0))
    return _build_result(
        f"GB/T 32915 线性复杂度检测 (m={m})",
        p_value,
        "线性复杂度分布满足标准要求。",
        "线性复杂度分布偏离标准要求。",
        "按照标准 4.13 用 Berlekamp-Massey 算法评估各块线性复杂度分布。",
        (
            TestMetric("块长 m", str(m)),
            TestMetric("块数 N", str(block_count)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.13", "m": m, "counts": tuple(buckets), "p_value": p_value},
    )


def _maurer_universal_test(bits: np.ndarray) -> TestResult:
    n = len(bits)
    l_value, q, k = _select_maurer_l(n)
    total_blocks = q + k
    usable = bits[: total_blocks * l_value].reshape(total_blocks, l_value)
    weights = (1 << np.arange(l_value - 1, -1, -1, dtype=np.int64))
    values = usable.dot(weights)
    table = np.zeros(1 << l_value, dtype=np.int64)
    for index in range(q):
        table[int(values[index])] = index + 1
    accum = 0.0
    for index in range(q, q + k):
        value = int(values[index])
        distance = (index + 1) - int(table[value])
        accum += math.log2(distance)
        table[value] = index + 1
    fn = accum / k
    mean, sigma = _maurer_stats(l_value, k)
    statistic = abs((fn - mean) / sigma)
    p_value = float(erfc(statistic / math.sqrt(2.0)))
    return _build_result(
        "GB/T 32915 Maurer 通用统计检测",
        p_value,
        "序列不可压缩性满足标准要求。",
        "序列不可压缩性偏离标准要求。",
        "按照标准 4.14 评估 L 位模式最近间距的对数平均值。",
        (
            TestMetric("L", str(l_value)),
            TestMetric("Q", str(q)),
            TestMetric("K", str(k)),
            TestMetric("fn", f"{fn:.6f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.14", "L": l_value, "p_value": p_value},
    )


def _discrete_fourier_test(bits: np.ndarray) -> TestResult:
    transformed = 2 * bits.astype(np.float64) - 1.0
    spectrum = np.fft.fft(transformed)
    modulus = np.abs(spectrum[: len(bits) // 2])
    threshold = math.sqrt(2.995732274 * len(bits))
    n0 = 0.95 * len(bits) / 2.0
    n1 = int(np.count_nonzero(modulus < threshold))
    statistic = abs((n1 - n0) / math.sqrt(0.95 * 0.05 * len(bits) / 4.0))
    p_value = float(erfc(statistic / math.sqrt(2.0)))
    return _build_result(
        "GB/T 32915 离散傅立叶检测",
        p_value,
        "频谱峰值分布满足标准要求。",
        "频谱峰值分布偏离标准要求。",
        "按照标准 4.15 检测频域内异常峰值个数是否超过允许范围。",
        (
            TestMetric("门限 T", f"{threshold:.2f}"),
            TestMetric("N0", f"{n0:.1f}"),
            TestMetric("N1", str(n1)),
            TestMetric("统计量", f"{statistic:.4f}"),
        ),
        {"kind": "gbt32915_item", "section": "4.15", "p_value": p_value},
    )


def _generate_sample_bits(algorithm: str, trial: int) -> np.ndarray:
    encrypt = get_algorithm(algorithm)["encrypt"]
    key = _sample_bytes(f"{algorithm}:gbt32915:key:{trial}", _key_size_for_algorithm(algorithm))
    plaintext = _sample_bytes(f"{algorithm}:gbt32915:pt:{trial}", _SEQUENCE_BYTES)
    tweak = _associated_data(algorithm, f"gbt32915:{trial}")
    ciphertext = encrypt(key, plaintext, tweak)
    return np.unpackbits(np.frombuffer(ciphertext, dtype=np.uint8))


def _run_single_suite(bits: np.ndarray) -> list[TestResult]:
    return [
        _frequency_test(bits),
        _block_frequency_test(bits, _BLOCK_FREQUENCY_M),
        *(_poker_test(bits, m) for m in _POKER_M),
        *(_overlapping_template_test(bits, m) for m in _OVERLAPPING_M),
        _runs_total_test(bits),
        _runs_distribution_test(bits),
        _longest_run_test(bits, _LONGEST_RUN_M),
        *(_binary_derivative_test(bits, k) for k in _BINARY_DERIVATIVE_K),
        *(_autocorrelation_test(bits, d) for d in _AUTOCORRELATION_D),
        _matrix_rank_test(bits),
        _cumulative_sums_test(bits),
        _approximate_entropy_test(bits, _APPROXIMATE_ENTROPY_M),
        _linear_complexity_test(bits, _LINEAR_COMPLEXITY_M),
        _maurer_universal_test(bits),
        _discrete_fourier_test(bits),
    ]


def _run_gbt32915_multi(algorithm: str, sample_count: int) -> tuple[TestResult, ...]:
    all_trial_results: list[list[TestResult]] = []
    for trial in range(sample_count):
        if trial == 0:
            bits = _bit_sequence(algorithm)
        else:
            bits = _generate_sample_bits(algorithm, trial)
        all_trial_results.append(_run_single_suite(bits))

    num_tests = len(all_trial_results[0])
    final_results: list[TestResult] = []
    for test_idx in range(num_tests):
        pass_count = sum(
            1 for trial_results in all_trial_results
            if trial_results[test_idx].status == TestStatus.PASSED
        )
        pass_rate = pass_count / sample_count
        representative = all_trial_results[0][test_idx]

        if pass_rate >= _PASS_RATE_THRESHOLD:
            status = TestStatus.PASSED
        else:
            status = TestStatus.FAILED

        extra_metrics = representative.metrics + (
            TestMetric("通过率", f"{pass_count}/{sample_count}"),
        )
        artifacts = dict(representative.artifacts)
        artifacts["pass_rate"] = pass_rate
        artifacts["pass_count"] = pass_count
        artifacts["sample_count"] = sample_count

        final_results.append(TestResult(
            category=representative.category,
            name=representative.name,
            status=status,
            summary=representative.summary if status == TestStatus.PASSED else representative.summary.replace("满足", "偏离").replace("良好", "偏弱") if status == TestStatus.FAILED else representative.summary,
            details=representative.details,
            metrics=extra_metrics,
            artifacts=artifacts,
        ))

    ciphertext = _ciphertext_sample(algorithm)
    bits_first = _bit_sequence(algorithm)
    counts, chi_history = _byte_histogram(algorithm)
    ones_ratio = _count_ones(bits_first) / len(bits_first)
    zeros_ratio = 1.0 - ones_ratio
    expected = len(ciphertext) / 256.0
    chi_square = float(sum(((count - expected) ** 2) / expected for count in counts)) if expected else 0.0
    passed = sum(1 for r in final_results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in final_results if r.status == TestStatus.FAILED)
    status = TestStatus.PASSED if failed == 0 else TestStatus.WARNING if passed >= len(final_results) * 0.8 else TestStatus.FAILED

    summary_result = TestResult(
        category=TestCategory.SECURITY,
        name="GB/T 32915 随机性测试总览",
        status=status,
        summary=(
            "标准随机性检测整体表现良好。"
            if status == TestStatus.PASSED
            else "标准随机性检测存在少量未通过项。"
            if status == TestStatus.WARNING
            else "标准随机性检测未通过项较多。"
        ),
        details=f"基于 {sample_count} 组独立密钥样本（各 1,000,000 比特）执行 GB/T 32915 第 4 章检测，按通过率≥{_PASS_RATE_THRESHOLD*100:.0f}%判定。",
        metrics=(
            TestMetric("样本组数", str(sample_count)),
            TestMetric("样本长度", f"{len(bits_first)} 比特"),
            TestMetric("通过项", str(passed)),
            TestMetric("失败项", str(failed)),
            TestMetric("1 比例", f"{ones_ratio * 100:.2f}%"),
            TestMetric("字节卡方", f"{chi_square:.2f}"),
        ),
        artifacts={
            "kind": "randomness",
            "ones_ratio": ones_ratio,
            "zeros_ratio": zeros_ratio,
            "chi_square": chi_square,
            "chi_history": chi_history,
            "byte_counts": counts,
            "sample_count": sample_count,
            "total_bytes": len(ciphertext),
            "passed": passed,
            "failed": failed,
            "gbt_tests": tuple((r.name, r.status.value) for r in final_results),
        },
    )
    return (summary_result, *final_results)


@lru_cache(maxsize=None)
def run_gbt32915_suite(algorithm: str) -> tuple[TestResult, ...]:
    return _run_gbt32915_multi(algorithm, sample_count=_DEFAULT_SAMPLE_COUNT)
