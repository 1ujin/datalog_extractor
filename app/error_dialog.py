#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/error_dialog.py
@Time   : 2023/05/24
@Desc   : 错误列表对话框
"""

import os
import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, \
    QAbstractItemView, QSpacerItem, QSizePolicy, QMenu, QAction, QDialog
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt, QPoint


class ErrorDialog(QDialog):
    """docstring for ErrorDialog"""

    def __init__(self, parent=None):
        super(ErrorDialog, self).__init__()
        self.parent = parent
        self.clipboard = QApplication.clipboard()
        # 设置阻塞整个应用程序
        # self.setWindowModality(Qt.ApplicationModal)
        # 设置窗口只有关闭按键
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setWindowTitle("错误")
        self.setStyleSheet("\
            QLabel { min-width: 70px;  font-family: \"微软雅黑\"; font-size: 18px; } \
            QPushButton { font-family: \"微软雅黑\"; max-width: 50px; } \
            QListWidget { font-family: \"微软雅黑\"; font-size: 18px; }")

        self.id_lbl = QLabel("文件名错误", self)
        self.id_error_list = QListWidget(self)
        self.id_error_list.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.id_error_list.itemDoubleClicked.connect(lambda item: self.open_path(item.text()))
        self.id_error_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.id_error_list.customContextMenuRequested[QPoint].connect(self.list_context_menu_event)

        self.duplicate_lbl = QLabel("重复错误", self)
        self.duplicate_error_list = QListWidget(self)
        self.duplicate_error_list.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.duplicate_error_list.itemDoubleClicked.connect(lambda item: self.open_path(item.text()))
        self.duplicate_error_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.duplicate_error_list.customContextMenuRequested[QPoint].connect(self.list_context_menu_event)

        self.temperature_lbl = QLabel("温度错误", self)
        self.temperature_error_list = QListWidget(self)
        self.temperature_error_list.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.temperature_error_list.itemDoubleClicked.connect(lambda item: self.open_path(item.text()))
        self.temperature_error_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.temperature_error_list.customContextMenuRequested[QPoint].connect(self.list_context_menu_event)

        accept_btn = QPushButton("继续", self)
        accept_btn.clicked.connect(self.accept)
        reject_btn = QPushButton("放弃", self)
        reject_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        btn_layout.addWidget(accept_btn)
        btn_layout.addWidget(reject_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.id_lbl)
        layout.addWidget(self.id_error_list)
        layout.addWidget(self.duplicate_lbl)
        layout.addWidget(self.duplicate_error_list)
        layout.addWidget(self.temperature_lbl)
        layout.addWidget(self.temperature_error_list)
        layout.addLayout(btn_layout)

    def fill_id_error_list(self, id_error):
        for path in id_error:
            QListWidgetItem(path, self.id_error_list)
        if self.id_error_list.count() == 0:
            self.id_lbl.hide()
            self.id_error_list.hide()

    def fill_duplicate_error_list(self, duplicate_error):
        for path in duplicate_error:
            QListWidgetItem(path, self.duplicate_error_list)
        if self.duplicate_error_list.count() == 0:
            self.duplicate_lbl.hide()
            self.duplicate_error_list.hide()

    def fill_temperature_error_list(self, temperature_error):
        for path in temperature_error:
            QListWidgetItem(path, self.temperature_error_list)
        if self.temperature_error_list.count() == 0:
            self.temperature_lbl.hide()
            self.temperature_error_list.hide()

    @staticmethod
    def open_path(path):
        if os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "linux":
                os.system("xdg-open " + path)

    def list_context_menu_event(self, pos):
        sender = self.sender()
        if not isinstance(sender, QListWidget):
            return
        hit_index = sender.indexAt(pos).row()
        if hit_index > -1:
            path = sender.currentItem().text()
            menu = QMenu(sender)
            open_file_action = QAction("打开", menu)
            open_file_action.triggered.connect(lambda: self.open_path(path))
            menu.addAction(open_file_action)
            open_folder_action = QAction("打开所在文件夹", menu)
            open_folder_action.triggered.connect(lambda: self.open_path(os.path.split(path)[0]))
            menu.addAction(open_folder_action)
            copy_action = QAction("复制路径", menu)
            copy_action.triggered.connect(lambda: self.clipboard.setText(path))
            menu.addAction(copy_action)
            menu.exec_(QCursor.pos())
