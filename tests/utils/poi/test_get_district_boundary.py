#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试行政区边界获取模块
"""

import unittest
from unittest.mock import patch, Mock
from shapely.geometry import Polygon
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.poi.get_district_boundary import (
    get_district_boundary,
    get_valid_boundary,
)


class TestGetDistrictBoundary(unittest.TestCase):
    """测试行政区边界获取功能"""

    @patch("sources.utils.poi.get_district_boundary.requests.get")
    def test_get_district_boundary_success(self, mock_get):
        """测试成功获取行政区边界"""
        # 模拟第一次API调用（获取基本信息）
        mock_basic_response = Mock()
        mock_basic_response.json.return_value = {
            "status": "1",
            "count": "1",
            "districts": [{"adcode": "340400", "name": "田家庵区"}],
        }

        # 模拟第二次API调用（获取边界信息）
        mock_boundary_response = Mock()
        mock_boundary_response.json.return_value = {
            "status": "1",
            "count": "1",
            "districts": [
                {
                    "adcode": "340400",
                    "name": "田家庵区",
                    "polyline": "116.998316,32.631699;116.999316,32.632699;117.000316,32.633699",
                }
            ],
        }

        # 设置mock_get的返回值序列
        mock_get.side_effect = [mock_basic_response, mock_boundary_response]

        # 测试获取行政区边界
        result = get_district_boundary("田家庵区", "淮南市", "340400")

        # 验证结果
        self.assertIsInstance(result, Polygon)
        self.assertTrue(result.is_valid)

        # 验证API调用次数
        self.assertEqual(mock_get.call_count, 2)

    @patch("sources.utils.poi.get_district_boundary.requests.get")
    def test_get_district_boundary_wrong_adcode(self, mock_get):
        """测试获取行政区边界（行政区划代码不匹配）"""
        # 模拟API响应（行政区划代码不匹配）
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "1",
            "count": "1",
            "districts": [{"adcode": "340100", "name": "田家庵区"}],  # 不匹配的代码
        }
        mock_get.return_value = mock_response

        # 测试获取行政区边界，应该抛出ValueError
        with self.assertRaises(ValueError):
            get_district_boundary("田家庵区", "淮南市", "340400")

    @patch("sources.utils.poi.get_district_boundary.requests.get")
    def test_get_district_boundary_no_districts(self, mock_get):
        """测试获取行政区边界（没有找到行政区）"""
        # 模拟API响应（没有找到行政区）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "1", "count": "0", "districts": []}
        mock_get.return_value = mock_response

        # 测试获取行政区边界，应该抛出ValueError
        with self.assertRaises(ValueError):
            get_district_boundary("不存在的区", "淮南市", "340400")

    @patch("sources.utils.poi.get_district_boundary.requests.get")
    def test_get_district_boundary_api_error(self, mock_get):
        """测试获取行政区边界（API错误）"""
        # 模拟API响应（状态码不为1）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "0", "info": "INVALID_USER_KEY"}
        mock_get.return_value = mock_response

        # 测试获取行政区边界，应该抛出ValueError
        with self.assertRaises(ValueError):
            get_district_boundary("田家庵区", "淮南市", "340400")

    @patch("sources.utils.poi.get_district_boundary.get_district_boundary")
    def test_get_valid_boundary_first_try(self, mock_get_boundary):
        """测试获取有效边界（第一次尝试成功）"""
        # 模拟第一次调用就成功
        mock_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        mock_get_boundary.return_value = mock_polygon

        # 测试获取有效边界
        result = get_valid_boundary("田家庵区")

        # 验证结果
        self.assertEqual(result, mock_polygon)

        # 验证只调用了一次
        mock_get_boundary.assert_called_once_with("田家庵区", "淮南市", "340400")

    @patch("sources.utils.poi.get_district_boundary.get_district_boundary")
    def test_get_valid_boundary_multiple_tries(self, mock_get_boundary):
        """测试获取有效边界（多次尝试后成功）"""
        # 模拟前三次调用失败，第四次成功
        mock_get_boundary.side_effect = [
            ValueError("第一次失败"),
            ValueError("第二次失败"),
            ValueError("第三次失败"),
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        ]

        # 测试获取有效边界
        result = get_valid_boundary("田家庵区")

        # 验证结果
        self.assertIsInstance(result, Polygon)

        # 验证调用了四次
        self.assertEqual(mock_get_boundary.call_count, 4)

        # 验证最后一次调用的参数
        mock_get_boundary.assert_called_with("田家庵区", "蚌埠市", "340300")

    @patch("sources.utils.poi.get_district_boundary.get_district_boundary")
    def test_get_valid_boundary_all_fail(self, mock_get_boundary):
        """测试获取有效边界（所有尝试都失败）"""
        # 模拟所有调用都失败
        mock_get_boundary.side_effect = [
            ValueError("第一次失败"),
            ValueError("第二次失败"),
            ValueError("第三次失败"),
            ValueError("第四次失败"),
        ]

        # 测试获取有效边界，应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            get_valid_boundary("不存在的区")

        # 验证异常信息
        self.assertIn("无法获取有效边界数据", str(context.exception))

        # 验证调用了四次
        self.assertEqual(mock_get_boundary.call_count, 4)


if __name__ == "__main__":
    unittest.main()
