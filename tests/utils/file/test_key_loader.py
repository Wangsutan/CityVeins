#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API密钥加载模块
"""

import sys, os
import tempfile
import unittest
from unittest.mock import patch, mock_open

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.file.key_loader import load_key

# 尝试导入config，如果失败则使用默认值
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import KEY_FILE
except ImportError:
    # 如果无法导入config，使用默认路径
    ROOT_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    KEY_FILE = os.path.join(ROOT_DIR, "data", "key", "key.txt")


class TestKeyLoader(unittest.TestCase):
    """测试API密钥加载功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 创建测试密钥文件
        self.key_file = os.path.join(self.test_dir, "test_key.txt")
        with open(self.key_file, "w", encoding="utf-8") as f:
            f.write("test_api_key_12345")

    def tearDown(self):
        """清理测试环境"""
        # 删除临时目录和文件
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_key_success(self):
        """测试成功加载API密钥"""
        # 测试加载密钥
        api_key = load_key(self.key_file)

        # 验证结果
        self.assertEqual(api_key, "test_api_key_12345")

    def test_load_key_file_not_exist(self):
        """测试加载不存在的密钥文件"""
        # 创建不存在的文件路径
        non_exist_file = os.path.join(self.test_dir, "non_exist_key.txt")

        # 测试加载不存在的文件，应该抛出FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            load_key(non_exist_file)

    def test_load_key_empty_file(self):
        """测试加载空的密钥文件"""
        # 创建空的密钥文件
        empty_key_file = os.path.join(self.test_dir, "empty_key.txt")
        with open(empty_key_file, "w", encoding="utf-8") as f:
            f.write("")

        # 测试加载空文件，应该抛出ValueError
        with self.assertRaises(ValueError):
            load_key(empty_key_file)

    def test_load_key_with_whitespace(self):
        """测试加载包含空白字符的密钥文件"""
        # 创建包含空白字符的密钥文件
        whitespace_key_file = os.path.join(self.test_dir, "whitespace_key.txt")
        with open(whitespace_key_file, "w", encoding="utf-8") as f:
            f.write("  test_api_key_with_whitespace  ")

        # 测试加载包含空白字符的密钥文件
        api_key = load_key(whitespace_key_file)

        # 验证结果（应该去除了空白字符）
        self.assertEqual(api_key, "test_api_key_with_whitespace")

    def test_load_key_default_path(self):
        """测试使用默认路径加载密钥文件"""
        # 使用mock模拟默认路径的文件存在
        with patch("builtins.open", mock_open(read_data="default_test_key")):
            # 测试使用默认路径加载密钥
            api_key = load_key(KEY_FILE)

            # 验证结果
            self.assertEqual(api_key, "default_test_key")


if __name__ == "__main__":
    unittest.main()
