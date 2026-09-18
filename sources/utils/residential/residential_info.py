"""
住宅区信息处理模块

提供住宅区信息获取和处理的工具函数。
"""

import os
import pandas as pd
from typing import Optional, Tuple
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)
from config import RESIDENTIAL_OUT


def get_residential_info(
    residential_id: str, district: str = "田家庵区"
) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float]]:
    """
    从住宅区数据文件中获取指定ID的住宅区信息

    Args:
        residential_id (str): 住宅区ID
        district (str): 行政区名称，默认为"田家庵区"

    Returns:
        tuple: (住宅区名称, 住宅区地址, 经度, 纬度) 或 (None, None, None, None) 如果未找到
    """
    try:
        # 尝试从多个可能的位置查找住宅区数据文件
        possible_paths = [
            RESIDENTIAL_OUT(district),  # 使用配置文件中的路径
            os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                ),
                "data",
                "residential",
                f"residential_{district}.csv",
            ),
        ]

        residential_file = None
        for path in possible_paths:
            if os.path.exists(path):
                residential_file = path
                break

        # 如果找到CSV文件，从中获取信息
        if residential_file:
            try:
                df = pd.read_csv(residential_file)
                residential = df[df["id"] == residential_id]

                if not residential.empty:
                    name = residential.iloc[0]["name"]
                    address = residential.iloc[0].get("address", "")
                    lng = residential.iloc[0].get("lng", None)
                    lat = residential.iloc[0].get("lat", None)
                    return name, address, lng, lat
                else:
                    print(
                        f"在文件 {residential_file} 中未找到ID为 {residential_id} 的住宅区"
                    )
            except Exception as e:
                print(f"读取住宅区文件 {residential_file} 失败: {str(e)}")

        # 如果CSV文件不存在或找不到住宅区，尝试通过高德API获取
        print(f"尝试通过高德API获取住宅区ID为 {residential_id} 的信息")
        try:
            import requests

            # 从环境变量或配置文件加载API密钥
            key_file = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                ),
                "data",
                "key",
                "key.txt",
            )

            if os.path.exists(key_file):
                with open(key_file, "r", encoding="utf-8") as f:
                    api_key = f.read().strip()
            else:
                print("未找到API密钥文件，无法通过API获取住宅区信息")
                return None, None, None, None

            # 使用高德POI详情API获取住宅区信息
            url = "https://restapi.amap.com/v3/place/detail"
            params = {"key": api_key, "id": residential_id}
            response = requests.get(url, params=params, timeout=10)
            result = response.json()

            if (
                result.get("status") == "1"
                and "pois" in result
                and len(result["pois"]) > 0
            ):
                poi_data = result["pois"][0]
                name = poi_data.get("name", "")
                address = poi_data.get("address", "")
                location = poi_data.get("location", "")

                lng, lat = None, None
                if location:
                    try:
                        location_parts = location.split(",")
                        if len(location_parts) >= 2:
                            lng, lat = (
                                float(location_parts[0]),
                                float(location_parts[1]),
                            )
                        else:
                            print(f"警告：位置格式不正确: {location}")
                    except Exception as e:
                        print(f"解析位置失败: {str(e)}")

                print(f"通过高德API成功获取住宅区信息: {name}, {address}")
                return name, address, lng, lat
            else:
                print(f"高德API未找到住宅区ID: {residential_id}")
                return None, None, None, None
        except Exception as e:
            print(f"通过高德API获取住宅区信息失败: {str(e)}")
            return None, None, None, None
    except Exception as e:
        print(f"获取住宅区信息失败: {str(e)}")
        return None, None, None, None
