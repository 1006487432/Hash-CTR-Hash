from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from ...testing import AlgorithmReport, TestCategory, algorithm_label, run_algorithm_report, run_algorithm_report_stream, run_category_report_stream
from ...testing.report import generate_report
from ..widgets import MetricCard, ResultCard, build_performance_charts, build_security_charts
from ..workers import start_streaming_task


_CATEGORY_TEXT = {
    TestCategory.CORRECTNESS: "正确性测试",
    TestCategory.PERFORMANCE: "性能测试",
    TestCategory.SECURITY: "安全性测试",
}

_CATEGORY_HINT = {
    TestCategory.CORRECTNESS: "单独执行往返与基本正确性检查，不触发性能和安全性测试。",
    TestCategory.PERFORMANCE: "单独执行速度、吞吐量、周期/字节、内存占用和密钥扩展复杂度分析。",
    TestCategory.SECURITY: "单独执行随机性、雪崩效应等安全性测试，不触发性能测试。",
}


class AlgorithmResultPage(QWidget):
    def __init__(self, algorithm: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.algorithm = algorithm
        # 每个类别的报告独立缓存，用户可以分开运行并保留已有结果。
        self._category_reports: dict[TestCategory, AlgorithmReport] = {}
        self._category_layouts: dict[TestCategory, QVBoxLayout] = {}
        self._active_category: TestCategory | None = None
        self._buttons: dict[TestCategory, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(14)

        self.toggle_top_btn = QPushButton("收起测试信息与操作面板 ▴")
        self.toggle_top_btn.setCheckable(True)
        self.toggle_top_btn.setStyleSheet(
            "QPushButton { border: none; color: #5f7382; font-weight: bold; text-align: left; padding: 4px; }"
            "QPushButton:hover { color: #18242d; }"
        )
        self.toggle_top_btn.clicked.connect(self._toggle_top_panel)
        root.addWidget(self.toggle_top_btn)

        self.top_panel = QWidget()
        top_layout = QVBoxLayout(self.top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("contentShell")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        title = QLabel(f"算法测试: {algorithm_label(self.algorithm)}")
        title.setObjectName("title")
        subtitle = QLabel("该标签页支持将正确性、性能和安全性测试分别执行，结果会保留在对应标签页中。")
        subtitle.setObjectName("subtitle")
        self.meta_label = QLabel(f"内部标识: {self.algorithm}")
        self.meta_label.setObjectName("subtitle")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        text_col.addWidget(self.meta_label)
        hero_layout.addLayout(text_col)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        for category in TestCategory:
            button = QPushButton(f"运行{_CATEGORY_TEXT[category]}")
            button.clicked.connect(lambda _checked=False, cat=category: self._run_category(cat))
            if category == TestCategory.PERFORMANCE:
                button.setProperty("class", "primary")
            self._buttons[category] = button
            button_row.addWidget(button)

        self.report_button = QPushButton("生成完整报告")
        self.report_button.clicked.connect(self._generate_report)
        button_row.addWidget(self.report_button)
        button_row.addStretch(1)
        hero_layout.addLayout(button_row)

        self.progress_text = QLabel("请选择要执行的测试类型。")
        self.progress_text.setObjectName("subtitle")
        hero_layout.addWidget(self.progress_text)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        hero_layout.addWidget(self.progress_bar)
        top_layout.addWidget(hero)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.metric_algorithm = MetricCard("算法", algorithm_label(self.algorithm))
        self.metric_passed = MetricCard("通过", "-")
        self.metric_failed = MetricCard("失败", "-")
        self.metric_runtime = MetricCard("累计耗时", "-")
        self.metric_checks = MetricCard("已完成项", "-")
        for card in [self.metric_algorithm, self.metric_passed, self.metric_failed, self.metric_runtime, self.metric_checks]:
            metrics_row.addWidget(card)
        top_layout.addLayout(metrics_row)
        
        root.addWidget(self.top_panel)

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
            placeholder = QLabel(_CATEGORY_HINT[category])
            placeholder.setWordWrap(True)
            container_layout.addWidget(placeholder)
            container_layout.addStretch(1)
            scroll.setWidget(container)
            page_layout.addWidget(scroll)

            self._category_layouts[category] = container_layout
            self.category_tabs.addTab(page, _CATEGORY_TEXT[category])
        root.addWidget(self.category_tabs, 1)

    def _toggle_top_panel(self, checked: bool) -> None:
        self.top_panel.setVisible(not checked)
        if checked:
            self.toggle_top_btn.setText("展开测试信息与操作面板 ▾")
        else:
            self.toggle_top_btn.setText("收起测试信息与操作面板 ▴")

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _render_category(self, category: TestCategory) -> None:
        layout = self._category_layouts[category]
        self._clear_layout(layout)
        report = self._category_reports.get(category)
        if report is None:
            empty = QLabel(_CATEGORY_HINT[category])
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #5f7382; padding: 10px 6px;")
            layout.addWidget(empty)
            layout.addStretch(1)
            return

        results = list(report.results)
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

    def _update_metrics(self) -> None:
        all_results = [result for report in self._category_reports.values() for result in report.results]
        runtime_ms = sum(report.runtime_ms for report in self._category_reports.values())
        passed = sum(1 for result in all_results if result.status.value == "passed")
        failed = sum(1 for result in all_results if result.status.value == "failed")
        self.metric_algorithm.set_value(algorithm_label(self.algorithm))
        self.metric_passed.set_value(str(passed) if all_results else "-")
        self.metric_failed.set_value(str(failed) if all_results else "-")
        self.metric_runtime.set_value(f"{runtime_ms:.1f} ms" if all_results else "-")
        self.metric_checks.set_value(str(len(all_results)) if all_results else "-")

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for button in self._buttons.values():
            button.setEnabled(enabled)
        if enabled:
            for category, button in self._buttons.items():
                button.setText(f"运行{_CATEGORY_TEXT[category]}")
        elif self._active_category is not None:
            self._buttons[self._active_category].setText(f"{_CATEGORY_TEXT[self._active_category]}运行中...")

    def _run_category(self, category: TestCategory) -> None:
        self._active_category = category
        self._set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"准备执行{_CATEGORY_TEXT[category]}。")
        layout = self._category_layouts[category]
        self._clear_layout(layout)
        wait = QLabel(f"正在执行{_CATEGORY_TEXT[category]}，请稍候...\n{_CATEGORY_HINT[category]}")
        wait.setWordWrap(True)
        layout.addWidget(wait)
        layout.addStretch(1)
        self.category_tabs.setCurrentIndex(list(TestCategory).index(category))
        start_streaming_task(
            run_category_report_stream,
            self._show_report,
            self._show_error,
            self._show_progress,
            self._show_partial,
            self.algorithm,
            category,
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
        self._category_reports[category] = report
        self._update_metrics()
        self._render_category(category)
        self.category_tabs.setCurrentIndex(list(TestCategory).index(category))

    def _show_error(self, message: str) -> None:
        category = self._active_category
        self._set_buttons_enabled(True)
        self.progress_bar.setValue(0)
        self.progress_text.setText("测试执行失败")
        if category is not None:
            layout = self._category_layouts[category]
            self._clear_layout(layout)
            label = QLabel(f"测试执行失败:\n{message}")
            label.setWordWrap(True)
            layout.addWidget(label)
            layout.addStretch(1)

    def _show_report(self, report: AlgorithmReport) -> None:
        category = self._active_category
        self._set_buttons_enabled(True)
        self.progress_bar.setValue(100)
        if category is None:
            self.progress_text.setText("测试已完成")
            return
        self._category_reports[category] = report
        self.progress_text.setText(f"{_CATEGORY_TEXT[category]}已完成")
        self._update_metrics()
        self._render_category(category)
        self.category_tabs.setCurrentIndex(list(TestCategory).index(category))

    def _generate_report(self) -> None:
        if not self._category_reports:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle("运行完整测试")
            msg.setText("尚未运行任何测试。是否立即运行完整测试（正确性+性能+安全性）并生成报告？")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setStyleSheet("QMessageBox { background-color: white; } QLabel { color: black; } QPushButton { color: black; }")
            reply = msg.exec()
            if reply == QMessageBox.StandardButton.Yes:
                self._run_full_test_and_report()
            return

        default_path = Path.cwd() / "reports" / f"{self.algorithm}_report.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存测试报告",
            str(default_path),
            "Markdown 文件 (*.md);;所有文件 (*.*)"
        )

        if not file_path:
            return

        try:
            all_results = []
            total_runtime = 0.0
            for category in [TestCategory.CORRECTNESS, TestCategory.PERFORMANCE, TestCategory.SECURITY]:
                if category in self._category_reports:
                    report = self._category_reports[category]
                    all_results.extend(report.results)
                    total_runtime += report.runtime_ms

            combined_report = AlgorithmReport(
                algorithm=self.algorithm,
                results=tuple(all_results),
                runtime_ms=total_runtime
            )

            generate_report(combined_report, Path(file_path))
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("报告生成成功")
            msg.setText(f"测试报告已保存至:\n{file_path}")
            msg.setStyleSheet("QMessageBox { background-color: white; } QLabel { color: black; } QPushButton { color: black; }")
            msg.exec()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("报告生成失败")
            msg.setText(f"生成报告时发生错误:\n{str(e)}")
            msg.setStyleSheet("QMessageBox { background-color: white; } QLabel { color: black; } QPushButton { color: black; }")
            msg.exec()

    def _run_full_test_and_report(self) -> None:
        self._set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        self.progress_text.setText("准备执行完整测试...")
        start_streaming_task(
            run_algorithm_report_stream,
            self._on_full_test_complete,
            self._show_error,
            self._show_progress,
            self._show_partial,
            self.algorithm,
        )

    def _on_full_test_complete(self, report: AlgorithmReport) -> None:
        self._set_buttons_enabled(True)
        self.progress_bar.setValue(100)
        self.progress_text.setText("完整测试已完成")
        for category in TestCategory:
            category_results = [r for r in report.results if r.category == category]
            if category_results:
                cat_report = AlgorithmReport(
                    algorithm=report.algorithm,
                    results=tuple(category_results),
                    runtime_ms=report.runtime_ms / 3
                )
                self._category_reports[category] = cat_report
                self._render_category(category)
        self._update_metrics()
        self._generate_report()
