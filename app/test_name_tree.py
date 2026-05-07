#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/test_name_tree.py
@Time   : 2023/05/08
@Desc   : 测试项树状列表
"""

import re
import sys
from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QTreeWidget, \
    QTreeWidgetItem, QStyledItemDelegate, QTreeWidgetItemIterator, QFrame, QSpacerItem, QSizePolicy, QLineEdit, \
    QAbstractItemView, QComboBox
from PyQt5.QtCore import Qt

from . import util
from .format_dialog import FormatDialog

BEGIN_REGEX = r"\ (Number[^A-Z]*)(Site[^A-Z]*)(Result[^A-Z]*)(Test\ Name[^A-Z]*)(Pin[^A-Z]*)(Channel[^A-Z]*)" \
              r"(Low[^A-Z]*)(Measured[^A-Z]*)(High[^A-Z]*)(Force[^A-Z]*)(Loc[^A-Z]*)\n"
TEST_NAME_PIN_REGEX = r"\ (.{11})(.{6})(.{9})(.{26})(.{12})(.{10})(.{15})(.{15})(.{15})(.{15})(.{3})\s+"


class TreeNode(object):
    """docstring for TreeNode"""

    def __init__(self, name: str, values: OrderedDict, children: OrderedDict):
        self.name = name
        self.values = values
        self.children = children

    def __str__(self):
        if self.children is None or len(self.children) == 0:
            return f"{{ name: {self.name} }}"
        else:
            return f"{{ name: {self.name}, children: {', '.join([str(child) for child in self.children.values()])} }}"


class ReadonlyDelegate(QStyledItemDelegate):
    """docstring for FullSizedDelegate
    禁止编辑委派类
    """

    def createEditor(self, parent: QTreeWidgetItem, option, index):  # pylint: disable=unused-argument,invalid-name
        """ 忽略编辑，如果有子节点则折叠 """
        if index.child(0, 0).data() is not None:
            item = parent.parent().topLevelItem(index.row())
            item.setExpanded(not item.isExpanded())


class FullSizedDelegate(QStyledItemDelegate):
    """docstring for FullSizedDelegate
    自动调整宽度委派类
    """

    def updateEditorGeometry(self, parent, option, index):  # pylint: disable=unused-argument,invalid-name
        parent.setGeometry(option.rect)


class TestNameTree(QWidget):
    """docstring for TestNameTree
    测试项树状列表
    """

    signal_has_checked = QtCore.pyqtSignal(int)
    mode = "泰瑞达"

    def __init__(self, parent=None):
        super(TestNameTree, self).__init__(parent)
        self.parent = parent
        self.tree = QTreeWidget()
        self.tree_iterator = None
        self.tree_item_count = 0
        self.pin_map = None
        self.begin_regex = BEGIN_REGEX
        self.regex = TEST_NAME_PIN_REGEX
        # self.setMinimumHeight(800)
        # self.resize(908, 600)
        # self.setMinimumSize(908, 600)
        self.setWindowTitle("测试项树状列表")
        self.setStyleSheet("\
            QPushButton { font-family: \"微软雅黑\"; max-width: 50px; } \
            QScrollArea { border: none } \
            QTreeView { height: 28px; font-family: \"微软雅黑\"; font-size: 18px; } \
            QTreeView::item { border: solid lightgray; border-width: 1px 1px 0px 0px; } \
            QTreeView::item:closed:!has-siblings:has-children {border: solid lightgray;border-width: 1px 1px 1px 0px;} \
            QTreeView::branch:has-siblings:!adjoins-item { border-image: url(\":/images/branch-vline.png\") 0; } \
            QTreeView::branch:has-siblings:adjoins-item { border-image: url(\":/images/branch-more.png\") 0; } \
            QTreeView::branch:!has-children:!has-siblings:adjoins-item { \
                border-image: url(\":/images/branch-end.png\") 0; } \
            QTreeView::branch:closed:has-children { border-image: none; image: url(\":/images/branch-closed.png\"); } \
            QTreeView::branch:open:has-children { border-image: none; image: url(\":/images/branch-opened.png\"); }")
        self.init_ui()

    def init_ui(self):
        load_btn = QPushButton("导入", self)
        load_btn.clicked.connect(self.load)
        select_all_btn = QPushButton("全选", self)
        select_all_btn.clicked.connect(self.select_all_tree_item)
        reverse_selected_btn = QPushButton("反选", self)
        reverse_selected_btn.clicked.connect(self.reverse_selected_tree_item)
        clear_selected_btn = QPushButton("清空", self)
        clear_selected_btn.clicked.connect(self.clear_selected_tree_item)
        expand_btn = QPushButton("展开", self)
        collapse_btn = QPushButton("折叠", self)
        search_btn = QPushButton("查找", self)

        btn_layout = QHBoxLayout()
        btn_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(reverse_selected_btn)
        btn_layout.addWidget(clear_selected_btn)
        btn_layout.addWidget(expand_btn)
        btn_layout.addWidget(collapse_btn)
        btn_layout.addWidget(search_btn)
        # btn_layout.setSpacing(0)
        # btn_layout.setContentsMargins(0, 0, 0, 0)

        search_line_edit = QLineEdit(self)
        search_line_edit.setStyleSheet("font-size: 18px;")
        search_line_edit.setPlaceholderText("请输入关键字")
        search_line_edit.returnPressed.connect(self.search_item_by_keyword)
        prev_item_btn = QPushButton("上一个", self)
        prev_item_btn.clicked.connect(lambda: self.search_previous_item_by_keyword(search_line_edit.text()))
        next_item_btn = QPushButton("下一个", self)
        next_item_btn.clicked.connect(lambda: self.search_next_item_by_keyword(search_line_edit.text()))

        search_layout = QHBoxLayout()
        search_layout.addWidget(search_line_edit)
        search_layout.addWidget(prev_item_btn)
        search_layout.addWidget(next_item_btn)

        self.search_frame = QFrame()
        self.search_frame.setLayout(search_layout)
        self.search_frame.hide()
        search_btn.clicked.connect(lambda: self.search_frame.setVisible(not self.search_frame.isVisible()))

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: lightgray")

        # 选项树
        self.tree = QTreeWidget()
        expand_btn.clicked.connect(self.tree.expandAll)
        collapse_btn.clicked.connect(self.tree.collapseAll)
        self.tree.itemClicked.connect(self.tree_clicked_handle)
        self.tree.header().setSectionsMovable(False)
        self.tree.setHeaderLabels(["Test Name  〉Pin", "下限", "上限", "单位"])
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        # 展开全部
        # self.tree.expandAll()
        # 首列宽度自适应
        self.tree.resizeColumnToContents(0)
        # 自动调整宽度
        # self.tree.setItemDelegate(FullSizedDelegate(self.tree))
        # 不可编辑
        self.tree.setItemDelegateForColumn(0, ReadonlyDelegate(self.tree))
        layout = QVBoxLayout()
        # layout.setSpacing(0)
        # layout.setContentsMargins(0, 0, 0, 0)
        # btn_layout.setSpacing(7)
        # btn_layout.setContentsMargins(12, 12, 12, 12)
        layout.setContentsMargins(0, 12, 0, 0)
        btn_layout.setContentsMargins(8, 0, 12, 0)
        search_layout.setContentsMargins(12, 0, 12, 0)
        layout.addLayout(btn_layout)
        # layout.addLayout(search_layout)
        layout.addWidget(self.search_frame)
        # layout.addWidget(line)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def load(self):
        """ 打开配置对话框并导入测试项 """
        dialog = FormatDialog(self, load_mode=True)
        dialog.signal_pin_dict.connect(self.generate_tree)
        dialog.resize(500, dialog.height())
        dialog.exec()

    def select_all_tree_item(self):
        """ 全选 """
        it = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.NotChecked)
        while it.value():
            if it.value().childCount() == 0:
                it.value().setCheckState(0, Qt.Checked)
            it.__iadd__(1)

    def reverse_selected_tree_item(self):
        """ 反选 """
        it = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.All)
        while it.value():
            if it.value().childCount() == 0:
                if it.value().checkState(0) == Qt.Checked:
                    it.value().setCheckState(0, Qt.Unchecked)
                elif it.value().checkState(0) == Qt.Unchecked:
                    it.value().setCheckState(0, Qt.Checked)
            it.__iadd__(1)

    def clear_selected_tree_item(self):
        """ 清空 """
        it = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
        while it.value():
            if it.value().childCount() == 0:
                it.value().setCheckState(0, Qt.Unchecked)
            it.__iadd__(1)

    def is_any_selected(self):
        it = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
        while it.value():
            return True
        return False

    def tree_clicked_handle(self):
        if self.is_any_selected():
            self.signal_has_checked.emit(1)
        else:
            self.signal_has_checked.emit(0)

    def get_all_pin(self):
        pin_list = list()
        it = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.All)
        while it.value():
            if it.value().childCount() == 0 and it.value().checkState(0) == Qt.Checked:
                pin = list()
                child = it.value()
                while child:
                    pin.insert(0, child.text(0))
                    child = child.parent()
                pin_list.append(pin)
            it.__iadd__(1)
        return pin_list

    def get_checked_pin_map(self):
        pin_map = OrderedDict()
        try:
            it: QTreeWidgetItemIterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
            while it.value():
                if it.value().childCount() == 0:
                    test_name = it.value().parent().text(0)
                    pin_name = it.value().text(0)

                    if self.mode == "爱德万":
                        testsuite = it.value().parent().parent().text(0)
                        testsuite_od = pin_map.get(testsuite)
                        if not testsuite_od:
                            testsuite_od = OrderedDict()
                            pin_map[testsuite] = testsuite_od
                        test_name_od = testsuite_od.get(test_name)
                        if not test_name_od:
                            test_name_od = OrderedDict()
                            testsuite_od[test_name] = test_name_od
                    else:
                        test_name_od = pin_map.get(test_name)
                        if not test_name_od:
                            test_name_od = OrderedDict()
                            pin_map[test_name] = test_name_od
                    test_name_od[pin_name] = list()

                elif self.mode == "泰瑞达" or it.value().parent():
                    test_name = it.value().text(0)
                    if self.mode == "爱德万":
                        testsuite = it.value().parent().text(0)
                        testsuite_od = pin_map.get(testsuite)
                        if not testsuite_od:
                            testsuite_od = OrderedDict()
                            pin_map[testsuite] = testsuite_od
                        test_name_od = testsuite_od.get(test_name)
                        if not test_name_od:
                            test_name_od = OrderedDict()
                            testsuite_od[test_name] = test_name_od
                    else:
                        test_name_od = pin_map.get(test_name)
                        if not test_name_od:
                            test_name_od = OrderedDict()
                            pin_map[test_name] = test_name_od

                    lower_bound = it.value().text(1)
                    upper_bound = it.value().text(2)
                    if lower_bound is not None and len(lower_bound) > 0:
                        if util.isnumber(lower_bound):
                            test_name_od["__lower_bound"] = Decimal(lower_bound)
                        else:
                            raise Exception("%s下限必须为数字" % test_name)
                    if upper_bound is not None and len(upper_bound) > 0:
                        if util.isnumber(upper_bound):
                            test_name_od["__upper_bound"] = Decimal(upper_bound)
                        else:
                            raise Exception("%s上限必须为数字" % test_name)
                    unit = self.tree.itemWidget(it.value(), 3).currentText()
                    test_name_od["__unit"] = unit
                it.__iadd__(1)
        except Exception as e:
            raise e
        return pin_map

    def generate_tree(self, pin_map):
        self.pin_map = pin_map
        self.tree.clear()
        self.tree_item_count = 0
        self.tree.addTopLevelItems([self.generate_tree_by_dfs(top, self.tree) for top in pin_map.items()])
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 100)
        self.tree.resizeColumnToContents(0)

    def search_item_by_keyword(self, keyword=None):
        if not keyword:
            sender = self.sender()
            if isinstance(sender, QLineEdit):
                keyword = sender.text()
        self.search_next_item_by_keyword(keyword)

    def search_previous_item_by_keyword(self, keyword):
        if len(keyword.strip()) == 0:
            self.tree_iterator = None
            return
        words = re.split(r"\s+", keyword.strip())
        if not self.tree_iterator or not self.tree_iterator.value():
            self.tree_iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.All)
            for _ in range(0, self.tree_item_count - 1):
                self.tree_iterator.__iadd__(1)
        while self.tree_iterator.value():
            text = self.tree_iterator.value().text(0)
            for word in words:
                if text.find(word) > -1:
                    self.tree.scrollToItem(self.tree_iterator.value(), QAbstractItemView.PositionAtTop)
                    self.tree_iterator.value().setSelected(True)
                    self.tree_iterator.__isub__(1)
                    return
            self.tree_iterator.__isub__(1)

    def search_next_item_by_keyword(self, keyword):
        if len(keyword.strip()) == 0:
            self.tree_iterator = None
            return
        words = re.split(r"\s+", keyword.strip())
        if not self.tree_iterator or not self.tree_iterator.value():
            self.tree_iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.All)
        while self.tree_iterator.value():
            text = self.tree_iterator.value().text(0)
            for word in words:
                if text.find(word) > -1:
                    self.tree.scrollToItem(self.tree_iterator.value(), QAbstractItemView.PositionAtTop)
                    self.tree_iterator.value().setSelected(True)
                    self.tree_iterator.__iadd__(1)
                    return
            self.tree_iterator.__iadd__(1)

    def generate_tree_by_dfs(self, values, parent):
        root = QTreeWidgetItem(parent)
        self.tree_item_count += 1
        root.setText(0, values[0])
        root.setCheckState(0, Qt.Unchecked)
        if values[1]:
            for child in values[1].items():
                if isinstance(child[0], str) and not child[0].startswith("__"):
                    self.generate_tree_by_dfs(child, root)
        if root.childCount() == 0 or self.mode == "爱德万" and not root.parent():
            root.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
        elif self.mode == "泰瑞达" or root.parent():
            unit_cb = QComboBox(self.tree)
            unit_cb.setStyleSheet("QComboBox { max-width: 75px; }")
            unit_cb.addItems(["V/A", "mV/mA", "uV/uA", "nV/nA", "pV/pA", "hz", "Khz", "Mhz", "Ghz"])
            unit_cb.setCurrentIndex(2)
            self.tree.setItemWidget(root, 3, unit_cb)
            unit = values[1]["__unit"]
            lower_limit = values[1]["__lower_bound"]
            upper_limit = values[1]["__upper_bound"]
            if isinstance(unit, str):
                if unit.endswith("hz") and unit_cb.findText(unit) > -1:
                    unit_cb.setCurrentText(unit)
                elif unit.find("p") > -1:
                    unit_cb.setCurrentText("pV/pA")
                elif unit.find("n") > -1:
                    unit_cb.setCurrentText("nV/nA")
                elif unit.find("u") > -1:
                    unit_cb.setCurrentText("uV/uA")
                elif unit.find("m") > -1:
                    unit_cb.setCurrentText("mV/mA")
                else:
                    unit_cb.setCurrentText("V/A")
            if isinstance(lower_limit, Decimal):
                root.setText(1, str(util.convert_decimal(lower_limit)))
            if isinstance(upper_limit, Decimal):
                root.setText(2, str(util.convert_decimal(upper_limit)))
            root.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate | Qt.ItemIsEditable)
        return root

    @staticmethod
    def load_test_name(filename, regex=None):
        pin_map = OrderedDict()
        current_regex = TEST_NAME_PIN_REGEX
        if regex:
            current_regex = regex
        with open(filename, "r", encoding="utf-8") as f:
            line = f.readline()
            while not line and len(line) > 0:
                matcher = re.match(current_regex, line)
                if matcher:
                    groups = matcher.groups()
                    if groups[0].strip().isdigit():
                        test_name = groups[3].strip()
                        pin_name = groups[4].strip()
                        if not pin_map.get(test_name):
                            pin_map[test_name] = OrderedDict()
                        pin_map.get(test_name)[pin_name] = OrderedDict()
                line = f.readline()
        return pin_map

    @staticmethod
    def get_tree_values(tree):
        def get_tree_item_values(item: QTreeWidgetItem, columns: list) -> Optional[OrderedDict]:
            if item is None:
                return
            value_map = OrderedDict()
            for v_idx, k in enumerate(columns):
                v = item.text(v_idx)
                value_map[k] = v
            return value_map

        def dfs(root: QTreeWidgetItem, columns: list) -> Optional[TreeNode]:
            """ 深度优先搜索 """
            if root is None:
                return
            if root.checkState(0) == Qt.Unchecked:
                return
            name = root.text(0)
            values = get_tree_item_values(root, columns)
            children = OrderedDict()
            for i in range(0, root.childCount()):
                child = dfs(root.child(i), columns)
                if child is None:
                    continue
                for root_val_k in values:
                    if root_val_k not in child.values.keys() or child.values[root_val_k] == "":
                        # 子节点继承父节点的值
                        child.values[root_val_k] = values.get(root_val_k)
                children[child.name] = child
            return TreeNode(name, values, children)

        columns_ = [tree.headerItem().text(x) for x in range(0, tree.header().count())]
        tree_map = OrderedDict()
        for j in range(0, tree.topLevelItemCount()):
            top = tree.topLevelItem(j)
            if top.checkState(0) == Qt.Unchecked:
                continue
            root_ = dfs(top, columns_)
            tree_map[root_.name] = root_
        return tree_map


if __name__ == "__main__":
    app = QApplication(sys.argv)
    __tree = TestNameTree()
    __tree.show()
    sys.exit(app.exec_())
