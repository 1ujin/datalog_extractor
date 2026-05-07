#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/datalog_extractor.py
@Time   : 2025/03/07
@Desc   : Datalog数据提取工具主窗口
"""

import ctypes
import gc
import os
import sys
import traceback

from app import __version__
from . import table_tab
from .test_name_tree import TestNameTree
from .file_list_box import FileListBox
from .movable_push_button import MovablePushButton
from .test_pin_table import TestPinTable

from PyQt5.QtCore import QSize, QRect, QPropertyAnimation, QSequentialAnimationGroup
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, \
    QMessageBox, QSizePolicy, QStyleFactory, QGridLayout, QSpacerItem, QSplitter, QTableWidget

if sys.platform == "win32":
    from PyQt5.QtWinExtras import QWinTaskbarButton


class DatalogExtractor(QMainWindow):
    """docstring for TestNameTree
    测试项树状列表
    """

    def __init__(self, parent=None):
        super(DatalogExtractor, self).__init__(parent)
        self.parent = parent
        # 剪贴板
        self.clipboard = QApplication.clipboard()
        # self.resize(908, 600)
        # self.setMinimumSize(908, 600)
        self.setWindowTitle("Datalog数据提取工具 v" + __version__)
        self.logo = QIcon(QPixmap(":/images/CESI_logo.png"))
        self.setWindowIcon(self.logo)
        self.setStyleSheet("\
            QPushButton { font-family: \"微软雅黑\"; } \
            QLabel { height: 28px;  font-family: \"微软雅黑\" } \
            QToolBoxButton { min-width: 150px; min-height: 30px; font-size: 28 } \
            QToolBox::tab { height: 28px; font-family: \"微软雅黑\"; font-size: 28 } \
            QToolBox * { margin: 0px } \
            QToolBar#right_bar { border: none } \
            QToolBar#right_bar QPushButton { width: auto; background-color: green; font-size: 25px } \
            QGroupBox { font-family: \"微软雅黑\" } \
            QListWidget { font-family: \"微软雅黑\"; font-size: 18px; } \
            QCheckBox { height: 28px; font-family: \"微软雅黑\"; margin-left: 10px; } \
            QPlainTextEdit { font-family: \"微软雅黑\"; font-size: 18px; }")
        self.taskbar_button = None
        self.taskbar_progress = None
        splitter = QSplitter(self)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter { margin: 11px }")

        self.tab = QTabWidget(splitter)
        self.test_name_tree = TestNameTree(self.tab)
        self.test_name_tree.signal_has_checked.connect(self.switch_compare_button)
        self.tab.setStyleSheet("QTabWidget:pane { padding: 0px; }")
        self.tab.setTabPosition(QTabWidget.West)
        self.tab.addTab(self.test_name_tree, "导入测试项")
        # self.text_edit = QPlainTextEdit(self)
        # self.text_edit.textChanged.connect(self.textChangedHandle)
        # self.text_edit.setPlaceholderText("请输入要对比的测试项名称，以逗号隔开，例：\n测试项A Pin1，测试项A Pin2，测试项B Pin3")
        # self.text_edit.setFont(QFont("微软雅黑", 10))
        # self.tab.addTab(self.text_edit, "手动填写测试项")
        self.test_pin_table = TestPinTable(self.tab)
        self.test_pin_table.table.cellChanged.connect(self.test_pin_table_changed_handle)
        # self.tab.addTab(self.test_pin_table, "手动填写测试项")
        self.tab.currentChanged.connect(lambda _: self.switch_compare_button())

        self.file_list_before_aging = FileListBox(self)
        self.file_list_before_aging.signal_row_count.connect(self.switch_compare_button)
        # self.file_list_after_aging = FileListBox(self)
        # self.file_list_after_aging.Signal_Row_Count.connect(self.switch_compare_button)

        self.compare_btn = MovablePushButton(self)
        self.compare_btn.setToolTip("对比并展示表格")
        self.compare_btn.setIconSize(QSize(32, 32))
        self.compare_btn.setIcon(QIcon(":/images/data-extract.png"))
        self.compare_btn.setStyleSheet("\
            QPushButton { \
                border-radius: 35px; \
                width: 70px; \
                height: 70px; \
                background-color: LimeGreen; \
            } \
            QPushButton:enabled:hover { \
                background-color: lightgreen; \
            } \
            QPushButton:enabled:pressed { \
                background-color: green; \
            }")
        self.compare_btn.clicked.connect(self.compare_datalog)
        self.compare_btn.hide()

        self.excel_btn = MovablePushButton(self)
        self.excel_btn.setToolTip("导出并打开Excel文件")
        self.excel_btn.setIconSize(QSize(32, 32))
        self.excel_btn.setIcon(QIcon(":/images/export-excel2.png"))
        self.excel_btn.setStyleSheet("\
            QPushButton { \
                border-radius: 35px; \
                width: 70px; \
                height: 70px; \
                background-color: LimeGreen; \
            } \
            QPushButton:enabled:hover { \
                background-color: lightgreen; \
            } \
            QPushButton:enabled:pressed { \
                background-color: green; \
            }")
        self.excel_btn.clicked.connect(self.export_and_open_excel)
        self.excel_btn.hide()

        self.geometry_animation = QPropertyAnimation(self.compare_btn, b"geometry")
        self.geometry_animation.setDuration(300)
        self.visible_animation = QPropertyAnimation(self.compare_btn, b"visible")
        self.visible_animation.setDuration(1)
        self.visible_animation.setStartValue(True)
        self.visible_animation.setEndValue(False)

        right = QWidget(splitter)
        self.right_layout = QGridLayout(right)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.addWidget(self.file_list_before_aging, 0, 0, 9, 16)
        # self.right_layout.addWidget(self.file_list_after_aging, 0, 8, 9, 8)

        table_btn_layout = QHBoxLayout()
        back_btn = QPushButton("返回")
        back_btn.clicked.connect(self.back_to_file_list)
        self.only_failed_btn = QPushButton("只显示失效", self)
        self.only_failed_btn.clicked.connect(self.show_only_failed)
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self.export_and_open_excel)
        table_btn_layout.addWidget(back_btn)
        table_btn_layout.addWidget(self.only_failed_btn)
        table_btn_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        table_btn_layout.addWidget(export_btn)

        self.table_layout_widget = QWidget(splitter)
        table_layout = QVBoxLayout(self.table_layout_widget)
        table_layout.setContentsMargins(12, 12, 0, 0)
        table_layout.addLayout(table_btn_layout)
        self.table = table_tab.TableTab(self)
        self.table.hide()
        table_layout.addWidget(self.table)
        self.right_layout.addWidget(self.table_layout_widget, 0, 0, 9, 16)
        self.table_layout_widget.hide()

        splitter.addWidget(self.tab)
        splitter.setStretchFactor(0, 0)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)
        self.animation_group = QSequentialAnimationGroup(self)

    def showEvent(self, event):  # pylint: disable=unused-argument,invalid-name
        self.taskbar_progress = None
        if sys.platform == "win32":
            self.taskbar_button = QWinTaskbarButton(self)
            self.taskbar_progress = self.taskbar_button.progress()
            self.taskbar_progress.show()
            self.taskbar_button.setWindow(self.windowHandle())

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        if self.compare_btn.isVisible():
            self.compare_btn.setGeometry(QRect(self.geometry().width() - 150, self.geometry().height() - 150, 70, 70))
        if self.excel_btn.isVisible():
            self.excel_btn.setGeometry(QRect(self.geometry().width() - 150, self.geometry().height() - 150, 70, 70))
        super(DatalogExtractor, self).resizeEvent(event)

    def switch_compare_button(self, count=None):
        if self.table_layout_widget.isVisible():
            return

        if count == 0 or not self.comparable():
            if self.compare_btn.geometry().y() <= self.geometry().height():
                self.geometry_animation.setStartValue(self.compare_btn.geometry())
                self.geometry_animation.setEndValue(
                    QRect(self.compare_btn.geometry().x(), self.geometry().height() + 10, 70, 70))

                self.animation_group.addAnimation(self.geometry_animation)
                self.animation_group.addAnimation(self.visible_animation)
                self.animation_group.start()

        elif self.compare_btn.geometry().y() > self.geometry().height() or not self.compare_btn.isVisible():
            self.compare_btn.show()
            self.geometry_animation.setStartValue(
                QRect(self.geometry().width() - 150, self.geometry().height(), 70, 70))
            self.geometry_animation.setEndValue(
                QRect(self.geometry().width() - 150, self.geometry().height() - 150, 70, 70))
            self.geometry_animation.start()

    def comparable(self):
        if self.get_begin_regex() is None or self.get_regex() is None:
            return False
        if self.file_list_before_aging.folder_list.count() + self.file_list_before_aging.file_list.count() == 0:
            return False
        if self.tab.currentIndex() == 0 and not self.test_name_tree.is_any_selected():
            return False
        if self.tab.currentIndex() == 1 and len(self.test_pin_table.get_pin_map()) == 0:
            return False
        if self.tab.currentIndex() > 1:
            return False
        return True

    def compare_datalog(self):
        try:
            compare_reply = None
            has_result = False
            for i in range(self.table.count()):
                has_result = False
                table_ = self.table.widget(i)
                if isinstance(table_, QTableWidget):
                    has_result = has_result or table_.rowCount() != 0
            if has_result:
                compare_msg_box = QMessageBox(QMessageBox.Question, "查看对比结果", "是否重新对比并生成结果？")
                compare_msg_box.setWindowIcon(self.logo)
                compare_msg_box.addButton("重新生成", QMessageBox.YesRole)
                compare_msg_box.addButton("显示上次结果", QMessageBox.NoRole)
                quit_cancel_btn = compare_msg_box.addButton("取消", QMessageBox.RejectRole)
                compare_msg_box.setDefaultButton(quit_cancel_btn)
                compare_reply = compare_msg_box.exec()

            if compare_reply == 2:
                return

            if not has_result or compare_reply == 0:
                if has_result and compare_reply == 0:
                    # for i in range(self.table.count()):
                    #     self.table.widget(i) is None
                    self.table.clear()
                gc.collect()
                if self.tab.currentIndex() == 0:
                    pin_map = self.get_checked_pin_map()
                elif self.tab.currentIndex() == 1:
                    pin_map = self.test_pin_table.get_pin_map()
                else:
                    raise Exception("error tab")
                before_aging = self.file_list_before_aging.get_path_ordered_dict()
                # after_aging = self.file_list_after_aging.getPathList()
                # self.table.fillTable(before_aging, after_aging, pin_map, self.getRegex(), self.getBeginRegex())
                self.table.fill_table(before_aging, pin_map, self.get_regex(), self.get_begin_regex())

            for i in range(self.table.count()):
                table_ = self.table.widget(i)
                if isinstance(table_, QTableWidget) and table_.rowCount() != 0:
                    self.switch_to_table()
                    break
        except Exception as e:  # pylint: disable=broad-except
            tb = traceback.extract_tb(e.__traceback__)[-1]
            QMessageBox.warning(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)

    def switch_to_table(self):
        self.compare_btn.hide()
        self.file_list_before_aging.hide()
        # self.file_list_after_aging.hide()
        self.table_layout_widget.show()
        self.excel_btn.setGeometry(self.geometry().width() - 150, self.geometry().height() - 150, 70, 70)
        self.excel_btn.show()

    def back_to_file_list(self):
        self.excel_btn.hide()
        self.table_layout_widget.hide()
        self.file_list_before_aging.show()
        # self.file_list_after_aging.show()
        if self.comparable():
            self.compare_btn.setGeometry(QRect(self.geometry().width() - 150, self.geometry().height() - 150, 70, 70))
            self.compare_btn.show()

    def test_pin_table_changed_handle(self):
        try:
            self.switch_compare_button()
        except Exception as e:  # pylint: disable=broad-except
            tb = traceback.extract_tb(e.__traceback__)[-1]
            QMessageBox.warning(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)

    def get_pin_map(self):
        if self.test_name_tree is None:
            return None
        return self.test_name_tree.pin_map

    def get_checked_pin_map(self):
        if self.test_name_tree is None:
            return None
        return self.test_name_tree.get_checked_pin_map()

    def get_regex(self):
        if self.tab.currentIndex() == 0:
            return self.test_name_tree.regex
        elif self.tab.currentIndex() == 1:
            return self.test_pin_table.regex
        else:
            return None

    def get_begin_regex(self):
        if self.tab.currentIndex() == 0:
            return self.test_name_tree.begin_regex
        elif self.tab.currentIndex() == 1:
            return self.test_pin_table.begin_regex
        else:
            return None

    def show_only_failed(self):
        if self.only_failed_btn.text() == "只显示失效":
            self.only_failed_btn.setText("全部显示")
        elif self.only_failed_btn.text() == "全部显示":
            self.only_failed_btn.setText("只显示失效")
        self.table.show_only_failed()

    def export_excel(self):
        try:
            return self.table.export_excel()
        except Exception as e:  # pylint: disable=broad-except
            if str(e) == "user canceled":
                QMessageBox.information(self, "提示", "已取消")
            else:
                tb = traceback.extract_tb(e.__traceback__)[-1]
                QMessageBox.critical(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)

    def export_and_open_excel(self):
        try:
            filename = self.export_excel()
            if filename and os.path.exists(filename):
                open_msg_box = QMessageBox(QMessageBox.Question, "导出成功", "是否打开导出文件？")
                open_msg_box.setWindowIcon(self.logo)
                open_msg_box.addButton("打开", QMessageBox.YesRole)
                open_no_btn = open_msg_box.addButton("取消", QMessageBox.NoRole)
                open_msg_box.setDefaultButton(open_no_btn)
                open_reply = open_msg_box.exec()
                if open_reply == 0:
                    if sys.platform == "win32":
                        os.startfile(filename)
                    elif sys.platform == "linux":
                        os.system("xdg-open " + filename)
        except Exception as e:  # pylint: disable=broad-except
            if str(e) == "user canceled":
                QMessageBox.information(self, "提示", "已取消")
            else:
                tb = traceback.extract_tb(e.__traceback__)[-1]
                QMessageBox.critical(self, "提示", "失败\n" + str(e) + "\n" + str(tb)[19:-1] + "\n" + tb.line)

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """ 重写关闭事件 """
        # 退出消息窗，默认取消
        quit_msg_box = QMessageBox(QMessageBox.Question, "退出程序", "确认退出?")
        quit_msg_box.setWindowIcon(self.logo)
        quit_msg_box.addButton("退出(&Y)", QMessageBox.YesRole)
        quit_no_btn = quit_msg_box.addButton("取消(&N)", QMessageBox.NoRole)
        quit_msg_box.setDefaultButton(quit_no_btn)
        quit_reply = int(quit_msg_box.exec())
        if quit_reply:
            event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("datalog_extractor")
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    app = QApplication(sys.argv)
    __main_window = DatalogExtractor()
    __main_window.showMaximized()
    sys.exit(app.exec_())
