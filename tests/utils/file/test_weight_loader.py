#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试权重配置加载模块
"""

import os
import tempfile
import unittest
import pandas as pd
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.file.weight_loader import load_weight_config


class TestWeightLoader(unittest.TestCase):
    """测试权重配置加载功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 创建测试权重配置文件
        self.weight_file = os.path.join(self.test_dir, "test_weights.csv")
        test_weights = [
            {
                "NEW_TYPE": "010100",
                "大类": "餐饮服务",
                "中类": "中餐厅",
                "小类": "中餐馆",
                "": 0.8,
                "客制化权重": 0.9,
            },
            {
                "NEW_TYPE": "010200",
                "大类": "餐饮服务",
                "中类": "快餐厅",
                "小类": "快餐店",
                "": 0.7,
                "客制化权重": "",
            },
            {
                "NEW_TYPE": "020100",
                "大类": "购物服务",
                "中类": "商场",
                "小类": "综合商场",
                "": 0.6,
                "客制化权重": 0.5,
            },
            {
                "NEW_TYPE": "020200",
                "大类": "购物服务",
                "中类": "超市",
                "小类": "便利店",
                "": 0.5,
                "客制化权重": "",
            },
        ]
        self.weight_df = pd.DataFrame(test_weights)
        self.weight_df.to_csv(self.weight_file, index=False, encoding="utf-8-sig")

    def tearDown(self):
        """清理测试环境"""
        # 删除临时目录和文件
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_weight_config_success(self):
        """测试成功加载权重配置"""
        # 测试加载权重配置
        weight_map = load_weight_config(self.weight_file)

        # 验证结果
        self.assertIsInstance(weight_map, dict)
        self.assertEqual(
            len(weight_map), 8
        )  # 每个POI类型有两个条目（主条目和_weight后缀条目）

        # 验证客制化权重优先
        self.assertEqual(weight_map["010100"]["权重"], 0.9)  # 使用客制化权重
        self.assertEqual(weight_map["010200"]["权重"], 0.7)  # 使用权重评分
        self.assertEqual(weight_map["020100"]["权重"], 0.5)  # 使用客制化权重
        self.assertEqual(weight_map["020200"]["权重"], 0.5)  # 使用权重评分

        # 验证_weight后缀条目
        self.assertEqual(weight_map["010100_weight"], 0.9)
        self.assertEqual(weight_map["010200_weight"], 0.7)
        self.assertEqual(weight_map["020100_weight"], 0.5)
        self.assertEqual(weight_map["020200_weight"], 0.5)

    def test_load_weight_config_no_custom_weights(self):
        """测试加载没有客制化权重的配置"""
        # 创建没有客制化权重的测试文件
        no_custom_file = os.path.join(self.test_dir, "no_custom_weights.csv")
        no_custom_weights = [
            {
                "NEW_TYPE": "010100",
                "大类": "餐饮服务",
                "中类": "中餐厅",
                "小类": "中餐馆",
                "": 0.8,
                "客制化权重": "",
            },
            {
                "NEW_TYPE": "010200",
                "大类": "餐饮服务",
                "中类": "快餐厅",
                "小类": "快餐店",
                "": 0.7,
                "客制化权重": "",
            },
        ]
        no_custom_df = pd.DataFrame(no_custom_weights)
        no_custom_df.to_csv(no_custom_file, index=False, encoding="utf-8-sig")

        # 测试加载权重配置
        weight_map = load_weight_config(no_custom_file)

        # 验证结果（应该全部使用权重评分）
        self.assertEqual(weight_map["010100"]["权重"], 0.8)
        self.assertEqual(weight_map["010200"]["权重"], 0.7)
        self.assertEqual(weight_map["010100_weight"], 0.8)
        self.assertEqual(weight_map["010200_weight"], 0.7)

    def test_load_weight_config_empty_file(self):
        """测试加载空的权重配置文件"""
        # 创建空的权重配置文件
        empty_file = os.path.join(self.test_dir, "empty_weights.csv")
        empty_df = pd.DataFrame(
            columns=["NEW_TYPE", "大类", "中类", "小类", "", "客制化权重"]
        )
        empty_df.to_csv(empty_file, index=False, encoding="utf-8-sig")

        # 测试加载空文件
        weight_map = load_weight_config(empty_file)

        # 验证结果（应该返回空字典）
        self.assertEqual(weight_map, {})

    def test_load_weight_config_missing_columns(self):
        """测试加载缺少必要列的权重配置文件"""
        # 创建缺少必要列的测试文件
        missing_cols_file = os.path.join(self.test_dir, "missing_cols_weights.csv")
        missing_cols_weights = [
            {
                "NEW_TYPE": "010100",
                "大类": "餐饮服务",
                "中类": "中餐厅",
                "": 0.8,
            }
        ]
        missing_cols_df = pd.DataFrame(missing_cols_weights)
        missing_cols_df.to_csv(missing_cols_file, index=False, encoding="utf-8-sig")

        # 测试加载缺少列的文件（应该能够处理，使用默认值填充缺失列）
        weight_map = load_weight_config(missing_cols_file)

        # 验证结果
        self.assertEqual(weight_map["010100"]["权重"], 0.8)
        self.assertEqual(weight_map["010100_weight"], 0.8)


if __name__ == "__main__":
    unittest.main()
