from src.wideblock.testing.models import (
    AlgorithmReport,
    ComparisonReport,
    ComparisonRow,
    TestCategory,
    TestMetric,
    TestResult,
    TestStatus,
)
from src.wideblock.testing.report import generate_report


def test_comparison_report_omits_extra_security_findings(tmp_path):
    algorithm_report = AlgorithmReport(
        algorithm="xcbstar_aes",
        runtime_ms=1.0,
        results=(
            TestResult(
                category=TestCategory.SECURITY,
                name="GB/T 32915 总览",
                status=TestStatus.PASSED,
                summary="通过随机性检测",
                metrics=(
                    TestMetric("通过项", "21"),
                    TestMetric("失败项", "0"),
                    TestMetric("1 比例", "50.00%"),
                    TestMetric("字节卡方", "230.00"),
                ),
                artifacts={"kind": "randomness"},
            ),
            TestResult(
                category=TestCategory.SECURITY,
                name="雪崩效应",
                status=TestStatus.PASSED,
                summary="通过雪崩效应检测",
                metrics=(
                    TestMetric("平均", "50.00%"),
                    TestMetric("最小", "48.00%"),
                    TestMetric("标准差", "1.20%"),
                ),
                artifacts={"kind": "avalanche"},
            ),
            TestResult(
                category=TestCategory.SECURITY,
                name="公开研究提示",
                status=TestStatus.WARNING,
                summary="不应作为额外小节输出",
                artifacts={"kind": "known_attack"},
            ),
        ),
    )
    report = ComparisonReport(
        rows=(
            ComparisonRow(
                algorithm="XCB* (AES)",
                correctness="通过",
                encrypt_speed="-",
                decrypt_speed="-",
                security="警告",
            ),
        ),
        reports=(algorithm_report,),
    )

    output_path = tmp_path / "comparison.md"
    generate_report(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "### 其他安全性发现" not in content
    assert "公开研究提示" not in content
    assert "### GB/T 32915 随机性检测总览" in content
    assert "### 雪崩效应" in content
