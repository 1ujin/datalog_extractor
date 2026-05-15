#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/format_dialog.py
@Time   : 2023/05/09
@Desc   : 格式对话框
"""

import os
import re
import sys
from collections import OrderedDict
from decimal import Decimal

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QLineEdit, QSpinBox, \
    QPushButton, QMessageBox, QGroupBox, QFileDialog, QCheckBox, QComboBox
from PyQt5.QtCore import Qt, QEvent, QObject

from . import util

REQUIRED = [3, 4, 6, 7, 8, 9]
COLUMN_NAME = ["Number", "Site", "Result", r"Test\ Name", "Pin", "Channel", "Low", "Measured", "High", "Force", "Loc"]
BEGIN_REGEX = r"\ "
TEST_NAME_PIN_REGEX = r"\ "
for i in range(len(COLUMN_NAME)):
    BEGIN_REGEX += r"(%s[^A-Z]*)"
    if i not in REQUIRED:
        BEGIN_REGEX += "?"
    TEST_NAME_PIN_REGEX += r"(.{%d})"
BEGIN_REGEX += r"\n"
TEST_NAME_PIN_REGEX += r"\s+"


class QLineEditEventHandler(QObject):
    """自定义类，实现文件拖拽获得路径"""

    def eventFilter(self, obj: QLineEdit, event):  # pylint: disable=invalid-name
        """
        处理窗体内出现的事件，如果有需要则自行添加if判断语句；
        目前已经实现将拖到控件上文件的路径设置为控件的显示文本；
        """
        if event.type() == QEvent.DragEnter:
            event.accept()
        if event.type() == QEvent.Drop:
            md = event.mimeData()
            if md.hasUrls():
                url = md.urls()[0]
                obj.setText(url.toLocalFile())
                return True
        return super().eventFilter(obj, event)


class FormatDialog(QDialog):
    """docstring for FormatDialog"""

    column_width = [11, 6, 9, 26, 12, 10, 15, 15, 15, 15, 3]
    signal_pin_dict = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, load_mode=False, format_file=None):
        super(FormatDialog, self).__init__(parent)
        self.parent = parent
        self.load_mode = load_mode
        self.regex = None
        self.begin_regex = BEGIN_REGEX % (*COLUMN_NAME,)
        # 设置阻塞整个应用程序
        self.setWindowModality(Qt.ApplicationModal)
        # 设置窗口只有关闭按键
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setWindowTitle("配置")
        self.setStyleSheet("\
            QComboBox { font-family: \"微软雅黑\"; font-size: 18px; } \
            QPushButton { font-family: \"微软雅黑\"; font-size: 18px; max-width: 100px; } \
            QLabel { height: 28px;  font-family: \"微软雅黑\"; font-size: 18px; } \
            QGroupBox { font-family: \"微软雅黑\" } \
            QSpinBox { height: 28px; font-family: \"微软雅黑\"; font-size: 18px; } \
            QLineEdit { height: 28px; font-family: \"微软雅黑\"; font-size: 18px; } \
            QCheckBox { margin: 0px; padding: 0px; font-family: \"微软雅黑\"; font-size: 18px; }")

        # QFormLayout
        self.path_line_edit = QLineEdit(self)
        self.path_line_edit.setAcceptDrops(True)
        self.path_line_edit.installEventFilter(QLineEditEventHandler(self))
        self.mode_cb = QComboBox(self)
        self.mode_cb.addItems(["泰瑞达", "爱德万"])
        path_btn = QPushButton("选择文件", self)
        path_btn.clicked.connect(self.select_datalog)
        datalog_layout = QHBoxLayout()
        datalog_layout.addWidget(self.mode_cb)
        datalog_layout.addWidget(self.path_line_edit)
        datalog_layout.addWidget(path_btn)
        group1 = QGroupBox("请选择 Data Log 文件", self)
        group1.setLayout(datalog_layout)

        form_layout = QFormLayout()
        form_layout.setAlignment(Qt.AlignHCenter)
        form_layout.setFormAlignment(Qt.AlignHCenter)
        for idx, pair in enumerate(zip(COLUMN_NAME, self.column_width)):
            name = pair[0].replace("\\", "")
            # lbl = QLabel(name)
            row = QHBoxLayout()
            checkbox = QCheckBox(name, self)
            checkbox.setCheckState(Qt.Checked)
            row.addWidget(checkbox)
            row.setContentsMargins(0, 0, 0, 0)
            spin = QSpinBox(self)
            spin.setMaximum(50)
            spin.setMinimum(len(name))
            spin.setValue(pair[1])
            row.addWidget(spin)
            form_layout.addRow(row)
        for idx, cb in enumerate(self.findChildren(QCheckBox)):
            if idx in REQUIRED:
                cb.setDisabled(True)
        group2 = QGroupBox("请确认并调整 Data Log 每列数据的宽度", self)
        group2.setLayout(form_layout)

        confirm_btn = QPushButton("确定", self)
        confirm_btn.clicked.connect(self.confirm)

        layout = QVBoxLayout(self)
        layout.addWidget(group1)
        layout.addWidget(group2)
        layout.setStretch(0, 0)
        layout.setStretch(1, 0)
        layout.addWidget(confirm_btn, alignment=Qt.AlignHCenter)
        self.mode_cb.currentTextChanged.connect(lambda text: [
            setattr(parent, "mode", text),
            group2.setHidden(text != "泰瑞达"),
            self.adjustSize(),
            None
        ][-1])
        self.mode_cb.setCurrentText(getattr(parent, "mode"))
        self.path_line_edit.textChanged.connect(self.load_datalog)

        if not self.load_mode:
            group1.hide()

        if format_file:
            self.path_line_edit.setText(format_file)

    def select_datalog(self):
        filename = QFileDialog.getOpenFileName(self, "选择 DataLog 文件", filter="All Files (*.*);;Text Files (*.txt)",
                                               initialFilter="Text Files (*.txt)")[0]
        if filename is None or len(filename) == 0:
            return
        self.path_line_edit.setText(filename)
        setattr(self.parent, "format_file", filename)

    def load_datalog(self, filename):
        if self.mode_cb.currentText() == "爱德万":
            return
        with open(filename, "r", encoding="utf-8") as f:
            line = f.readline()
            while line is not None and len(line) > 0:
                matcher = re.match(self.begin_regex, line)
                if matcher:
                    groups = matcher.groups()
                    for (x, y, z) in zip(self.findChildren(QSpinBox), self.findChildren(QCheckBox), groups):
                        if z is not None:
                            x.setValue(len(z))
                            y.setCheckState(Qt.Checked)
                        else:
                            y.setCheckState(Qt.Unchecked)
                    break
                line = f.readline()

    def confirm(self):
        self.regex = self.get_regex()
        self.parent.regex = self.regex
        self.parent.begin_regex = self.begin_regex
        if self.load_mode:
            datalog_path = self.path_line_edit.text()
            if datalog_path is not None and len(datalog_path) > 0:
                if not os.path.exists(datalog_path):
                    QMessageBox.critical(self, "提示", "找不到文件：\n" + datalog_path)
                else:
                    if self.mode_cb.currentText() == "爱德万":
                        pin_map = self.load_test_name_v93k(datalog_path)
                    else:
                        pin_map = self.load_test_name_j750(datalog_path, self.regex)
                    self.signal_pin_dict.emit(pin_map)
        self.close()

    def get_regex(self):
        self.column_width = list()
        for (x, y) in zip(self.findChildren(QSpinBox), self.findChildren(QCheckBox)):
            if y.checkState() == Qt.Unchecked:
                self.column_width.append(0)
            else:
                self.column_width.append(x.value())
        regex = TEST_NAME_PIN_REGEX % (*self.column_width,)
        return regex

    @staticmethod
    def load_test_name_j750(filename, regex=None):
        pin_map = OrderedDict()
        with open(filename, "r", encoding="utf-8") as f:
            line = f.readline()
            while line is not None and len(line) > 0:
                matcher = re.match(regex, line)
                if matcher:
                    groups = matcher.groups()
                    if groups[0].strip().isdigit():
                        test_name = groups[3].strip()
                        pin_name = groups[4].strip()
                        lower_limit, lower_unit = groups[6].strip().split(" ", 1)
                        upper_limit, upper_unit = groups[8].strip().split(" ", 1)

                        test_od = pin_map.get(test_name)
                        if test_od is None:
                            test_od = OrderedDict()
                            pin_map[test_name] = test_od
                            test_od["__unit"] = lower_unit
                            test_od["__lower_bound"] = Decimal(lower_limit)
                            test_od["__upper_bound"] = util.convert_unit(Decimal(upper_limit), upper_unit, lower_unit)
                        test_od[pin_name] = OrderedDict()
                line = f.readline()
        return pin_map

    @staticmethod
    def load_test_name_v93k(filename):
        pin_map = OrderedDict()
        with open(filename, "r", encoding="utf-8") as f:
            line = f.readline()
            testsuite = ""
            test_name = ""
            upper_limit = ""
            lower_limit = ""
            limit_unit = ""
            while line is not None and len(line) > 0:
                # Testsuite
                testsuite_begin_regex = r"=+\ Started\ Testsuite\s+(.+)\ =+"
                matcher = re.match(testsuite_begin_regex, line)
                if matcher:
                    groups = matcher.groups()
                    testsuite = groups[0]
                    line = f.readline()
                    continue
                # Test Name Without Functional
                test_name_begin_regex = r"-+\ Test\ Name:\s+(.+):\ .+\ -+"
                matcher = re.match(test_name_begin_regex, line)
                if matcher:
                    groups = matcher.groups()
                    test_name = groups[0]
                    if test_name.lower().startswith("function"):
                        test_name = ""
                        line = f.readline()
                    else:
                        f.readline()
                        line = f.readline()
                        line = line.strip()
                        if line.lower().find("limits:") > -1:
                            line = line[line.find("[") + 1:line.rfind("]")].strip()
                            lower_limit, upper_limit = line.split(",", 1)
                            lower_limit, limit_unit = lower_limit.strip().split(" ")
                            upper_limit = upper_limit.strip().split(" ")[0]
                    continue
                # Pin Name
                pin_results_begin_regex = r"-+\ Pin\ Results\ -+"
                matcher = re.match(pin_results_begin_regex, line)
                if matcher:
                    line = f.readline()
                    while line is not None and len(line.strip()) > 0:
                        pin_name = line.strip().split(" ")[0]
                        if len(testsuite) > 0:
                            testsuite_dict = pin_map.get(testsuite)
                            if not testsuite_dict:
                                testsuite_dict = OrderedDict()
                                pin_map[testsuite] = testsuite_dict
                        else:
                            line = f.readline()
                            continue
                        if len(test_name) > 0:
                            test_name_dict = testsuite_dict.get(test_name)
                            if not test_name_dict:
                                test_name_dict = OrderedDict()
                                testsuite_dict[test_name] = test_name_dict
                                test_name_dict["__unit"] = limit_unit
                                test_name_dict["__lower_bound"] = Decimal(lower_limit)
                                test_name_dict["__upper_bound"] = Decimal(upper_limit)
                        else:
                            line = f.readline()
                            continue
                        if len(pin_name) > 0:
                            pin_name_dict = test_name_dict.get(pin_name)
                            if not pin_name_dict:
                                pin_name_dict = OrderedDict()
                                test_name_dict[pin_name] = pin_name_dict
                            del pin_name
                        else:
                            line = f.readline()
                            continue
                        line = f.readline()
                else:
                    line = f.readline()
        return pin_map


if __name__ == "__main__":
    app = QApplication(sys.argv)
    __dialog = FormatDialog()
    __dialog.show()
    # __dialog.setFixedHeight(__dialog.height())
    sys.exit(app.exec_())
