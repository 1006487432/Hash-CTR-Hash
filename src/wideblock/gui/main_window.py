from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..testing import algorithm_label, available_algorithms
from .pages import AlgorithmResultPage, ComparisonResultPage


_GROUPS = {
    "HCH 系列": ["hch_aes", "hch_sm4"],
    "HCTR 系列": ["hctr1_aes", "hctr1_sm4", "hctr2"],
    "XCB 系列": ["xcbstar", "xcbstar_sm4", "xcbv1", "xcbv1_sm4", "xcbv2", "xcbv2_sm4"],
}

_ACTIVE_TEXT = QColor("#0f5160")
_NORMAL_TEXT = QColor("#18242d")
_MUTED_TEXT = QColor("#5f7382")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("宽块密码算法测试平台")
        self.resize(1600, 980)
        self.setMinimumSize(1280, 800)
        self._syncing_tree = False

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        layout.addWidget(splitter)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(22, 24, 22, 22)
        side_layout.setSpacing(14)

        brand = QLabel("宽块密码\n算法测试平台")
        brand.setStyleSheet("font-size: 24pt; font-weight: 800;")
        side_layout.addWidget(brand)

        info = QLabel("左侧勾选算法与测试方式\n右侧标签页同时保留多个结果")
        info.setStyleSheet("color: #5f7382; line-height: 1.5;")
        side_layout.addWidget(info)

        pick_title = QLabel("算法选择")
        pick_title.setStyleSheet("font-size: 12pt; font-weight: 700; padding-top: 8px;")
        side_layout.addWidget(pick_title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self._select_all)
        self.clear_all_button = QPushButton("清空")
        self.clear_all_button.clicked.connect(self._clear_all)
        toolbar.addWidget(self.select_all_button)
        toolbar.addWidget(self.clear_all_button)
        side_layout.addLayout(toolbar)

        self.algorithm_tree = QTreeWidget()
        self.algorithm_tree.setHeaderHidden(True)
        self.algorithm_tree.setRootIsDecorated(False)
        self.algorithm_tree.setIndentation(18)
        self.algorithm_tree.itemChanged.connect(self._handle_item_changed)
        side_layout.addWidget(self.algorithm_tree, 1)

        self.selection_label = QLabel("当前已勾选 0 个算法")
        self.selection_label.setStyleSheet("color: #5f7382; font-size: 9.5pt;")
        side_layout.addWidget(self.selection_label)

        self.single_button = QPushButton("打开单算法测试")
        self.single_button.setProperty("class", "primary")
        self.single_button.clicked.connect(self._open_single_tab)
        side_layout.addWidget(self.single_button)

        self.compare_button = QPushButton("打开交叉对比测试")
        self.compare_button.clicked.connect(self._open_comparison_tab)
        side_layout.addWidget(self.compare_button)

        self.hint_label = QLabel(
            "使用方式:\n"
            "1. 勾选一个算法，打开单算法测试\n"
            "2. 勾选多个算法，打开交叉对比测试\n"
            "3. 右侧标签页可并行保留多个结果"
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #5f7382; font-size: 9.5pt; padding-top: 6px;")
        side_layout.addWidget(self.hint_label)

        self.status_label = QLabel("请先勾选算法。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #d28c1f; font-size: 9.5pt; padding-top: 4px;")
        side_layout.addWidget(self.status_label)

        self._build_algorithm_tree()
        self.algorithm_tree.expandAll()

        content_panel = QFrame()
        content_panel.setObjectName("contentPanel")
        content_outer = QVBoxLayout(content_panel)
        content_outer.setContentsMargins(14, 14, 14, 14)
        content_outer.setSpacing(0)

        content = QFrame()
        content.setObjectName("contentShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header = QLabel("结果展示")
        header.setStyleSheet("font-size: 17pt; font-weight: 800;")
        header_row.addWidget(header)
        header_row.addStretch(1)
        content_layout.addLayout(header_row)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        content_layout.addWidget(self.tabs, 1)

        content_outer.addWidget(content)

        splitter.addWidget(sidebar)
        splitter.addWidget(content_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1220])

    def _build_algorithm_tree(self) -> None:
        self._syncing_tree = True
        self.algorithm_tree.clear()
        all_names = set(available_algorithms())
        for group_name, names in _GROUPS.items():
            present = [name for name in names if name in all_names]
            if not present:
                continue
            parent = QTreeWidgetItem([group_name])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            parent.setData(0, Qt.ItemDataRole.UserRole, None)
            self.algorithm_tree.addTopLevelItem(parent)
            for name in present:
                child = QTreeWidgetItem([algorithm_label(name)])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, name)
                parent.addChild(child)
            self._apply_item_visuals(parent)
        self._syncing_tree = False
        self._refresh_selection_label()

    def _checked_algorithm_names(self) -> list[str]:
        selected: list[str] = []
        for index in range(self.algorithm_tree.topLevelItemCount()):
            parent = self.algorithm_tree.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.checkState(0) == Qt.CheckState.Checked:
                    selected.append(child.data(0, Qt.ItemDataRole.UserRole))
        return selected

    def _set_status(self, text: str, *, warn: bool = True) -> None:
        color = "#d28c1f" if warn else "#5f7382"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 9.5pt; padding-top: 4px;")
        self.status_label.setText(text)

    def _refresh_selection_label(self) -> None:
        count = len(self._checked_algorithm_names())
        self.selection_label.setText(f"当前已勾选 {count} 个算法")

    def _set_subtree_state(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for index in range(item.childCount()):
            item.child(index).setCheckState(0, state)

    def _update_parent_state(self, parent: QTreeWidgetItem) -> None:
        checked = 0
        partial = 0
        for index in range(parent.childCount()):
            state = parent.child(index).checkState(0)
            if state == Qt.CheckState.PartiallyChecked:
                partial += 1
            elif state == Qt.CheckState.Checked:
                checked += 1
        if checked == parent.childCount():
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif checked == 0 and partial == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _apply_item_visuals(self, item: QTreeWidgetItem) -> None:
        state = item.checkState(0)
        font = QFont()
        if item.childCount() > 0:
            font.setBold(True)
            if state == Qt.CheckState.Checked:
                item.setForeground(0, _ACTIVE_TEXT)
            elif state == Qt.CheckState.PartiallyChecked:
                item.setForeground(0, QColor("#9a6d18"))
            else:
                item.setForeground(0, _NORMAL_TEXT)
        else:
            font.setBold(state == Qt.CheckState.Checked)
            item.setForeground(0, _ACTIVE_TEXT if state == Qt.CheckState.Checked else _NORMAL_TEXT)
        item.setFont(0, font)
        for index in range(item.childCount()):
            self._apply_item_visuals(item.child(index))

    def _handle_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._syncing_tree or column != 0:
            return
        self._syncing_tree = True
        if item.childCount() > 0:
            self._set_subtree_state(item, item.checkState(0))
        else:
            parent = item.parent()
            if parent is not None:
                self._update_parent_state(parent)
                self._apply_item_visuals(parent)
        self._apply_item_visuals(item)
        self._syncing_tree = False
        self._refresh_selection_label()

    def _select_all(self) -> None:
        self._syncing_tree = True
        for index in range(self.algorithm_tree.topLevelItemCount()):
            parent = self.algorithm_tree.topLevelItem(index)
            parent.setCheckState(0, Qt.CheckState.Checked)
            self._set_subtree_state(parent, Qt.CheckState.Checked)
            self._apply_item_visuals(parent)
        self._syncing_tree = False
        self._refresh_selection_label()
        self._set_status("已全选全部算法。", warn=False)

    def _clear_all(self) -> None:
        self._syncing_tree = True
        for index in range(self.algorithm_tree.topLevelItemCount()):
            parent = self.algorithm_tree.topLevelItem(index)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            self._set_subtree_state(parent, Qt.CheckState.Unchecked)
            self._apply_item_visuals(parent)
        self._syncing_tree = False
        self._refresh_selection_label()
        self._set_status("已清空全部勾选。", warn=False)

    def _open_single_tab(self) -> None:
        selected = self._checked_algorithm_names()
        if not selected:
            self._set_status("未勾选算法，无法打开单算法测试。")
            return
        algorithm = selected[0]
        page = AlgorithmResultPage(algorithm)
        self.tabs.addTab(page, f"算法 | {algorithm_label(algorithm)}")
        self.tabs.setCurrentWidget(page)
        self._set_status(f"已打开 {algorithm_label(algorithm)} 的测试结果页。", warn=False)

    def _open_comparison_tab(self) -> None:
        selected = self._checked_algorithm_names()
        if len(selected) < 2:
            self._set_status("交叉对比测试至少需要勾选两个算法。")
            return
        page = ComparisonResultPage(selected)
        summary = " / ".join(algorithm_label(name) for name in selected[:2])
        if len(selected) > 2:
            summary += f" 等{len(selected)}个"
        self.tabs.addTab(page, f"对比 | {summary}")
        self.tabs.setCurrentWidget(page)
        self._set_status(f"已打开 {len(selected)} 个算法的交叉对比结果页。", warn=False)

    def _close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
