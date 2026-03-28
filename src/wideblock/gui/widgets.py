from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..testing import AlgorithmReport, TestResult, algorithm_label
from .theme import ACCENT, ACCENT_ALT, MUTED, TEXT, status_color


_STATUS_TEXT = {
    "passed": "通过",
    "warning": "警告",
    "failed": "失败",
    "info": "信息",
}


class CardFrame(QFrame):
    def __init__(self, alt: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("class", "cardAlt" if alt else "card")
        self.setStyleSheet("QFrame { } QFrame.cardAlt { }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(20, 40, 54, 28))
        self.setGraphicsEffect(shadow)


class MetricCard(CardFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"QLabel {{ color: {TEXT}; font-size: 16pt; font-weight: 700; }}")
        self.value_label.setWordWrap(True)
        self.label_widget = QLabel(label)
        self.label_widget.setStyleSheet(f"QLabel {{ color: {MUTED}; font-size: 9pt; }}")
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_widget)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class ResultCard(CardFrame):
    def __init__(self, result: TestResult, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel(result.name)
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        title.setWordWrap(True)
        status = QLabel(_STATUS_TEXT.get(result.status.value, result.status.value))
        color = status_color(result.status.value).name()
        status.setStyleSheet(
            f"background: {color}; color: white; border-radius: 10px; padding: 4px 10px; font-weight: 700;"
        )
        header.addWidget(title, 1)
        header.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        summary = QLabel(result.summary)
        summary.setWordWrap(True)
        summary.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(summary)

        if result.metrics:
            metric_row = QHBoxLayout()
            metric_row.setSpacing(8)
            for metric in result.metrics:
                chip = QLabel(f"{metric.label}: {metric.value}")
                chip.setStyleSheet(
                    f"background: rgba(30,143,163,0.08); border-radius: 10px; padding: 5px 10px; color: {TEXT};"
                )
                metric_row.addWidget(chip)
            metric_row.addStretch(1)
            layout.addLayout(metric_row)

        if result.details:
            details = QLabel(result.details)
            details.setWordWrap(True)
            details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            details.setStyleSheet(f"color: {MUTED}; padding-top: 2px;")
            layout.addWidget(details)


class RatioBar(QWidget):
    def __init__(self, label: str, value: float, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.label = label
        self.value = max(0.0, min(1.0, value))
        self.color = QColor(color)
        self.setMinimumHeight(28)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        label_rect = QRectF(rect.left(), rect.top(), 80, rect.height())
        painter.setPen(QColor(TEXT))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.label)

        bar_rect = QRectF(label_rect.right() + 10, rect.top() + 7, rect.width() - label_rect.width() - 90, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 143, 163, 24))
        painter.drawRoundedRect(bar_rect, 7, 7)

        fill_rect = QRectF(bar_rect.left(), bar_rect.top(), bar_rect.width() * self.value, bar_rect.height())
        painter.setBrush(self.color)
        painter.drawRoundedRect(fill_rect, 7, 7)

        marker_x = bar_rect.left() + bar_rect.width() * 0.5
        painter.setPen(QPen(QColor(198, 162, 77), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(marker_x, bar_rect.top() - 3), QPointF(marker_x, bar_rect.bottom() + 3))

        value_rect = QRectF(bar_rect.right() + 10, rect.top(), 70, rect.height())
        painter.setPen(QColor(TEXT))
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{self.value * 100:.2f}%")


class HistogramWidget(QWidget):
    def __init__(self, values: Sequence[float], bins: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self.values = list(values)
        self.bins = max(4, bins)
        self.setMinimumHeight(160)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -20)
        painter.fillRect(rect, QColor(30, 143, 163, 10))

        if not self.values:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无分布数据")
            return

        counts = [0] * self.bins
        for value in self.values:
            index = min(self.bins - 1, int(max(0.0, min(0.999999, value)) * self.bins))
            counts[index] += 1

        max_count = max(counts) or 1
        gap = 6
        bar_width = (rect.width() - gap * (self.bins - 1)) / self.bins
        for index, count in enumerate(counts):
            height = rect.height() * (count / max_count)
            x = rect.left() + index * (bar_width + gap)
            bar_rect = QRectF(x, rect.bottom() - height, bar_width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 143, 163, 180 if index == self.bins // 2 else 120))
            painter.drawRoundedRect(bar_rect, 4, 4)

        ideal_x = rect.left() + rect.width() * 0.5
        painter.setPen(QPen(QColor(198, 162, 77), 1.4, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(ideal_x, rect.top()), QPointF(ideal_x, rect.bottom()))

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(rect.left(), self.height() - 18, 60, 16), Qt.AlignmentFlag.AlignLeft, "0%")
        painter.drawText(QRectF(self.width() / 2 - 30, self.height() - 18, 60, 16), Qt.AlignmentFlag.AlignCenter, "50%")
        painter.drawText(QRectF(rect.right() - 60, self.height() - 18, 60, 16), Qt.AlignmentFlag.AlignRight, "100%")


class ByteFrequencyWidget(QWidget):
    def __init__(self, counts: Sequence[int], groups: int = 16, parent: QWidget | None = None):
        super().__init__(parent)
        self.counts = list(counts)
        self.groups = max(8, groups)
        self.setMinimumHeight(170)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -20)
        painter.fillRect(rect, QColor(198, 162, 77, 12))

        if not self.counts:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无频率数据")
            return

        group_size = max(1, len(self.counts) // self.groups)
        grouped = [sum(self.counts[i * group_size:(i + 1) * group_size]) for i in range(self.groups)]
        max_count = max(grouped) or 1
        gap = 4
        bar_width = (rect.width() - gap * (self.groups - 1)) / self.groups
        for index, count in enumerate(grouped):
            height = rect.height() * (count / max_count)
            x = rect.left() + index * (bar_width + gap)
            bar_rect = QRectF(x, rect.bottom() - height, bar_width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(198, 162, 77, 150 if index % 4 == 0 else 110))
            painter.drawRoundedRect(bar_rect, 3, 3)

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(rect.left(), self.height() - 18, 80, 16), Qt.AlignmentFlag.AlignLeft, "00")
        painter.drawText(QRectF(self.width() / 2 - 20, self.height() - 18, 40, 16), Qt.AlignmentFlag.AlignCenter, "80")
        painter.drawText(QRectF(rect.right() - 80, self.height() - 18, 80, 16), Qt.AlignmentFlag.AlignRight, "FF")


class MultiSeriesBarChart(QWidget):
    def __init__(self, labels: Sequence[str], values: Sequence[float], title_hint: str, *, scale_max: float | None = None, percent: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.labels = list(labels)
        self.values = list(values)
        self.title_hint = title_hint
        self.scale_max = scale_max
        self.percent = percent
        self.setMinimumHeight(220)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 16, -18, -24)
        painter.fillRect(rect, QColor(30, 143, 163, 10))

        if not self.labels or not self.values:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无对比数据")
            return

        axis_left = rect.left() + 110
        axis_right = rect.right() - 10
        top = rect.top() + 8
        row_gap = 14
        bar_height = max(18, int((rect.height() - row_gap * (len(self.labels) - 1)) / len(self.labels)))
        max_value = self.scale_max if self.scale_max is not None else max(self.values) or 1.0
        painter.setPen(QPen(QColor(30, 143, 163, 55), 1))
        painter.drawLine(QPointF(axis_left, top - 4), QPointF(axis_left, rect.bottom()))

        for index, (label, value) in enumerate(zip(self.labels, self.values, strict=False)):
            y = top + index * (bar_height + row_gap)
            label_rect = QRectF(rect.left(), y, 100, bar_height)
            painter.setPen(QColor(TEXT))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

            bar_rect = QRectF(axis_left, y + 2, axis_right - axis_left, bar_height - 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 143, 163, 24))
            painter.drawRoundedRect(bar_rect, 6, 6)
            fill_width = 0 if max_value <= 0 else bar_rect.width() * (value / max_value)
            fill_rect = QRectF(bar_rect.left(), bar_rect.top(), fill_width, bar_rect.height())
            color = QColor(ACCENT if index % 2 == 0 else ACCENT_ALT)
            painter.setBrush(color)
            painter.drawRoundedRect(fill_rect, 6, 6)

            value_rect = QRectF(bar_rect.right() - 70, y, 70, bar_height)
            painter.setPen(QColor(TEXT))
            text = f"{value * 100:.2f}%" if self.percent else f"{value:.2f}"
            painter.drawText(value_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, text)


class LineChartWidget(QWidget):
    def __init__(self, series: Sequence[tuple[str, Sequence[float]]], parent: QWidget | None = None):
        super().__init__(parent)
        self.series = [(label, list(values)) for label, values in series]
        self.setMinimumHeight(220)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(24, 12, -18, -28)
        painter.fillRect(rect, QColor(198, 162, 77, 10))

        all_values = [value for _, values in self.series for value in values]
        if not all_values:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无历史数据")
            return

        min_value = min(all_values)
        max_value = max(all_values)
        span = max(max_value - min_value, 1e-6)
        colors = [QColor(ACCENT), QColor(ACCENT_ALT), QColor("#2da56c"), QColor("#cb4d4d")]

        painter.setPen(QPen(QColor(30, 143, 163, 45), 1))
        for tick in range(5):
            y = rect.top() + rect.height() * tick / 4
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        for index, (label, values) in enumerate(self.series):
            if len(values) < 2:
                continue
            path_points = []
            for point_index, value in enumerate(values):
                x = rect.left() + rect.width() * point_index / (len(values) - 1)
                y = rect.bottom() - rect.height() * ((value - min_value) / span)
                path_points.append(QPointF(x, y))
            pen = QPen(colors[index % len(colors)], 2.2)
            painter.setPen(pen)
            for first, second in zip(path_points, path_points[1:]):
                painter.drawLine(first, second)
            painter.drawText(QRectF(rect.left() + 6, rect.top() + 4 + index * 16, 180, 14), label)

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(rect.left(), self.height() - 18, 40, 16), Qt.AlignmentFlag.AlignLeft, "1")
        painter.drawText(QRectF(rect.right() - 60, self.height() - 18, 60, 16), Qt.AlignmentFlag.AlignRight, "样本序号")


