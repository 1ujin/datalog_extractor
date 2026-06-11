#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/__init__.py
@Time   : 2026/05/05
@Desc   : 启动文件
"""

# 1. 定义包的元数据
__version__ = "1.3.4"
__author__ = "Lu Jin"

# 2. 定义公共 API，这是最关键的部分
# 通过这种方式，外部代码可以简洁地导入核心组件
# 例如：from app import MainWindow, AppController
from .datalog_extractor import DatalogExtractor

# 3. 控制 'from app import *' 的行为
# 明确指定哪些内容会被通配符导入，避免命名空间污染
__all__ = ["DatalogExtractor", "__version__"]

# 4. 包的初始化逻辑（可选）
# 例如，在应用启动时进行一些全局配置
# print(f"正在初始化 MyApp 版本 {__version__}...")
