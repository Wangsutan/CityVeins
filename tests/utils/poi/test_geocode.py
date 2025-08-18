#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试地理编码模块
"""

import unittest
from unittest.mock import patch, Mock
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from sources.utils.poi.geocode import geocode


class TestGeocode(unittest.TestCase):
    """测试地理编码功能"""

    @patch("sources.utils.poi.geocode.requests.get")
    def test_geocode_success(self, mock_get):
        """测试成功地理编码"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "1",
            "count": "1",
            "geocodes": [{"location": "116.998316,32.631699"}],
        }
        mock_get.return_value = mock_response

        # 测试地理编码
        result = geocode("舜耕西路123号")

        # 验证结果
        self.assertEqual(result, (116.998316, 32.631699))

        # 验证API调用
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("key", kwargs["params"])
        self.assertEqual(kwargs["params"]["address"], "舜耕西路123号")

    @patch("sources.utils.poi.geocode.requests.get")
    def test_geocode_failure_status(self, mock_get):
        """测试API状态码失败的地理编码"""
        # 模拟API响应（状态码不为1）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "0", "info": "INVALID_USER_KEY"}
        mock_get.return_value = mock_response

        # 测试地理编码，应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            geocode("不存在的地址")

        # 验证异常信息
        self.assertIn("Geocode失败", str(context.exception))
        self.assertIn("INVALID_USER_KEY", str(context.exception))

    @patch("sources.utils.poi.geocode.requests.get")
    def test_geocode_failure_count(self, mock_get):
        """测试API返回结果数为0的地理编码"""
        # 模拟API响应（结果数为0）
        mock_response = Mock()
        mock_response.json.return_value = {"status": "1", "count": "0", "geocodes": []}
        mock_get.return_value = mock_response

        # 测试地理编码，应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            geocode("不存在的地址")

        # 验证异常信息
        self.assertIn("Geocode失败", str(context.exception))

    @patch("sources.utils.poi.geocode.requests.get")
    def test_geocode_timeout(self, mock_get):
        """测试API超时的地理编码"""
        # 模拟API超时
        mock_get.side_effect = Exception("Request timeout")

        # 测试地理编码，应该抛出异常
        with self.assertRaises(Exception):
            geocode("测试地址")


if __name__ == "__main__":
    unittest.main()
