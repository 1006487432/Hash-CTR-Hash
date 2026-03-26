from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from ...testing import AlgorithmReport, TestCategory, algorithm_label, run_algorithm_report_stream
from ..widgets import MetricCard, ResultCard, build_performance_charts, build_security_charts
from ..workers import start_streaming_task


_CATEGORY_TEXT = {
    TestCategory.CORRECTNESS: "正确性测试",
    TestCategory.PERFORMANCE: "性能测试",
    TestCategory.SECURITY: "安全性测试",
}


class AlgorithmResultPage(QWidget):
    def __init__(self, algorithm: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.algorithm = algorithm
        self._report: AlgorithmReport | None = None
        self._category_layouts: dict[TestCategory, QVBoxLayout] = {}
        self._loaded_categories: set[TestCategory] = set()

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
        title = QLabel(f"算法测试: {algorithm_label(self.algorithm)}")
        title.setObjectName("title")
        subtitle = QLabel("该标签页展示单个算法的正确性、性能和安全性测试结果。")
        subtitle.setObjectName("subtitle")
        self.meta_label = QLabel(f"内部标识: {self.algorithm}")
        self.meta_label.setObjectName("subtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        text_col.addWidget(self.meta_label)

        self.progress_text = QLabel("准备运行测试...")
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
        hero_layout.addWidget(self.run_button)
        root.addWidget(hero)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.metric_algorithm = MetricCard("算法", algorithm_label(self.algorithm))
        self.metric_passed = MetricCard("通过", "-")
        self.metric_failed = MetricCard("失败", "-")
        self.metric_runtime = MetricCard("总耗时", "-")
        self.metric_checks = MetricCard("检查项", "-")
        for card in [self.metric_algorithm, self.metric_passed, self.metric_failed, self.metric_runtime, self.metric_checks]:
            metrics_row.addWidget(card)
        root.addLayout(metrics_row)

        self.category_tabs = QTabWidget()
        self.category_tabs.setDocumentMode(True)
        for category in TestCategory:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(4, 4, 4, 4)
            container_layout.setSpacing(12)
            placeholder = QLabel("等待该类测试开始...")
            placeholder.setWordWrap(True)
            container_layout.addWidget(placeholder)
            container_layout.addStretch(1)
            scroll.setWidget(container)
            page_layout.addWidget(scroll)

            self._category_layouts[category] = container_layout
            self.category_tabs.addTab(page, _CATEGORY_TEXT[category])
        root.addWidget(self.category_tabs, 1)

        QTimer.singleShot(0, self._run_report)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _render_category(self, category: TestCategory, report: AlgorithmReport) -> None:
        layout = self._category_layouts[category]
        self._clear_layout(layout)
        results = [result for result in report.results if result.category == category]
        if not results:
            empty = QLabel("暂无结果。")
            empty.setStyleSheet("color: #5f7382; padding: 10px 6px;")
            layout.addWidget(empty)
            layout.addStretch(1)
            return

        if category == TestCategory.PERFORMANCE:
            for chart in build_performance_charts(results):
                layout.addWidget(chart)
        elif category == TestCategory.SECURITY:
            for result in results:
                for chart in build_security_charts(result):
                    layout.addWidget(chart)

        for result in results:
            layout.addWidget(ResultCard(result))
        layout.addStretch(1)

    def _update_metrics(self, report: AlgorithmReport) -> None:
        self.metric_algorithm.set_value(algorithm_label(report.algorithm))
        self.metric_passed.set_value(str(report.passed))
        self.metric_failed.set_value(str(report.failed))
        self.metric_runtime.set_value(f"{report.runtime_ms:.1f} ms")
        self.metric_checks.set_value(str(len(report.results)))

    def _run_report(self) -> None:
        self._loaded_categories.clear()
        self.run_button.setEnabled(False)
        self.run_button.setText("运行中...")
        self.progress_bar.setValue(0)
        self.progress_text.setText("准备运行测试...")
        for layout in self._category_layouts.values():
            self._clear_layout(layout)
            wait = QLabel("等待该类测试开始...")
            wait.setWordWrap(True)
            layout.addWidget(wait)
            layout.addStretch(1)
        start_streaming_task(
            run_algorithm_report_stream,
            self._show_report,
            self._show_error,
            self._show_progress,
            self._show_partial,
            self.algorithm,
        )

    def _show_progress(self, current: int | float, total: int, text: str) -> None:
        value = 0 if total <= 0 else int(max(0.0, min(1.0, float(current) / float(total))) * 100)
        self.progress_bar.setValue(value)
        self.progress_text.setText(text)

    def _show_partial(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        report, category = payload
        if not isinstance(report, AlgorithmReport) or not isinstance(category, TestCategory):
            return
        self._report = report
        self._loaded_categories.add(category)
        self._update_metrics(report)
        self._render_category(category, report)
        self.category_tabs.setCurrentIndex(list(TestCategory).index(category))

    def _show_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("重新运行")
        self.progress_bar.setValue(0)
        self.progress_text.setText("测试执行失败")
        for layout in self._category_layouts.values():
            self._clear_layout(layout)
            label = QLabel(f"测试执行失败:\n{message}")
            label.setWordWrap(True)
            layout.addWidget(label)
            layout.addStretch(1)

    def _show_report(self, report: AlgorithmReport) -> None:
        self._report = report
        self.run_button.setEnabled(True)
        self.run_button.setText("重新运行")
        self.progress_bar.setValue(100)
        self.progress_text.setText("全部测试已完成")
        self._update_metrics(report)
        for category in TestCategory:
            self._render_category(category, report)
        self.category_tabs.setCurrentIndex(0)
