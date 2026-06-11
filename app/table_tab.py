#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/table.py
@Time   : 2023/05/22
@Desc   : 表格组件
"""
import gc
import os
import re
import sys
import traceback
from collections import OrderedDict
from decimal import Decimal
from typing import Tuple

from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QFileDialog, QTabWidget, QTableWidget, QTableWidgetItem, QMessageBox, QProgressDialog, \
    QInputDialog, QTabBar

from . import datalog_extractor, util  # pylint: disable=unused-import
from .error_dialog import ErrorDialog

MIN_SIZE = -sys.maxsize - 1
FAILED_COLOR = QBrush(QColor(255, 0, 0))
FILENAME_REGEX = r"^([0-9]+)(_(?i)failed)?\.(?i)txt"
RGB_WHITE = 256 * 256 * 256
CHIP_ID_COL = 0
PASS_FLAG_COL = 1
ROUND_NUM_COL = 2


class EditableTabBar(QTabBar):
    """docstring for EditableTabBar"""

    # 定义一个自定义信号，用于通知 TabWidget 更新文本
    tab_text_changed = QtCore.pyqtSignal(int, str)

    def mouseDoubleClickEvent(self, event):  # pylint: disable=invalid-name
        # 获取双击位置的标签索引
        index = self.tabAt(event.pos())
        if index != -1:
            # 弹出输入对话框，默认显示当前名称
            new_name, reply = QInputDialog.getText(self, "修改标签名", "请输入新名称:", text=self.tabText(index),
                                                   flags=Qt.Dialog | Qt.WindowCloseButtonHint)
            # 如果用户点击了确定，并且输入不为空
            if reply and new_name:
                # 发射信号，告诉外界标签文本变了
                self.tab_text_changed.emit(index, new_name)

        # 调用父类的处理，保证默认行为不受影响
        super().mouseDoubleClickEvent(event)


class TableTab(QTabWidget):
    """docstring for Table"""
    only_failed = False
    show_retest = True
    freeze_cell = None

    def __init__(self, parent: "datalog_extractor.DatalogExtractor"):
        super(TableTab, self).__init__(parent)
        tab_bar = EditableTabBar()
        tab_bar.tab_text_changed.connect(self.setTabText)
        self.setTabBar(tab_bar)
        self.setMovable(True)
        self.setTabPosition(QTabWidget.South)
        self.setStyleSheet("QTabWidget:pane { padding: 0px; } QTabBar { qproperty-drawBase: 0; }")
        self.parent = parent
        self.progress = None
        self.taskbar_progress = None

    @staticmethod
    def extract_j750(path, compare_chip_dict, pin_map, regex, begin_regex, show_retest: bool):
        total = 0
        # 读取文件
        with open(path, "r", encoding="utf-8") as f:
            line = f.readline()
            while line is not None and len(line) > 0:
                if re.match(begin_regex, line):
                    break
                line = f.readline()
            line = f.readline()
            while line is not None and len(line) > 0:
                matcher = re.match(regex, line)
                if not matcher:
                    line = f.readline()
                    continue
                group = matcher.groups()
                test_name = group[3].strip()
                pin_name = group[4].strip()
                # 匹配测试项
                test_dict = pin_map.get(test_name)
                if test_dict is None:
                    # 该测试项未被选中
                    line = f.readline()
                    continue

                compare_test_dict = compare_chip_dict.get(test_name)
                if compare_test_dict is None:
                    compare_test_dict = dict()
                    compare_chip_dict[test_name] = compare_test_dict

                if test_dict is not None:
                    test_unit = test_dict.get("__unit")

                    # 匹配Pin
                    pin_dict = test_dict.get(pin_name)
                    if pin_dict is not None:
                        compare_pin_values = compare_test_dict.get(pin_name)
                        if compare_pin_values is None:
                            compare_pin_values = list()
                            compare_test_dict[pin_name] = compare_pin_values

                        val, val_unit = group[7].strip().split(" ", 1)
                        val = util.convert_unit(val, val_unit, test_unit)

                        if not show_retest:
                            compare_pin_values.clear()
                        compare_pin_values.append(val)
                        total += 1
                line = f.readline()
        return total

    @staticmethod
    def extract_v93k(path, compare_chip_dict, pin_map, show_retest: bool):
        total = 0
        # 读取文件
        with open(path, "r", encoding="utf-8") as f:
            compare_testsuite_od = None
            compare_test_dict = None
            line = f.readline()
            while line is not None and len(line) > 0:
                # Testsuite
                testsuite_begin_regex = r"=+\ Started\ Testsuite\s+(.+)\ =+"
                matcher = re.match(testsuite_begin_regex, line)
                if matcher:
                    groups = matcher.groups()
                    testsuite = groups[0]
                    # 匹配 testsuite
                    testsuite_od = pin_map.get(testsuite)
                    if testsuite_od is not None:
                        compare_testsuite_od = compare_chip_dict.get(testsuite)
                        if compare_testsuite_od is None:
                            compare_testsuite_od = OrderedDict()
                            compare_chip_dict[testsuite] = compare_testsuite_od
                    else:
                        test_dict = None
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
                    if testsuite_od:
                        # 匹配 test name
                        test_dict = testsuite_od.get(test_name)
                        if test_dict is not None:
                            compare_test_dict = compare_testsuite_od.get(test_name)
                            if compare_test_dict is None:
                                compare_test_dict = dict()
                                compare_testsuite_od[test_name] = compare_test_dict

                            test_unit = test_dict.get("__unit")
                    else:
                        test_dict = None
                    line = f.readline()
                    continue
                # Pin Name
                pin_results_begin_regex = r"-+\ Pin\ Results\ -+"
                matcher = re.match(pin_results_begin_regex, line)
                if matcher:
                    line = f.readline()
                    while line is not None and len(line.strip()) > 0:
                        if testsuite_od and test_dict:
                            pin_name, _, val, val_unit = re.split(r"\s+", line.strip())
                            pin_dict = test_dict.get(pin_name)
                            if pin_dict is not None:
                                compare_pin_values = compare_test_dict.get(pin_name)
                                if compare_pin_values is None:
                                    compare_pin_values = list()
                                    compare_test_dict[pin_name] = compare_pin_values
                                val = util.convert_unit(val, val_unit, test_unit)

                                if not show_retest:
                                    compare_pin_values.clear()
                                compare_pin_values.append(val)
                                total += 1
                        else:
                            line = f.readline()
                            break
                        line = f.readline()
                else:
                    line = f.readline()
        return total

    def extract_data_to_dict(self, path_lists, pin_map, regex, begin_regex):
        # 解析文件名并分类
        path_dict: OrderedDict = OrderedDict()
        id_error = list()
        duplicate_error = list()
        temperature_error = list()

        for folder in path_lists.items():
            folder_od = OrderedDict()
            path_dict[folder[0]] = folder_od
            for path in folder[1]:
                # 提取编号
                basename = os.path.basename(path)
                matcher = re.match(FILENAME_REGEX, basename)
                if matcher:
                    chip_id = matcher.groups()[0]
                    passed = matcher.groups()[1] is None
                    if not passed:
                        chip_id += matcher.groups()[1]
                else:
                    id_error.append(path)
                    continue
                if folder_od.get(chip_id):
                    duplicate_error.append(path)
                    continue
                folder_od[chip_id] = (path, passed, OrderedDict())

        error_reply = 1
        if len(id_error) + len(duplicate_error) + len(temperature_error) > 0:
            if self.progress:
                self.progress.reset()
                if sys.platform == "win32":
                    self.taskbar_progress.resume()
                    self.taskbar_progress.reset()
            # 错误列表
            dialog = ErrorDialog(self)
            dialog.fill_id_error_list(id_error)
            dialog.fill_duplicate_error_list(duplicate_error)
            dialog.fill_temperature_error_list(temperature_error)
            error_reply = dialog.exec()

        if error_reply != 1:
            raise Exception("user canceled")

        if self.progress:
            sum_length = sum([len(x) for x in path_dict.values()])
            self.progress.setLabelText("正在解析文件内容")
            self.progress.setRange(0, sum_length)
            self.progress.setValue(0)
            if sys.platform == "win32":
                self.taskbar_progress = self.parent.taskbar_progress
                self.taskbar_progress.setRange(0, sum_length)
                self.taskbar_progress.setValue(0)

        done = 0
        total = 0
        for folder_od in path_dict.values():
            folder_od: OrderedDict
            for file_tuple in folder_od.values():
                file_tuple: Tuple[str, bool, OrderedDict]
                done += 1
                if self.progress:
                    if self.progress.wasCanceled():
                        raise Exception("user canceled")
                    self.progress.setValue(done)
                    if sys.platform == "win32":
                        self.taskbar_progress.setValue(done)
                path, passed, compare_chip_dict = file_tuple
                if self.parent.test_name_tree.mode == "爱德万":
                    total += self.extract_v93k(path, compare_chip_dict, pin_map, self.show_retest)
                else:
                    total += self.extract_j750(path, compare_chip_dict, pin_map, regex, begin_regex, self.show_retest)

        if self.progress:
            self.progress.setLabelText("正在填充表格")
            self.progress.setRange(0, total)
            self.progress.setValue(0)
            if sys.platform == "win32":
                self.taskbar_progress = self.parent.taskbar_progress
                self.taskbar_progress.setRange(0, total)
                self.taskbar_progress.setValue(0)
        return pin_map, path_dict, id_error, temperature_error, duplicate_error

    def fill_table(self, path_lists, pin_map, regex, begin_regex):
        if self.progress is None:
            self.progress = QProgressDialog(self)
        self.progress.setWindowTitle("请稍等...")
        self.progress.setLabelText("正在计算文件数量")
        self.progress.setCancelButtonText("停止")
        self.progress.setMinimumDuration(100)
        self.progress.setFixedWidth(500)
        # 窗口是应用的模式窗口，阻塞所有其他应用窗口获得输入
        self.progress.setWindowModality(Qt.ApplicationModal)
        # 设置窗口标题只有关闭
        self.progress.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        self.progress.setValue(0)
        if sys.platform == "win32":
            self.taskbar_progress = self.parent.taskbar_progress
            self.taskbar_progress.setValue(0)

        try:
            pin_map, path_dict, *_ = self.extract_data_to_dict(path_lists, pin_map, regex, begin_regex)
        except Exception as e:  # pylint: disable=broad-except
            self.progress.cancel()
            if sys.platform == "win32":
                self.taskbar_progress.stop()
            if str(e) == "user canceled":
                QMessageBox.information(self, "提示", "已取消")
            else:
                tb = traceback.extract_tb(e.__traceback__)[-1]
                QMessageBox.critical(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)
            self.progress.reset()
            if sys.platform == "win32":
                self.taskbar_progress.resume()
                self.taskbar_progress.reset()
            gc.collect()
            return

        if len(path_dict) == 0:
            QMessageBox.warning(self, "提示", "请选择至少一个有效的Datalog！")
            return

        try:
            done = 0
            for folder_idx, folder_item in enumerate(path_dict.items()):
                self.progress.setLabelText("正在填充表格（" + str(folder_idx + 1) + "/" + str(len(path_dict)) + "）")
                folder_path, folder_od = folder_item
                folder_name = os.path.basename(folder_path)
                table = QTableWidget(0, 0)

                table.clear()
                table.setColumnCount(ROUND_NUM_COL + 1)
                if self.parent.test_name_tree.mode == "爱德万":
                    chip_row = 6
                    table.setRowCount(chip_row)
                    table.setItem(0, CHIP_ID_COL, self.get_table_item("TestSuite"))
                    table.setItem(0, PASS_FLAG_COL, self.get_table_item("PASSFG"))
                    table.setItem(1, CHIP_ID_COL, self.get_table_item("Test Name"))
                    table.setItem(2, CHIP_ID_COL, self.get_table_item("Pin"))
                    table.setItem(3, CHIP_ID_COL, self.get_table_item("Min"))
                    table.setItem(4, CHIP_ID_COL, self.get_table_item("Max"))
                    table.setItem(5, CHIP_ID_COL, self.get_table_item("Unit"))
                else:
                    chip_row = 5
                    table.setRowCount(chip_row)
                    table.setItem(0, CHIP_ID_COL, self.get_table_item("Test Name"))
                    table.setItem(0, PASS_FLAG_COL, self.get_table_item("PASSFG"))
                    table.setItem(1, CHIP_ID_COL, self.get_table_item("Pin"))
                    table.setItem(2, CHIP_ID_COL, self.get_table_item("Min"))
                    table.setItem(3, CHIP_ID_COL, self.get_table_item("Max"))
                    table.setItem(4, CHIP_ID_COL, self.get_table_item("Unit"))
                    table.setRowCount(chip_row)
                # table.setSpan(0, CHIP_ID_COL, chip_row, 2)
                # table.setItem(0, CHIP_ID_COL, self.get_table_item(folder_path, Qt.AlignVCenter | Qt.TextWordWrap))

                testsuite_col = ROUND_NUM_COL + 1
                self.freeze_cell = (testsuite_col + 1, chip_row + 1)
                if self.parent.test_name_tree.mode == "泰瑞达":
                    self.fill_table_headers(table, pin_map, 0, testsuite_col)
                else:
                    for testsuite_item in pin_map.items():
                        if self.progress.wasCanceled():
                            table.setRowCount(0)
                            table.setColumnCount(0)
                            table.clear()
                            raise Exception("user canceled")
                        # 循环测试项
                        testsuite, test_dict = testsuite_item
                        test_name_col = self.fill_table_headers(table, test_dict, 1, testsuite_col)
                        table.setItem(0, testsuite_col, self.get_table_item(testsuite))
                        table.setSpan(0, testsuite_col, 1, test_name_col)
                        if test_name_col > 10:
                            table.item(0, testsuite_col).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        testsuite_col += test_name_col

                # 测试结果
                for compare_chip_item in folder_od.items():
                    # 循环样品
                    testsuite_col = ROUND_NUM_COL + 1
                    max_round_row = 1
                    chip_id, (_, passed, chip_dict) = compare_chip_item
                    table.insertRow(table.rowCount())
                    if self.parent.test_name_tree.mode == "泰瑞达":
                        _, max_round_row, done = self.fill_table_contents(
                            table, chip_dict, pin_map, chip_row, testsuite_col, max_round_row, done)
                    else:
                        for testsuite_item in pin_map.items():
                            if self.progress.wasCanceled():
                                table.setRowCount(0)
                                table.setColumnCount(0)
                                table.clear()
                                raise Exception("user canceled")
                            testsuite, testsuite_od = testsuite_item
                            compare_testsuite_od = chip_dict.get(testsuite)
                            test_name_col, max_round_row, done = self.fill_table_contents(
                                table, compare_testsuite_od, testsuite_od, chip_row, testsuite_col, max_round_row, done)
                            testsuite_col += test_name_col

                    # 芯片编号
                    if table.item(chip_row, CHIP_ID_COL)\
                            and table.item(chip_row, CHIP_ID_COL).background().color().rgb() % RGB_WHITE != 0:
                        table.item(chip_row, CHIP_ID_COL).setText(chip_id)
                    else:
                        table.setItem(chip_row, CHIP_ID_COL, self.get_table_item(chip_id))
                    table.setSpan(chip_row, CHIP_ID_COL, max_round_row, 1)
                    table.setSpan(chip_row, PASS_FLAG_COL, max_round_row, 1)
                    if max_round_row > 1:
                        for i in range(max_round_row):
                            table.setItem(chip_row + i, ROUND_NUM_COL, self.get_table_item(i + 1))
                    if passed is False:
                        table.item(chip_row, CHIP_ID_COL).setBackground(FAILED_COLOR)
                        table.setItem(chip_row, PASS_FLAG_COL, self.get_table_item("FAIL"))
                        table.item(chip_row, PASS_FLAG_COL).setBackground(FAILED_COLOR)
                    else:
                        table.setItem(chip_row, PASS_FLAG_COL, self.get_table_item("PASS"))
                    chip_row += max_round_row

                round_col_removable = True
                for j in range(table.rowCount()):
                    item = table.item(j, ROUND_NUM_COL)
                    if item is not None and item.text().isdigit() and int(item.text()) > 1:
                        round_col_removable = False
                        break
                if round_col_removable:
                    # 删除多轮序号
                    table.removeColumn(ROUND_NUM_COL)
                    # 调整冻结窗口
                    self.freeze_cell = (self.freeze_cell[0] - 1, self.freeze_cell[1])
                self.addTab(table, os.path.basename(folder_name))

        except Exception as e:  # pylint: disable=broad-except
            self.progress.cancel()
            if sys.platform == "win32":
                self.taskbar_progress.stop()
            if str(e) == "user canceled":
                QMessageBox.information(self, "提示", "已取消")
            else:
                tb = traceback.extract_tb(e.__traceback__)[-1]
                QMessageBox.critical(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)
            self.progress.reset()
            if sys.platform == "win32":
                self.taskbar_progress.resume()
                self.taskbar_progress.reset()
            for i in range(self.count()):
                self.removeTab(i)
            self.clear()
            del pin_map
            del path_dict
            gc.collect()
            return
        self.progress.reset()
        if sys.platform == "win32":
            self.taskbar_progress.resume()
            self.taskbar_progress.reset()
        # if self.rowCount() != 0 and self.columnCount() != 0:
        #     self.show()
        self.show()
        # 重新填充表格后重置只显示失效按钮
        if self.only_failed:
            self.parent.show_only_failed()
        del pin_map
        del path_dict
        gc.collect()

    def fill_table_headers(self, table: QTableWidget, pin_map, test_name_row, testsuite_col):
        test_name_col = 0
        # 确定列数
        for test_item in pin_map.items():
            if self.progress.wasCanceled():
                table.setRowCount(0)
                table.setColumnCount(0)
                table.clear()
                raise Exception("user canceled")
            # 循环测试项
            test_name, pin_dict = test_item

            # 上下限值和单位
            lower_bound = pin_dict.get("__lower_bound")
            upper_bound = pin_dict.get("__upper_bound")
            unit = pin_dict.get("__unit")

            # 表头
            temp_set = set()
            for pin_item in pin_dict.items():
                if pin_item[0] == "__upper_bound" or pin_item[0] == "__lower_bound" or pin_item[0] == "__unit":
                    continue
                temp_set.update(pin_item[1])
                table.insertColumn(table.columnCount())
            temp_list = list(temp_set)
            temp_list.sort()

            pin_name_col = 0
            if lower_bound is None:
                lower_bound = ""
            if upper_bound is None:
                upper_bound = ""
            unit = " (" + unit + ")"
            col_sum = testsuite_col + test_name_col + pin_name_col
            table.setItem(test_name_row, col_sum, self.get_table_item(test_name + unit))
            for pin_item in pin_dict.items():
                if pin_item[0] == "__upper_bound" or pin_item[0] == "__lower_bound" or pin_item[0] == "__unit":
                    continue
                col_sum = testsuite_col + test_name_col + pin_name_col
                table.setItem(test_name_row + 1, col_sum, self.get_table_item(pin_item[0] + unit))
                table.setItem(test_name_row + 2, col_sum, self.get_table_item(lower_bound))
                table.setItem(test_name_row + 3, col_sum, self.get_table_item(upper_bound))
                table.setItem(test_name_row + 4, col_sum, self.get_table_item(unit[2:-1]))
                pin_name_col += 1
            table.setSpan(test_name_row, testsuite_col + test_name_col, 1, pin_name_col)
            if pin_name_col > 10:
                table.item(test_name_row, testsuite_col + test_name_col).setTextAlignment(
                    Qt.AlignLeft | Qt.AlignVCenter)
            test_name_col += pin_name_col
        return test_name_col

    def fill_table_contents(
            self, table: QTableWidget, compare_test_parent_dict, test_parent_map, chip_row, test_parent_col,
            max_round_row, done):
        test_name_col = 0
        for test_item in test_parent_map.items():
            pin_name_col = 0
            # 循环test_name
            test_name, test_dict = test_item
            compare_test_dict = compare_test_parent_dict.get(test_name)
            if self.progress.wasCanceled():
                table.setRowCount(0)
                table.setColumnCount(0)
                table.clear()
                raise Exception("user canceled")

            lower_bound: Decimal = test_dict.get("__lower_bound")
            upper_bound: Decimal = test_dict.get("__upper_bound")
            for pin_name in test_dict.keys():
                # 循环pin_name
                round_row = 0
                if self.progress.wasCanceled():
                    table.setRowCount(0)
                    table.setColumnCount(0)
                    table.clear()
                    raise Exception("user canceled")
                if compare_test_dict is None:
                    # self.insertRow(self.rowCount())
                    continue
                if pin_name == "__lower_bound" or pin_name == "__upper_bound" or pin_name == "__unit":
                    continue
                compare_pin_values: list = compare_test_dict.get(pin_name)
                if not compare_pin_values:
                    continue
                exp_row_cnt = chip_row + len(compare_pin_values)
                if exp_row_cnt > table.rowCount():
                    table.setRowCount(exp_row_cnt)
                for pin_val in compare_pin_values:
                    if chip_row + round_row >= table.rowCount():
                        table.insertRow(table.rowCount())
                    table.setItem(chip_row + round_row, test_parent_col + test_name_col + pin_name_col,
                                  self.get_table_item(util.convert_decimal(pin_val), Qt.AlignRight | Qt.AlignVCenter))
                    if lower_bound and pin_val < lower_bound or upper_bound and pin_val > upper_bound:
                        if table.item(chip_row, CHIP_ID_COL) is None:
                            table.setItem(chip_row, CHIP_ID_COL, self.get_table_item(""))
                        table.item(chip_row, CHIP_ID_COL).setBackground(FAILED_COLOR)
                        table.item(chip_row + round_row, test_parent_col + test_name_col + pin_name_col) \
                            .setBackground(FAILED_COLOR)
                    done += 1
                    self.progress.setValue(done)
                    if sys.platform == "win32":
                        self.taskbar_progress.setValue(done)
                    round_row += 1
                pin_name_col += 1
                max_round_row = max(max_round_row, round_row)
            test_name_col += pin_name_col
        return test_name_col, max_round_row, done

    @staticmethod
    def get_table_item(text, alignment=Qt.AlignHCenter | Qt.AlignVCenter):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(alignment)
        return item

    def show_only_failed(self):
        self.only_failed = not self.only_failed
        if self.only_failed:
            for i in range(self.count()):
                begin_row = self.freeze_cell[1] - 1
                begin_col = self.freeze_cell[0] - 1
                self: QTabWidget
                table: QTableWidget = self.widget(i)
                # begin_row = table.rowSpan(0, 0)
                # begin_col = table.columnSpan(0, 0)
                end_row = table.rowCount()
                end_col = table.columnCount()
                for j in range(begin_row, end_row):
                    if table.item(j, CHIP_ID_COL)\
                            and table.item(j, CHIP_ID_COL).background().color().rgb() % RGB_WHITE == 0:
                        for k in range(table.rowSpan(j, CHIP_ID_COL)):
                            table.hideRow(j + k)
                for j in range(begin_col, end_col):
                    hide_col = True
                    for k in range(begin_row, end_row):
                        if table.isRowHidden(k):
                            continue
                        if table.item(k, j) and table.item(k, j).background().color().rgb() % RGB_WHITE != 0:
                            hide_col = False
                            break
                    if hide_col:
                        table.hideColumn(j)
        else:
            self: QTabWidget
            for i in range(self.count()):
                table: QTableWidget = self.widget(i)
                for j in range(table.rowCount()):
                    table.showRow(j)
                for k in range(table.columnCount()):
                    table.showColumn(k)

    def export_excel(self):
        filename = QFileDialog.getSaveFileName(self, "导出表格", filter="Excel Files (*.xlsx *.xls)")[0]
        if filename == "":
            return
        if self.progress is None:
            self.progress = QProgressDialog(self)
        self.progress.setWindowTitle("请稍等...")
        self.progress.setLabelText("正在导出")
        self.progress.setCancelButtonText("停止")
        self.progress.setMinimumDuration(100)
        self.progress.setFixedWidth(500)
        # 窗口是应用的模式窗口，阻塞所有其他应用窗口获得输入
        self.progress.setWindowModality(Qt.ApplicationModal)
        # 设置窗口标题只有关闭
        self.progress.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        try:
            if sys.platform == "win32":
                util.export_excel(self, filename, self.progress, self.parent.taskbar_progress)
            else:
                util.export_excel(self, filename, self.progress)
            return filename
        except PermissionError:
            QMessageBox.critical(self, "提示", "文件已被打开或占用")
        except Exception as e:  # pylint: disable=broad-except
            self.progress.cancel()
            if sys.platform == "win32":
                self.taskbar_progress.stop()
            if str(e) == "user canceled":
                QMessageBox.information(self, "提示", "已取消")
            else:
                tb = traceback.extract_tb(e.__traceback__)[-1]
                QMessageBox.critical(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)
            self.progress.reset()
            if sys.platform == "win32":
                self.taskbar_progress.resume()
                self.taskbar_progress.reset()
