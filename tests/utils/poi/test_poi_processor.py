#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试POI数据处理和统计模块
"""

import os
import tempfile
import unittest
import pandas as pd
import json
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.poi.poi_processor import (
    calculate_weighted_score,
    generate_score_report,
)


class TestPoiProcessor(unittest.TestCase):
    """测试POI数据处理和统计功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 创建测试POI数据
        self.test_poi_data = [
            {
                "住宅区ID": "B022A02HI1",
                "住宅区名称": "裕安小区",
                "POI类型": "010100",
                "POI大类": "餐饮服务",
                "POI中类": "中餐厅",
                "POI小类": "中餐馆",
                "POI名称": "测试餐厅1",
                "POI地址": "舜耕西路123号",
                "经度": "116.998316",
                "纬度": "32.631699",
                "距离(米)": "500",
                "默认权重": "0.8",
            },
            {
                "住宅区ID": "B022A02HI1",
                "住宅区名称": "裕安小区",
                "POI类型": "010200",
                "POI大类": "餐饮服务",
                "POI中类": "快餐厅",
                "POI小类": "快餐店",
                "POI名称": "测试餐厅2",
                "POI地址": "舜耕西路124号",
                "经度": "116.999316",
                "纬度": "32.632699",
                "距离(米)": "600",
                "默认权重": "0.7",
            },
            {
                "住宅区ID": "B022A02HI1",
                "住宅区名称": "裕安小区",
                "POI类型": "020100",
                "POI大类": "购物服务",
                "POI中类": "商场",
                "POI小类": "综合商场",
                "POI名称": "测试商场",
                "POI地址": "舜耕西路125号",
                "经度": "117.000316",
                "纬度": "32.633699",
                "距离(米)": "700",
                "默认权重": "0.6",
            },
        ]

        # 创建测试权重映射
        self.weight_map = {
            "010100": {
                "大类": "餐饮服务",
                "中类": "中餐厅",
                "小类": "中餐馆",
                "权重": 0.8,
            },
            "010200": {
                "大类": "餐饮服务",
                "中类": "快餐厅",
                "小类": "快餐店",
                "权重": 0.7,
            },
            "020100": {
                "大类": "购物服务",
                "中类": "商场",
                "小类": "综合商场",
                "权重": 0.6,
            },
        }

        # 创建测试POI文件
        self.poi_csv_file = os.path.join(self.test_dir, "test_poi.csv")
        self.poi_df = pd.DataFrame(self.test_poi_data)
        self.poi_df.to_csv(self.poi_csv_file, index=False, encoding="utf-8-sig")

        # 创建测试POI JSON文件
        self.poi_json_file = os.path.join(self.test_dir, "test_poi.json")
        with open(self.poi_json_file, "w", encoding="utf-8") as f:
            json.dump(self.test_poi_data, f, ensure_ascii=False, indent=2)

    def tearDown(self):
        """清理测试环境"""
        # 删除临时目录和文件
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_calculate_weighted_score_csv(self):
        """测试计算加权得分（CSV格式）"""
        # 测试计算加权得分
        total_score, poi_count, category_stats = calculate_weighted_score(
            self.poi_csv_file, self.weight_map
        )

        # 验证结果
        self.assertIsInstance(total_score, float)
        self.assertIsInstance(poi_count, int)
        self.assertIsInstance(category_stats, pd.DataFrame)

        # 验证得分计算
        expected_score = 0.8 + 0.7 + 0.6  # 所有POI的权重之和
        self.assertEqual(total_score, expected_score)

        # 验证POI数量
        self.assertEqual(poi_count, 3)

        # 验证分类统计
        self.assertGreater(len(category_stats), 0)

        # 验证包含所有层级
        types = set(category_stats["类型"].unique())
        self.assertIn("大类", types)
        self.assertIn("中类", types)
        self.assertIn("小类", types)

    def test_calculate_weighted_score_json(self):
        """测试计算加权得分（JSON格式）"""
        # 测试计算加权得分
        total_score, poi_count, category_stats = calculate_weighted_score(
            self.poi_json_file, self.weight_map
        )

        # 验证结果
        self.assertIsInstance(total_score, float)
        self.assertIsInstance(poi_count, int)
        self.assertIsInstance(category_stats, pd.DataFrame)

        # 验证得分计算
        expected_score = 0.8 + 0.7 + 0.6  # 所有POI的权重之和
        self.assertEqual(total_score, expected_score)

        # 验证POI数量
        self.assertEqual(poi_count, 3)

    def test_calculate_weighted_score_missing_columns(self):
        """测试计算加权得分（缺少列的情况）"""
        # 创建缺少列的测试数据
        incomplete_poi_data = [
            {"住宅区ID": "B022A02HI1", "POI类型": "010100"},
            {"住宅区ID": "B022A02HI1", "POI类型": "010200"},
        ]

        # 创建缺少列的测试文件
        incomplete_file = os.path.join(self.test_dir, "incomplete_poi.csv")
        incomplete_df = pd.DataFrame(incomplete_poi_data)
        incomplete_df.to_csv(incomplete_file, index=False, encoding="utf-8-sig")

        # 测试计算加权得分
        total_score, poi_count, category_stats = calculate_weighted_score(
            incomplete_file, self.weight_map
        )

        # 验证结果（应该能够处理缺失列）
        self.assertIsInstance(total_score, float)
        self.assertIsInstance(poi_count, int)
        self.assertIsInstance(category_stats, pd.DataFrame)

        # 验证POI数量
        self.assertEqual(poi_count, 2)

    def test_calculate_weighted_score_unsupported_format(self):
        """测试计算加权得分（不支持的文件格式）"""
        # 创建不支持的文件格式
        unsupported_file = os.path.join(self.test_dir, "unsupported_poi.txt")
        with open(unsupported_file, "w", encoding="utf-8") as f:
            f.write("This is a text file")

        # 测试计算加权得分，应该抛出ValueError
        with self.assertRaises(ValueError):
            calculate_weighted_score(unsupported_file, self.weight_map)

    def test_generate_score_report(self):
        """测试生成得分报告"""
        # 创建输出目录
        output_dir = os.path.join(self.test_dir, "output")
        residential_id = "B022A02HI1"

        # 测试生成得分报告
        total_score, poi_count = generate_score_report(
            self.poi_csv_file, self.weight_map, output_dir, residential_id
        )

        # 验证结果
        self.assertIsInstance(total_score, float)
        self.assertIsInstance(poi_count, int)

        # 验证输出目录是否创建
        self.assertTrue(os.path.exists(output_dir))

        # 验证得分文件是否创建
        score_file = os.path.join(output_dir, f"score_{residential_id}.csv")
        self.assertTrue(os.path.exists(score_file))

        # 验证统计文件是否创建
        stats_file = os.path.join(output_dir, f"stats_{residential_id}.csv")
        self.assertTrue(os.path.exists(stats_file))

        # 验证汇总文件是否创建
        summary_file = os.path.join(output_dir, f"summary_{residential_id}.json")
        self.assertTrue(os.path.exists(summary_file))

        # 验证得分文件内容
        score_df = pd.read_csv(score_file)
        self.assertEqual(len(score_df), 1)
        self.assertEqual(score_df.iloc[0]["住宅区ID"], residential_id)
        self.assertEqual(score_df.iloc[0]["POI总数"], poi_count)
        self.assertEqual(score_df.iloc[0]["加权得分"], total_score)

        # 验证汇总文件内容
        with open(summary_file, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
        self.assertEqual(summary_data["residential_id"], residential_id)
        self.assertEqual(summary_data["poi_count"], poi_count)
        self.assertEqual(summary_data["total_score"], total_score)


if __name__ == "__main__":
    unittest.main()
