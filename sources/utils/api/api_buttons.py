#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API按钮模块

该模块提供了高德地图API的按钮组件，可以集成到主GUI界面中。
这个按钮用于检查API状态、更新API密钥等功能。
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QDialog, QGroupBox,
    QVBoxLayout, QTextEdit, QLineEdit, QFormLayout,
    QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# 修改导入路径，确保能正确找到AMapAPIManager
from .amap_api_manager import AMapAPIManager


class AMapButton(QPushButton):
    """高德地图API状态按钮"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_manager = AMapAPIManager()
        self.setText("高德API")
        self.setFixedSize(80, 30)
        self.setFont(QFont("Arial", 9))
        self.update_status()
        self.clicked.connect(self.show_dialog)

    def update_status(self):
        """更新按钮状态颜色"""
        if self.api_manager.check_api():
            self.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.setStyleSheet("background-color: #F44336; color: white;")

    def show_dialog(self):
        """显示高德API对话框"""
        dialog = AMapDialog(self.api_manager, self)
        dialog.exec_()
        self.update_status()


class AMapDialog(QDialog):
    """高德地图API设置对话框"""

    def __init__(self, api_manager: AMapAPIManager, parent=None):
        super().__init__(parent)
        self.api_manager = api_manager
        self.setWindowTitle("高德地图API设置")
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox("关于高德地图API")
        info_layout = QVBoxLayout(info_group)
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
            <p>该程序依赖高德地图API来获取POI（兴趣点）数据。</p>
            <ol>
                <li>访问高德开放平台网站</li>
                <li>注册并登录账号</li>
                <li>创建应用并选择Web服务API</li>
                <li>获取Key值并填入下方</li>
            </ol>
        """)
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        key_group = QGroupBox("API密钥设置")
        key_layout = QFormLayout(key_group)
        self.key_input = QLineEdit()
        self.key_input.setText(self.api_manager.get_key())
        self.key_input.setPlaceholderText("请输入高德地图API密钥")
        key_layout.addRow("API密钥:", self.key_input)
        layout.addWidget(key_group)

        button_layout = QHBoxLayout()
        visit_button = QPushButton("访问高德开放平台")
        visit_button.clicked.connect(self.api_manager.open_api_website)
        button_layout.addWidget(visit_button)

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self.save_key)
        dialog_buttons.rejected.connect(self.reject)
        button_layout.addWidget(dialog_buttons)

        layout.addLayout(button_layout)

    def save_key(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "警告", "API密钥不能为空")
            return
        if self.api_manager.update_key(key):
            QMessageBox.information(self, "成功", "API密钥已更新")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "API密钥更新失败")


class APIButtonsWidget(QWidget):
    """仅包含高德API按钮的组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.amap_button = AMapButton(self)
        layout.addWidget(self.amap_button)
        layout.addStretch()
