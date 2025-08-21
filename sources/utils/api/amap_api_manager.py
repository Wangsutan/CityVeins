#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
高德地图API管理模块

该模块负责管理高德地图API的配置、状态检查和交互功能。
它提供了一套统一的接口，用于检查API状态、更新API密钥。
"""

import os
import webbrowser
from typing import Dict, Optional, Tuple, List, Any

# 导入项目配置
from config import DATA_DIR, KEY_FILE


class AMapAPIManager:
    """高德地图API管理器类"""

    def __init__(self):
        """初始化高德地图API管理器"""
        self.api_dir = os.path.join(DATA_DIR, "key")
        self.amap_key_file = KEY_FILE

        # 确保API目录存在
        os.makedirs(self.api_dir, exist_ok=True)

    def check_api(self) -> bool:
        """
        检查高德地图API是否存在

        Returns:
            bool: 如果API密钥存在且不为空则返回True，否则返回False
        """
        try:
            if os.path.exists(self.amap_key_file):
                with open(self.amap_key_file, "r", encoding="utf-8") as f:
                    key = f.read().strip()
                    return bool(key)
            return False
        except Exception:
            return False

    def update_key(self, key: str) -> bool:
        """
        更新高德地图API密钥

        Args:
            key (str): 新的高德地图API密钥

        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            with open(self.amap_key_file, "w", encoding="utf-8") as f:
                f.write(key.strip())
            return True
        except Exception:
            return False

    def get_key(self) -> str:
        """
        获取当前的高德地图API密钥

        Returns:
            str: 当前的高德地图API密钥，如果不存在则返回空字符串
        """
        try:
            if os.path.exists(self.amap_key_file):
                with open(self.amap_key_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return ""
        except Exception:
            return ""

    def open_api_website(self):
        """打开高德开放平台网站"""
        webbrowser.open("https://lbs.amap.com/")
