#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件处理模块
"""

import os
import tempfile
import unittest
import pandas as pd
import json
from unittest.mock import patch, mock_open
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.file.file_handler import (
    read_poi_file,
    save_poi_file,
    save_category_stats,
)


class TestFileHandler(unittest.TestCase):
    """测试文件处理功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 创建测试数据
        self.test_data = [
            {
                "住宅区ID": "B022A02HI1",
                "住宅区名称": "裕安小区",
                "POI类型": "010100",
                "POI大类": "餐饮服务",
                "POI中类": "中餐厅",
                "POI小类": "中餐馆",
                "POI名称": "测试餐厅",
                "POI地址": "舜耕西路123号",
                "经度": "116.998316",
                "纬度": "32.631699",
                "距离(米)": "500",
                "默认权重": "0.8",
            }
        ]

        # 创建测试DataFrame
        self.test_df = pd.DataFrame(self.test_data)

    def tearDown(self):
        """清理测试环境"""
        # 删除临时目录和文件
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_read_poi_file_csv(self):
        """测试读取CSV格式的POI文件"""
        # 创建测试CSV文件
        csv_file = os.path.join(self.test_dir, "test_poi.csv")
        self.test_df.to_csv(csv_file, index=False, encoding="utf-8-sig")

        # 测试读取CSV文件
        result_df = read_poi_file(csv_file)

        # 验证结果
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df.iloc[0]["住宅区ID"], "B022A02HI1")

    def test_read_poi_file_json(self):
        """测试读取JSON格式的POI文件"""
        # 创建测试JSON文件
        json_file = os.path.join(self.test_dir, "test_poi.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.test_data, f, ensure_ascii=False, indent=2)

        # 测试读取JSON文件
        result_df = read_poi_file(json_file)

        # 验证结果
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df.iloc[0]["住宅区ID"], "B022A02HI1")

    def test_read_poi_file_unsupported_format(self):
        """测试读取不支持的文件格式"""
        # 创建测试TXT文件
        txt_file = os.path.join(self.test_dir, "test_poi.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("This is a text file")

        # 测试读取不支持的格式，应该抛出ValueError
        with self.assertRaises(ValueError):
            read_poi_file(txt_file)

    def test_save_poi_file_csv(self):
        """测试保存CSV格式的POI文件"""
        # 创建输出CSV文件路径
        csv_file = os.path.join(self.test_dir, "output_poi.csv")

        # 测试保存CSV文件
        save_poi_file(self.test_df, csv_file)

        # 验证文件是否创建
        self.assertTrue(os.path.exists(csv_file))

        # 验证文件内容
        result_df = pd.read_csv(csv_file)
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df.iloc[0]["住宅区ID"], "B022A02HI1")

    def test_save_poi_file_json(self):
        """测试保存JSON格式的POI文件"""
        # 创建输出JSON文件路径
        json_file = os.path.join(self.test_dir, "output_poi.json")

        # 测试保存JSON文件
        save_poi_file(self.test_df, json_file)

        # 验证文件是否创建
        self.assertTrue(os.path.exists(json_file))

        # 验证文件内容
        with open(json_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["住宅区ID"], "B022A02HI1")

    def test_save_poi_file_unsupported_format(self):
        """测试保存不支持的文件格式"""
        # 创建输出TXT文件路径
        txt_file = os.path.join(self.test_dir, "output_poi.txt")

        # 测试保存不支持的格式，应该抛出ValueError
        with self.assertRaises(ValueError):
            save_poi_file(self.test_df, txt_file)

    def test_save_category_stats(self):
        """测试保存分类统计信息"""
        # 创建测试统计数据
        stats_data = pd.DataFrame(
            [
                {
                    "类型": "大类",
                    "名称": "餐饮服务",
                    "数量": 10,
                    "加权得分": 8.0,
                    "平均权重": 0.8,
                    "子类型数量": 3,
                },
                {
                    "类型": "中类",
                    "名称": "中餐厅",
                    "数量": 5,
                    "加权得分": 4.0,
                    "平均权重": 0.8,
                    "子类型数量": 2,
                },
            ]
        )

        # 创建输出目录
        output_dir = os.path.join(self.test_dir, "stats")
        residential_id = "B022A02HI1"

        # 测试保存分类统计信息
        save_category_stats(stats_data, output_dir, residential_id)

        # 验证CSV文件是否创建
        csv_file = os.path.join(output_dir, f"stats_{residential_id}.csv")
        self.assertTrue(os.path.exists(csv_file))

        # 验证JSON文件是否创建
        json_file = os.path.join(output_dir, f"stats_{residential_id}.json")
        self.assertTrue(os.path.exists(json_file))

        # 验证文件内容
        result_df = pd.read_csv(csv_file)
        self.assertEqual(len(result_df), 2)
        self.assertEqual(result_df.iloc[0]["名称"], "餐饮服务")

        with open(json_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        self.assertEqual(len(result_data), 2)
        self.assertEqual(result_data[0]["名称"], "餐饮服务")


if __name__ == "__main__":
    unittest.main()
