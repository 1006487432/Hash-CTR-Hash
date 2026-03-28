from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestCategory(str, Enum):
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    SECURITY = "security"


class TestStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    INFO = "info"


@dataclass(frozen=True)
class TestMetric:
    label: str
    value: str


@dataclass(frozen=True)
class TestResult:
    category: TestCategory
    name: str
    status: TestStatus
    summary: str
    details: str = ""
    metrics: tuple[TestMetric, ...] = ()
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlgorithmReport:
    algorithm: str
    results: tuple[TestResult, ...]
    runtime_ms: float

    @property
    def passed(self) -> int:
        return sum(result.status == TestStatus.PASSED for result in self.results)

    @property
    def warnings(self) -> int:
        return sum(result.status == TestStatus.WARNING for result in self.results)

    @property
    def failed(self) -> int:
        return sum(result.status == TestStatus.FAILED for result in self.results)


@dataclass(frozen=True)
class ComparisonRow:
    algorithm: str
    correctness: str
    encrypt_speed: str
    decrypt_speed: str
    security: str
    notes: str = ""


@dataclass(frozen=True)
class ComparisonReport:
    rows: tuple[ComparisonRow, ...]
    notes: tuple[str, ...] = ()
    reports: tuple[AlgorithmReport, ...] = ()


@dataclass
class RunSelection:
    algorithms: list[str] = field(default_factory=list)
