#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试POI权重过滤模块
"""

import os
import tempfile
import unittest
import pandas as pd
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.poi.poi_filter import filter_poi_types, get_poi_type_stats


class TestPoiFilter(unittest.TestCase):
    """测试POI权重过滤功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()

        # 创建测试POI类型文件
        self.poi_types_file = os.path.join(self.test_dir, "test_poi_types.csv")
        test_poi_types = [
            {
                "POI类型": "010100",
                "大类": "餐饮服务",
                "中类": "中餐厅",
                "小类": "中餐馆",
                "权重": 0.8,
            },
            {
                "POI类型": "010200",
                "大类": "餐饮服务",
                "中类": "快餐厅",
                "小类": "快餐店",
                "权重": 0.7,
            },
            {
                "POI类型": "020100",
                "大类": "购物服务",
                "中类": "商场",
                "小类": "综合商场",
                "权重": 0.6,
            },
            {
                "POI类型": "020200",
                "大类": "购物服务",
                "中类": "超市",
                "小类": "便利店",
                "权重": 0.5,
            },
            {
                "POI类型": "030100",
                "大类": "汽车服务",
                "中类": "汽车维修",
                "小类": "汽车保养",
                "权重": 0.7,
            },
            {
                "POI类型": "030200",
                "大类": "汽车服务",
                "中类": "汽车销售",
                "小类": "4S店",
                "权重": 0.6,
            },
            {
                "POI类型": "040100",
                "大类": "生活服务",
                "中类": "邮局",
                "小类": "邮政支局",
                "权重": 0.5,
            },
            {
                "POI类型": "040200",
                "大类": "生活服务",
                "中类": "物流速递",
                "小类": "快递点",
                "权重": 0.4,
            },
            {
                "POI类型": "040300",
                "大类": "生活服务",
                "中类": "家政服务",
                "小类": "家政公司",
                "权重": 0.3,
            },
            {
                "POI类型": "050100",
                "大类": "住宿服务",
                "中类": "酒店",
                "小类": "星级酒店",
                "权重": 0.6,
            },
            {
                "POI类型": "050200",
                "大类": "住宿服务",
                "中类": "宾馆旅馆",
                "小类": "经济型酒店",
                "权重": 0.5,
            },
        ]
        self.poi_types_df = pd.DataFrame(test_poi_types)
        self.poi_types_df.to_csv(self.poi_types_file, index=False, encoding="utf-8-sig")

    def tearDown(self):
        """清理测试环境"""
        # 删除临时目录和文件
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_filter_poi_types_with_filter(self):
        """测试过滤POI类型（启用过滤）"""
        # 测试过滤POI类型
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            self.poi_types_file, filter_low_weight_poi=True, poi_weight_threshold=0.4
        )

        # 验证结果
        self.assertIsInstance(filtered_types, list)
        self.assertIsInstance(kept_categories, set)
        self.assertIsInstance(type_mapping, dict)

        # 验证过滤结果
        # 餐饮服务和购物服务应该被保留（权重较高）
        self.assertIn("餐饮服务", kept_categories)
        self.assertIn("购物服务", kept_categories)

        # 汽车服务、生活服务和住宿服务应该被过滤掉（权重被调低）
        self.assertNotIn("汽车服务", kept_categories)
        self.assertNotIn("生活服务", kept_categories)
        self.assertNotIn("住宿服务", kept_categories)

        # 验证类型映射
        for type_code in filtered_types:
            self.assertIn(type_code, type_mapping)
            self.assertIn("大类", type_mapping[type_code])
            self.assertIn("中类", type_mapping[type_code])
            self.assertIn("小类", type_mapping[type_code])
            self.assertIn("权重", type_mapping[type_code])

    def test_filter_poi_types_without_filter(self):
        """测试过滤POI类型（禁用过滤）"""
        # 测试不过滤POI类型
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            self.poi_types_file, filter_low_weight_poi=False, poi_weight_threshold=0.4
        )

        # 验证结果
        self.assertIsInstance(filtered_types, list)
        self.assertIsInstance(kept_categories, set)
        self.assertIsInstance(type_mapping, dict)

        # 验证所有大类都被保留
        expected_categories = {
            "餐饮服务",
            "购物服务",
            "汽车服务",
            "生活服务",
            "住宿服务",
        }
        self.assertEqual(kept_categories, expected_categories)

    def test_filter_poi_types_high_threshold(self):
        """测试使用高阈值过滤POI类型"""
        # 测试使用高阈值过滤POI类型
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            self.poi_types_file, filter_low_weight_poi=True, poi_weight_threshold=0.7
        )

        # 验证结果
        # 只有餐饮服务（权重0.8）应该被保留
        self.assertEqual(kept_categories, {"餐饮服务"})

        # 验证只有高权重的POI类型被保留
        for type_code in filtered_types:
            self.assertGreaterEqual(type_mapping[type_code]["权重"], 0.7)

    def test_filter_poi_types_special_keep_subcategories(self):
        """测试特殊保留的生活服务子类"""
        # 创建一个只包含生活服务的测试文件
        life_service_file = os.path.join(self.test_dir, "life_service_poi_types.csv")
        life_service_poi_types = [
            {
                "POI类型": "040100",
                "大类": "生活服务",
                "中类": "邮局",
                "小类": "邮政支局",
                "权重": 0.5,
            },
            {
                "POI类型": "040200",
                "大类": "生活服务",
                "中类": "物流速递",
                "小类": "快递点",
                "权重": 0.4,
            },
            {
                "POI类型": "040300",
                "大类": "生活服务",
                "中类": "家政服务",
                "小类": "家政公司",
                "权重": 0.3,
            },
        ]
        life_service_df = pd.DataFrame(life_service_poi_types)
        life_service_df.to_csv(life_service_file, index=False, encoding="utf-8-sig")

        # 测试过滤POI类型
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            life_service_file, filter_low_weight_poi=True, poi_weight_threshold=0.4
        )

        # 验证结果
        # 邮局和物流速递应该被保留（特殊保留的子类）
        self.assertIn("生活服务", kept_categories)

        # 验证特殊保留的子类被保留
        subcategories = {type_mapping[t]["中类"] for t in filtered_types}
        self.assertIn("邮局", subcategories)
        self.assertIn("物流速递", subcategories)

        # 家政服务应该被过滤掉（权重低且不是特殊保留的子类）
        self.assertNotIn("家政服务", subcategories)

    def test_get_poi_type_stats(self):
        """测试获取POI类型统计信息"""
        # 创建测试类型映射和过滤后的类型列表
        type_mapping = {
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
            "020200": {
                "大类": "购物服务",
                "中类": "超市",
                "小类": "便利店",
                "权重": 0.5,
            },
        }
        filtered_types = ["010100", "010200", "020100", "020200"]
        kept_categories = {"餐饮服务", "购物服务"}

        # 测试获取POI类型统计信息
        stats = get_poi_type_stats(type_mapping, filtered_types, kept_categories)

        # 验证结果
        self.assertIsInstance(stats, list)

        # 验证统计信息包含所有层级
        types = {stat["类型"] for stat in stats}
        self.assertIn("大类", types)
        self.assertIn("中类", types)
        self.assertIn("小类", types)

        # 验证大类统计
        category_stats = [stat for stat in stats if stat["类型"] == "大类"]
        self.assertEqual(len(category_stats), 2)  # 餐饮服务和购物服务

        # 验证中类统计
        subcategory_stats = [stat for stat in stats if stat["类型"] == "中类"]
        self.assertEqual(len(subcategory_stats), 2)  # 中餐厅和快餐厅，或者商场和超市

        # 验证小类统计
        small_category_stats = [stat for stat in stats if stat["类型"] == "小类"]
        self.assertEqual(
            len(small_category_stats), 4
        )  # 中餐馆、快餐店、综合商场、便利店


if __name__ == "__main__":
    unittest.main()
