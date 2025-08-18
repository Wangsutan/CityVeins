#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试POI数据获取模块
"""

import unittest
from unittest.mock import patch, Mock
import time
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.poi.poi_fetcher import get_pois


class TestPoiFetcher(unittest.TestCase):
    """测试POI数据获取功能"""

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    def test_get_pois_success_single_page(self, mock_get):
        """测试成功获取POI数据（单页结果）"""
        # 模拟API响应（单页结果）
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "1",
            "pois": [
                {
                    "id": "B001",
                    "name": "测试POI1",
                    "address": "测试地址1",
                    "location": "116.998316,32.631699",
                    "distance": "500",
                },
                {
                    "id": "B002",
                    "name": "测试POI2",
                    "address": "测试地址2",
                    "location": "116.999316,32.632699",
                    "distance": "600",
                },
            ],
        }
        mock_get.return_value = mock_response

        # 测试获取POI数据
        result = get_pois(116.998316, 32.631699, "010100")

        # 验证结果
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "B001")
        self.assertEqual(result[1]["id"], "B002")

        # 验证API调用
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("key", kwargs["params"])
        self.assertEqual(kwargs["params"]["location"], "116.998316,32.631699")
        self.assertEqual(kwargs["params"]["types"], "010100")
        self.assertEqual(kwargs["params"]["page"], 1)

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    def test_get_pois_success_multiple_pages(self, mock_get):
        """测试成功获取POI数据（多页结果）"""
        # 模拟第一页API响应（满页结果）
        first_page_response = Mock()
        first_page_response.json.return_value = {
            "status": "1",
            "pois": [
                {
                    "id": f"B{i:03d}",
                    "name": f"测试POI{i}",
                    "location": "116.998316,32.631699",
                    "distance": "500",
                }
                for i in range(1, 26)
            ],
        }

        # 模拟第二页API响应（不满页结果）
        second_page_response = Mock()
        second_page_response.json.return_value = {
            "status": "1",
            "pois": [
                {
                    "id": "B026",
                    "name": "测试POI26",
                    "location": "116.998316,32.631699",
                    "distance": "500",
                }
            ],
        }

        # 设置mock_get的返回值序列
        mock_get.side_effect = [first_page_response, second_page_response]

        # 测试获取POI数据
        result = get_pois(116.998316, 32.631699, "010100")

        # 验证结果
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 26)
        self.assertEqual(result[0]["id"], "B001")
        self.assertEqual(result[25]["id"], "B026")

        # 验证API调用次数
        self.assertEqual(mock_get.call_count, 2)

        # 验证第二次调用的页码
        args, kwargs = mock_get.call_args_list[1]
        self.assertEqual(kwargs["params"]["page"], 2)

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    def test_get_pois_api_failure(self, mock_get):
        """测试API调用失败"""
        # 模拟API响应（状态码不为1）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "0", "info": "INVALID_USER_KEY"}
        mock_get.return_value = mock_response

        # 测试获取POI数据
        result = get_pois(116.998316, 32.631699, "010100")

        # 验证结果（应该返回空列表）
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    def test_get_pois_empty_result(self, mock_get):
        """测试API返回空结果"""
        # 模拟API响应（空结果）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "1", "pois": []}
        mock_get.return_value = mock_response

        # 测试获取POI数据
        result = get_pois(116.998316, 32.631699, "010100")

        # 验证结果（应该返回空列表）
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    @patch("time.sleep", return_value=None)  # Mock sleep to speed up tests
    def test_get_pois_with_custom_radius(self, mock_sleep, mock_get):
        """测试使用自定义半径获取POI数据"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "1",
            "pois": [
                {
                    "id": "B001",
                    "name": "测试POI1",
                    "location": "116.998316,32.631699",
                    "distance": "1500",
                }
            ],
        }
        mock_get.return_value = mock_response

        # 测试使用自定义半径获取POI数据
        result = get_pois(116.998316, 32.631699, "010100", radius=2000)

        # 验证结果
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

        # 验证API调用参数包含自定义半径
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["radius"], 2000)

    @patch("sources.utils.poi.poi_fetcher.requests.get")
    def test_get_pois_timeout(self, mock_get):
        """测试API超时"""
        # 模拟API超时
        mock_get.side_effect = Exception("Request timeout")

        # 测试获取POI数据，应该抛出异常
        with self.assertRaises(Exception):
            get_pois(116.998316, 32.631699, "010100")


if __name__ == "__main__":
    unittest.main()
