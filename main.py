#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : main.py
@Time   : 2026/05/05
@Desc   : 启动文件
"""

import ctypes
import sys
from PyQt5.QtWidgets import QApplication, QStyleFactory

from app import DatalogExtractor, resource  # pylint: disable=unused-import


if __name__ == "__main__":
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("datalog_extractor")
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    app = QApplication(sys.argv)
    __main_window = DatalogExtractor()
    __main_window.showMaximized()
    sys.exit(app.exec_())
