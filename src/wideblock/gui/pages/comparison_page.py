from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ...testing import ComparisonReport, TestCategory, algorithm_label, run_comparison_report_stream_for_category
from ..widgets import MetricCard, build_comparison_performance_charts, build_comparison_security_charts
from ..workers import start_streaming_task


_MODE_TEXT = {
    TestCategory.PERFORMANCE: "性能交叉对比",
    TestCategory.SECURITY: "安全性交叉对比",
}

_MODE_HINT = {
    TestCategory.PERFORMANCE: "仅执行性能相关测试，比较时延、吞吐量、峰值内存和密钥扩展复杂度。",
    TestCategory.SECURITY: "仅执行安全性相关测试，比较随机性、卡方统计和雪崩效应。",
}


class ComparisonResultPage(QWidget):
    def __init__(self, algorithms: list[str], category: TestCategory, parent: QWidget | None = None):
        super().__init__(parent)
        self.algorithms = list(algorithms)
        self.category = category

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("contentShell")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        title = QLabel(_MODE_TEXT[self.category])
        title.setObjectName("title")
        subtitle = QLabel(_MODE_HINT[self.category])
        subtitle.setObjectName("subtitle")
        selected_text = "、".join(algorithm_label(name) for name in self.algorithms)
        self.meta_label = QLabel(f"已选算法: {selected_text}")
        self.meta_label.setObjectName("subtitle")
        self.meta_label.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        text_col.addWidget(self.meta_label)

        self.progress_text = QLabel(f"准备执行{_MODE_TEXT[self.category]}...")
        self.progress_text.setObjectName("subtitle")
        text_col.addWidget(self.progress_text)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        text_col.addWidget(self.progress_bar)
        hero_layout.addLayout(text_col, 1)

        self.run_button = QPushButton("重新运行")
        self.run_button.setProperty("class", "primary")
        self.run_button.clicked.connect(self._run_report)
        hero_layout.addWidget(self.run_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(hero)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.metric_count = MetricCard("参与算法", str(len(self.algorithms)))
        if self.category == TestCategory.PERFORMANCE:
            self.metric_primary = MetricCard("最快加密", "-")
            self.metric_secondary = MetricCard("最高吞吐", "-")
            self.metric_status = MetricCard("已完成算法", "-")
        else:
            self.metric_primary = MetricCard("安全结论", "-")
            self.metric_secondary = MetricCard("警告数量", "-")
            self.metric_status = MetricCard("已完成算法", "-")
        for card in [self.metric_count, self.metric_primary, self.metric_secondary, self.metric_status]:
            metrics_row.addWidget(card)
        root.addLayout(metrics_row)

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(14)
        self.content_scroll.setWidget(content)
        root.addWidget(self.content_scroll, 1)

        table_card = QFrame()
        table_card.setObjectName("contentShell")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(12)

        table_title = QLabel("对比结果")
        table_title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        table_layout.addWidget(table_title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["算法", "正确性", "加密性能", "解密性能", "安全性", "备注"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table, 1)
        self.content_layout.addWidget(table_card)

        self.chart_grid = QGridLayout()
        self.chart_grid.setHorizontalSpacing(14)
        self.chart_grid.setVerticalSpacing(14)
        self.content_layout.addLayout(self.chart_grid)

        note_card = QFrame()
        note_card.setObjectName("contentShell")
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(18, 18, 18, 18)
        note_layout.setSpacing(12)

        note_title = QLabel("对比说明")
        note_title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        note_layout.addWidget(note_title)

        self.summary_label = QLabel(f"准备执行{_MODE_TEXT[self.category]}...")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #18242d; line-height: 1.6;")
        note_layout.addWidget(self.summary_label)

        self.notes = QLabel("-")
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.notes.setStyleSheet("color: #5f7382; line-height: 1.7;")
        note_layout.addWidget(self.notes)
        note_layout.addStretch(1)
        self.content_layout.addWidget(note_card)

    def _clear_chart_grid(self) -> None:
        while self.chart_grid.count():
            item = self.chart_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _run_report(self) -> None:
        self.run_button.setEnabled(False)
        self.run_button.setText("对比中...")
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"准备执行{_MODE_TEXT[self.category]}...")
        self.summary_label.setText("正在逐个执行算法测试，表格会在部分结果完成后即时更新。")
        self.notes.setText("-")
        self.table.setRowCount(0)
        self._clear_chart_grid()
        start_streaming_task(
            run_comparison_report_stream_for_category,
            self._show_report,
            self._show_error,
            self._show_progress,
            self._show_partial,
            self.algorithms,
            self.category,
        )

    def _show_progress(self, current: int | float, total: int, text: str) -> None:
        value = 0 if total <= 0 else int(max(0.0, min(1.0, float(current) / float(total))) * 100)
        self.progress_bar.setValue(value)
        self.progress_text.setText(text)

    def _show_partial(self, report: object) -> None:
        if isinstance(report, ComparisonReport):
            self._render_report(report, partial=True)

    def _show_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("重新运行")
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"{_MODE_TEXT[self.category]}执行失败")
        self.summary_label.setText(f"{_MODE_TEXT[self.category]}执行失败。")
        self.notes.setText(message)
        self.table.setRowCount(0)
        self._clear_chart_grid()

    def _show_report(self, report: ComparisonReport) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("重新运行")
        self.progress_bar.setValue(100)
        self.progress_text.setText(f"{_MODE_TEXT[self.category]}已完成")
        self._render_report(report, partial=False)

    def _render_report(self, report: ComparisonReport, *, partial: bool) -> None:
        self.metric_count.set_value(str(len(report.rows)))
        self.metric_status.set_value(f"{len(report.rows)}/{len(self.algorithms)}")
        if self.category == TestCategory.PERFORMANCE:
            fastest = self._best_by_column(report, 2, reverse=False)
            highest_tp = self._best_throughput(report)
            self.metric_primary.set_value(fastest.algorithm if fastest is not None else "-")
            self.metric_secondary.set_value(highest_tp.algorithm if highest_tp is not None else "-")
        else:
            states = {row.security for row in report.rows if row.security and row.security != "-"}
            warnings = sum(1 for row in report.rows if "警告" in row.security)
            self.metric_primary.set_value(" / ".join(sorted(states)) if states else "-")
            self.metric_secondary.set_value(str(warnings))

        self.table.setRowCount(len(report.rows))
        for row_index, row in enumerate(report.rows):
            values = [row.algorithm, row.correctness, row.encrypt_speed, row.decrypt_speed, row.security, row.notes]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col_index, item)
        self.table.resizeColumnsToContents()

        self._clear_chart_grid()
        charts = build_comparison_performance_charts(report.reports) if self.category == TestCategory.PERFORMANCE else build_comparison_security_charts(report.reports)
        for index, chart in enumerate(charts):
            self.chart_grid.addWidget(chart, index // 2, index % 2)

        if partial:
            self.summary_label.setText(f"已完成 {len(report.rows)}/{len(self.algorithms)} 个算法，正在继续更新对比结果。")
        elif self.category == TestCategory.PERFORMANCE:
            self.summary_label.setText("已完成性能交叉对比，可继续查看时延、吞吐量、峰值内存和密钥扩展复杂度差异。")
        else:
            self.summary_label.setText("已完成安全性交叉对比，可继续查看随机性、卡方统计和雪崩效应差异。")
        self.notes.setText("\n".join(f"- {note}" for note in report.notes) if report.notes else "-")

    def _best_by_column(self, report: ComparisonReport, column: int, *, reverse: bool):
        candidates = []
        for row in report.rows:
            text = [row.algorithm, row.correctness, row.encrypt_speed, row.decrypt_speed, row.security, row.notes][column]
            try:
                value = float(text.split()[0])
            except (ValueError, IndexError):
                continue
            candidates.append((value, row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=reverse)
        return candidates[0][1]

    def _best_throughput(self, report: ComparisonReport):
        candidates = []
        for row in report.rows:
            marker = "加密吞吐 "
            if marker not in row.notes:
                continue
            try:
                value = float(row.notes.split(marker, 1)[1].split()[0])
            except (ValueError, IndexError):
                continue
            candidates.append((value, row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