class RandomnessChartCard(CardFrame):
    def __init__(self, result: TestResult, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        artifacts = result.artifacts
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("随机性比例图")
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel("展示密文比特 0/1 占比，虚线基准为理想的 50%。")
        note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(RatioBar("比特 1", float(artifacts.get("ones_ratio", 0.0)), ACCENT))
        layout.addWidget(RatioBar("比特 0", float(artifacts.get("zeros_ratio", 0.0)), ACCENT_ALT))


class ByteFrequencyChartCard(CardFrame):
    def __init__(self, result: TestResult, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        artifacts = result.artifacts
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("字节频率分布图")
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel("按字节值区间汇总密文频率，观察是否存在异常峰值。")
        note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(ByteFrequencyWidget(artifacts.get("byte_counts", ())))


class AvalancheChartCard(CardFrame):
    def __init__(self, result: TestResult, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        artifacts = result.artifacts
        ratios = tuple(float(value) for value in artifacts.get("ratios", ()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("雪崩翻转分布图")
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel("展示单比特扰动后，密文翻转比例在多次试验中的分布。虚线基准为 50%。")
        note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(HistogramWidget(ratios))

        stat_row = QHBoxLayout()
        stat_row.setSpacing(8)
        for label, value in [
            ("平均", artifacts.get("average_ratio", 0.0)),
            ("最小", artifacts.get("min_ratio", 0.0)),
            ("最大", artifacts.get("max_ratio", 0.0)),
        ]:
            chip = QLabel(f"{label}: {float(value) * 100:.2f}%")
            chip.setStyleSheet(
                f"background: rgba(30,143,163,0.08); border-radius: 10px; padding: 5px 10px; color: {TEXT};"
            )
            stat_row.addWidget(chip)
        stat_row.addStretch(1)
        layout.addLayout(stat_row)


class ComparisonMetricChartCard(CardFrame):
    def __init__(self, title_text: str, note_text: str, labels: Sequence[str], values: Sequence[float], *, scale_max: float | None = None, percent: bool = False, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel(note_text)
        note.setStyleSheet(f"color: {MUTED};")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(MultiSeriesBarChart(labels, values, title_text, scale_max=scale_max, percent=percent))


class ComparisonLineChartCard(CardFrame):
    def __init__(self, title_text: str, note_text: str, series: Sequence[tuple[str, Sequence[float]]], parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel(note_text)
        note.setStyleSheet(f"color: {MUTED};")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(LineChartWidget(series))


class PerformanceLineChartCard(CardFrame):
    def __init__(self, title_text: str, note_text: str, series: Sequence[tuple[str, Sequence[float]]], parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel(note_text)
        note.setStyleSheet(f"color: {MUTED};")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addWidget(LineChartWidget(series))


class KeyScheduleChartCard(CardFrame):
    def __init__(self, result: TestResult, parent: QWidget | None = None):
        super().__init__(alt=True, parent=parent)
        artifacts = result.artifacts
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("密钥扩展复杂度概览")
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {TEXT};")
        note = QLabel("按底层原语、子密钥派生数量和名义调度轮数评估密钥扩展负担。")
        note.setStyleSheet(f"color: {MUTED};")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for label, value in [
            ("原语", artifacts.get("primitive", "-")),
            ("子密钥组数", artifacts.get("derived_key_count", 0)),
            ("调度轮数", artifacts.get("schedule_rounds", 0)),
            ("复杂度", artifacts.get("complexity_level", "-")),
        ]:
            chip = QLabel(f"{label}: {value}")
            chip.setStyleSheet(
                f"background: rgba(30,143,163,0.08); border-radius: 10px; padding: 5px 10px; color: {TEXT};"
            )
            chip_row.addWidget(chip)
        chip_row.addStretch(1)
        layout.addLayout(chip_row)

        details = QLabel(str(artifacts.get("note", "")))
        details.setWordWrap(True)
        details.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(details)


def build_performance_charts(results: Sequence[TestResult], parent: QWidget | None = None) -> list[QWidget]:
    # 图表构建按 artifacts.kind 聚合结果，这样测试层新增指标时不会影响 GUI 其余部分。
    encrypt_latency: list[tuple[int, float]] = []
    decrypt_latency: list[tuple[int, float]] = []
    encrypt_throughput: list[tuple[int, float]] = []
    decrypt_throughput: list[tuple[int, float]] = []
    encrypt_cpb: list[tuple[int, float]] = []
    decrypt_cpb: list[tuple[int, float]] = []
    memory_result: TestResult | None = None
    key_schedule_result: TestResult | None = None

    for result in results:
        artifacts = result.artifacts
        if artifacts.get("operation") == "encrypt" and artifacts.get("kind") == "performance":
            encrypt_latency.append((int(artifacts.get("size", 0)), float(artifacts.get("avg_us", 0.0))))
        elif artifacts.get("operation") == "decrypt" and artifacts.get("kind") == "performance":
            decrypt_latency.append((int(artifacts.get("size", 0)), float(artifacts.get("avg_us", 0.0))))
        elif artifacts.get("operation") == "encrypt" and artifacts.get("kind") == "performance_throughput":
            encrypt_throughput.append((int(artifacts.get("size", 0)), float(artifacts.get("throughput_mib_s", 0.0))))
        elif artifacts.get("operation") == "decrypt" and artifacts.get("kind") == "performance_throughput":
            decrypt_throughput.append((int(artifacts.get("size", 0)), float(artifacts.get("throughput_mib_s", 0.0))))
        elif artifacts.get("operation") == "encrypt" and artifacts.get("kind") == "performance_cpb" and artifacts.get("cpb") is not None:
            encrypt_cpb.append((int(artifacts.get("size", 0)), float(artifacts.get("cpb", 0.0))))
        elif artifacts.get("operation") == "decrypt" and artifacts.get("kind") == "performance_cpb" and artifacts.get("cpb") is not None:
            decrypt_cpb.append((int(artifacts.get("size", 0)), float(artifacts.get("cpb", 0.0))))
        elif artifacts.get("kind") == "memory":
            memory_result = result
        elif artifacts.get("kind") == "key_schedule":
            key_schedule_result = result

    encrypt_latency.sort(key=lambda item: item[0])
    decrypt_latency.sort(key=lambda item: item[0])
    encrypt_throughput.sort(key=lambda item: item[0])
    decrypt_throughput.sort(key=lambda item: item[0])
    encrypt_cpb.sort(key=lambda item: item[0])
    decrypt_cpb.sort(key=lambda item: item[0])

    cards: list[QWidget] = []
    if encrypt_latency or decrypt_latency:
        cards.append(
            PerformanceLineChartCard(
                "性能时延曲线",
                "按消息长度展示平均单次加解密耗时，便于观察算法在不同数据规模下的时延变化。",
                [
                    ("加密", [value for _, value in encrypt_latency]),
                    ("解密", [value for _, value in decrypt_latency]),
                ],
                parent=parent,
            )
        )
    if encrypt_throughput or decrypt_throughput:
        cards.append(
            PerformanceLineChartCard(
                "性能吞吐量曲线",
                "按消息长度展示平均吞吐量，便于横向观察数据规模变化时的处理效率。",
                [
                    ("加密吞吐量", [value for _, value in encrypt_throughput]),
                    ("解密吞吐量", [value for _, value in decrypt_throughput]),
                ],
                parent=parent,
            )
        )
    if encrypt_cpb or decrypt_cpb:
        cards.append(
            PerformanceLineChartCard(
                "周期/字节曲线 (cpb)",
                "按消息长度展示每字节平均消耗的 CPU 时钟周期数，适合在不同 CPU 主频下做更稳定的横向比较。",
                [
                    ("加密 cpb", [value for _, value in encrypt_cpb]),
                    ("解密 cpb", [value for _, value in decrypt_cpb]),
                ],
                parent=parent,
            )
        )
    if memory_result is not None:
        artifacts = memory_result.artifacts
        cards.append(
            PerformanceLineChartCard(
                "峰值内存占用曲线",
                "展示不同消息长度下的 Python 层峰值内存分配，适合比较实现的临时对象与缓冲区开销。",
                [
                    ("加密峰值 KiB", [float(value) for value in artifacts.get("encrypt_peak_kib", ())]),
                    ("解密峰值 KiB", [float(value) for value in artifacts.get("decrypt_peak_kib", ())]),
                ],
                parent=parent,
            )
        )
    if key_schedule_result is not None:
        cards.append(KeyScheduleChartCard(key_schedule_result, parent=parent))
    return cards


def build_security_charts(result: TestResult, parent: QWidget | None = None) -> list[QWidget]:
    kind = result.artifacts.get("kind")
    if kind == "randomness":
        return [
            RandomnessChartCard(result, parent=parent),
            ByteFrequencyChartCard(result, parent=parent),
        ]
    if kind == "avalanche":
        return [AvalancheChartCard(result, parent=parent)]
    return []


def build_comparison_performance_charts(reports: Sequence[AlgorithmReport], parent: QWidget | None = None) -> list[QWidget]:
    # 交叉对比页取各算法在多档消息长度上的平均值，用于做统一口径的横向概览。
    labels: list[str] = []
    encrypt_latency: list[float] = []
    decrypt_latency: list[float] = []
    encrypt_throughput: list[float] = []
    decrypt_throughput: list[float] = []
    encrypt_cpb: list[float] = []
    decrypt_cpb: list[float] = []
    memory_peaks: list[float] = []
    key_scores: list[float] = []

    for report in reports:
        short_label = algorithm_label(report.algorithm)
        enc_perf = []
        dec_perf = []
        enc_tp = []
        dec_tp = []
        enc_cpb = []
        dec_cpb = []
        memory_peak = None
        key_score = None
        for result in report.results:
            kind = result.artifacts.get("kind")
            if kind == "performance" and result.artifacts.get("operation") == "encrypt":
                enc_perf.append(float(result.artifacts.get("avg_us", 0.0)))
            elif kind == "performance" and result.artifacts.get("operation") == "decrypt":
                dec_perf.append(float(result.artifacts.get("avg_us", 0.0)))
            elif kind == "performance_throughput" and result.artifacts.get("operation") == "encrypt":
                enc_tp.append(float(result.artifacts.get("throughput_mib_s", 0.0)))
            elif kind == "performance_throughput" and result.artifacts.get("operation") == "decrypt":
                dec_tp.append(float(result.artifacts.get("throughput_mib_s", 0.0)))
            elif kind == "performance_cpb" and result.artifacts.get("operation") == "encrypt" and result.artifacts.get("cpb") is not None:
                enc_cpb.append(float(result.artifacts.get("cpb", 0.0)))
            elif kind == "performance_cpb" and result.artifacts.get("operation") == "decrypt" and result.artifacts.get("cpb") is not None:
                dec_cpb.append(float(result.artifacts.get("cpb", 0.0)))
            elif kind == "memory":
                memory_peak = max(
                    max((float(value) for value in result.artifacts.get("encrypt_peak_kib", ())), default=0.0),
                    max((float(value) for value in result.artifacts.get("decrypt_peak_kib", ())), default=0.0),
                )
            elif kind == "key_schedule":
                key_score = float(result.artifacts.get("complexity_score", 0.0))

        labels.append(short_label)
        encrypt_latency.append(sum(enc_perf) / len(enc_perf) if enc_perf else 0.0)
        decrypt_latency.append(sum(dec_perf) / len(dec_perf) if dec_perf else 0.0)
        encrypt_throughput.append(sum(enc_tp) / len(enc_tp) if enc_tp else 0.0)
        decrypt_throughput.append(sum(dec_tp) / len(dec_tp) if dec_tp else 0.0)
        encrypt_cpb.append(sum(enc_cpb) / len(enc_cpb) if enc_cpb else 0.0)
        decrypt_cpb.append(sum(dec_cpb) / len(dec_cpb) if dec_cpb else 0.0)
        memory_peaks.append(memory_peak or 0.0)
        key_scores.append(key_score or 0.0)

    cards: list[QWidget] = []
    if labels:
        cards.append(
            ComparisonMetricChartCard(
                "加密时延横向对比",
                "比较各算法平均单次加密耗时，数值越低通常越有利。",
                labels,
                encrypt_latency,
                parent=parent,
            )
        )
        cards.append(
            ComparisonMetricChartCard(
                "解密时延横向对比",
                "比较各算法平均单次解密耗时，数值越低通常越有利。",
                labels,
                decrypt_latency,
                parent=parent,
            )
        )
        cards.append(
            ComparisonMetricChartCard(
                "加密吞吐量横向对比",
                "比较各算法平均加密吞吐量，数值越高通常越有利。",
                labels,
                encrypt_throughput,
                parent=parent,
            )
        )
        cards.append(
            ComparisonMetricChartCard(
                "周期/字节横向对比 (加密)",
                "比较各算法每字节平均消耗的 CPU 周期数，数值越低通常越有利。",
                labels,
                encrypt_cpb,
                parent=parent,
            )
        )
        cards.append(
            ComparisonMetricChartCard(
                "峰值内存占用横向对比",
                "比较 Python 层实现的峰值内存开销，适合观察临时对象与缓冲区成本。",
                labels,
                memory_peaks,
                parent=parent,
            )
        )
        cards.append(
            ComparisonMetricChartCard(
                "密钥扩展复杂度横向对比",
                "基于名义调度轮数和子密钥派生数量构造复杂度分值，数值越高表示密钥调度负担越大。",
                labels,
                key_scores,
                parent=parent,
            )
        )
    return cards


def build_comparison_security_charts(reports: Sequence[AlgorithmReport], parent: QWidget | None = None) -> list[QWidget]:
    labels: list[str] = []
    ones_ratios: list[float] = []
    chi_values: list[float] = []
    avalanche_values: list[float] = []
    chi_series: list[tuple[str, Sequence[float]]] = []

    for report in reports:
        short_label = algorithm_label(report.algorithm)
        for result in report.results:
            kind = result.artifacts.get("kind")
            if kind == "randomness":
                labels.append(short_label)
                ones_ratios.append(float(result.artifacts.get("ones_ratio", 0.0)))
                chi_values.append(float(result.artifacts.get("chi_square", 0.0)))
                chi_series.append((short_label, tuple(float(v) for v in result.artifacts.get("chi_history", ()))))
            elif kind == "avalanche":
                avalanche_values.append(float(result.artifacts.get("average_ratio", 0.0)))

    cards: list[QWidget] = []
    if labels and ones_ratios:
        cards.append(
            ComparisonMetricChartCard(
                "随机性横向对比",
                "对比各算法密文中比特 1 的比例，理想值接近 50%。",
                labels,
                ones_ratios,
                scale_max=1.0,
                percent=True,
                parent=parent,
            )
        )
    if labels and chi_values:
        cards.append(
            ComparisonMetricChartCard(
                "卡方值横向对比",
                "对比各算法密文字节分布的卡方值，越平稳通常越接近均匀分布。",
                labels,
                chi_values,
                parent=parent,
            )
        )
        cards.append(
            ComparisonLineChartCard(
                "卡方历史曲线",
                "展示样本逐步累积时的卡方变化趋势，方便观察随机性统计是否稳定。",
                chi_series,
                parent=parent,
            )
        )
    if labels and avalanche_values:
        cards.append(
            ComparisonMetricChartCard(
                "雪崩效应横向对比",
                "对比明文单比特扰动后平均密文翻转比例，理想值接近 50%。",
                labels,
                avalanche_values,
                scale_max=1.0,
                percent=True,
                parent=parent,
            )
        )
    return cards
