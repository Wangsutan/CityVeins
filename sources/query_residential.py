#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
住宅区查询工具
提供多种方式查询住宅区信息，包括名称、经纬度等
"""

import os
import sys
import json
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from config import KEY_FILE, OUTPUT_DIR

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_api_key() -> str:
    """
    从密钥文件中获取API密钥

    Returns:
        str: API密钥
    """
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"读取API密钥失败: {str(e)}")
        return ""


def query_by_name(name: str) -> List[Dict[str, Any]]:
    """
    根据住宅区名称查询住宅区信息

    Args:
        name (str): 住宅区名称

    Returns:
        List[Dict[str, Any]]: 查询结果列表
    """
    try:
        # 获取API密钥
        api_key = get_api_key()
        if not api_key:
            print("错误: 无法获取API密钥")
            return []

        # 使用高德地图POI搜索API获取真实的POI ID
        url = "https://restapi.amap.com/v3/place/text"
        params = {
            "key": api_key,
            "keywords": name,
            "city": "全国",
            "types": "120000",  # 住宅区类型代码
            "offset": 20,  # 增加返回结果数量
        }

        response = requests.get(url, params=params)
        data = response.json()

        # 不再打印API响应

        if data["status"] == "1" and int(data["count"]) > 0:
            results = []
            for poi in data["pois"]:
                # 提取经纬度
                location_parts = poi["location"].split(",")
                if len(location_parts) >= 2:
                    longitude = float(location_parts[0])
                    latitude = float(location_parts[1])
                else:
                    print(f"警告：位置格式不正确: {poi['location']}")
                    continue

                # 构建结果，使用真实的POI ID
                result = {
                    "id": poi["id"],  # 使用高德地图返回的真实POI ID
                    "name": poi["name"],
                    "address": poi["address"],
                    "province": poi.get("pname", ""),
                    "city": poi.get("cityname", ""),
                    "district": poi.get("adname", ""),
                    "longitude": longitude,
                    "latitude": latitude,
                    "type": poi["type"],
                }
                results.append(result)

            return results
        else:
            # 如果POI搜索失败，回退到地理编码API
            return _fallback_to_geocoding(api_key, name)
    except Exception as e:
        print(f"查询失败: {str(e)}")
        return []


def query_by_coordinates(
    longitude: float, latitude: float, radius: int = 1000
) -> List[Dict[str, Any]]:
    """
    根据经纬度查询附近的住宅区

    Args:
        longitude (float): 经度
        latitude (float): 纬度
        radius (int): 搜索半径，单位米

    Returns:
        List[Dict[str, Any]]: 查询结果列表
    """
    try:
        # 获取API密钥
        api_key = get_api_key()
        if not api_key:
            print("错误: 无法获取API密钥")
            return []

        # 使用高德地图API进行逆地理编码
        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {
            "key": api_key,
            "location": f"{longitude},{latitude}",
            "radius": radius,
            "extensions": "all",
        }

        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] == "1":
            results = []
            regeocode = data["regeocode"]

            # 获取POI信息
            if "pois" in regeocode:
                for poi in regeocode["pois"]:
                    # 只选择住宅区相关的POI
                    if "小区" in poi["name"] or "住宅" in poi["type"]:
                        # 提取经纬度
                        location_parts = poi["location"].split(",")
                        if len(location_parts) >= 2:
                            poi_longitude = float(location_parts[0])
                            poi_latitude = float(location_parts[1])
                        else:
                            print(f"警告：位置格式不正确: {poi['location']}")
                            continue

                        # 构建结果
                        result = {
                            "id": poi["id"],
                            "name": poi["name"],
                            "address": poi["address"],
                            "longitude": poi_longitude,
                            "latitude": poi_latitude,
                            "type": poi["type"],
                            "distance": poi["distance"],
                        }
                        results.append(result)

            # 如果没有找到POI，使用地址信息
            if not results and "addressComponent" in regeocode:
                address_component = regeocode["addressComponent"]
                formatted_address = regeocode.get("formatted_address", "")

                # 构建结果
                result = {
                    "id": f"L{address_component.get('adcode', '')}{address_component.get('towncode', '')[:6]}",
                    "name": formatted_address,
                    "address": formatted_address,
                    "longitude": longitude,
                    "latitude": latitude,
                    "adcode": address_component.get("adcode", ""),
                    "level": "未知",
                }
                results.append(result)

            return results
        else:
            return []
    except Exception as e:
        print(f"查询失败: {str(e)}")
        return []


def get_residential_details(residential_id: str) -> Optional[Dict[str, Any]]:
    """
    获取住宅区详细信息

    Args:
        residential_id (str): 住宅区ID

    Returns:
        Optional[Dict[str, Any]]: 住宅区详细信息，如果找不到则返回None
    """
    try:
        # 尝试从已有的POI文件中获取信息
        poi_file = os.path.join(OUTPUT_DIR, "poi", f"poi_{residential_id}.csv")
        if os.path.exists(poi_file):
            df = pd.read_csv(poi_file)
            if not df.empty:
                # 获取第一行的住宅区信息
                row = df.iloc[0]
                return {
                    "id": residential_id,
                    "name": row.get("住宅区名称", ""),
                    "address": row.get("住宅区地址", ""),
                    "longitude": row.get("经度", 0),
                    "latitude": row.get("纬度", 0),
                }

        # 如果找不到POI文件，尝试从高德地图API获取信息
        try:
            # 如果是临时ID（以L开头），尝试通过名称和地址获取真实ID
            if residential_id.startswith("L"):
                # 从临时ID中提取可能的名称信息
                # 尝试通过地理编码API获取更详细的信息
                api_key = get_api_key()
                if api_key:
                    # 使用逆地理编码API尝试获取POI信息
                    url = "https://restapi.amap.com/v3/geocode/regeo"
                    # 这里需要经纬度信息，但我们没有，所以尝试其他方法

                    # 尝试通过POI搜索API获取真实ID
                    url = "https://restapi.amap.com/v3/place/text"
                    # 从ID中提取可能的名称信息
                    name = residential_id[1:]  # 去掉开头的L
                    params = {
                        "key": api_key,
                        "keywords": name,
                        "city": "全国",
                        "types": "120000",  # 住宅区类型代码
                        "offset": 5,  # 只取前5个结果
                    }

                    response = requests.get(url, params=params)
                    data = response.json()

                    if data["status"] == "1" and int(data["count"]) > 0:
                        # 取第一个结果
                        poi = data["pois"][0]
                        location = poi["location"].split(",")
                        longitude = float(location[0])
                        latitude = float(location[1])

                        return {
                            "id": poi["id"],  # 使用高德地图返回的真实POI ID
                            "name": poi["name"],
                            "address": poi["address"],
                            "longitude": longitude,
                            "latitude": latitude,
                        }
        except Exception as e:
            print(f"通过API获取住宅区详情失败: {str(e)}")

        return None
    except Exception as e:
        print(f"获取住宅区详情失败: {str(e)}")
        return None


def save_query_results(
    results: List[Dict[str, Any]], query_type: str, query_value: str
) -> str:
    """
    保存查询结果到文件

    Args:
        results (List[Dict[str, Any]]): 查询结果列表
        query_type (str): 查询类型，如name、coordinates
        query_value (str): 查询值

    Returns:
        str: 保存的文件路径
    """
    # 创建查询结果目录
    query_dir = os.path.join(OUTPUT_DIR, "query_results")
    os.makedirs(query_dir, exist_ok=True)

    # 生成文件名
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filename = f"query_{query_type}_{query_value}_{timestamp}.json"
    filepath = os.path.join(query_dir, filename)

    # 保存结果
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "query_type": query_type,
                "query_value": query_value,
                "timestamp": timestamp,
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return filepath


def main():
    """主函数，用于测试"""
    # 测试按名称查询
    print("测试按名称查询...")
    name_results = query_by_name("万科城市花园")
    print(f"找到 {len(name_results)} 个结果")
    for i, result in enumerate(name_results[:3]):  # 只显示前3个结果
        print(f"{i+1}. {result['name']} ({result['longitude']}, {result['latitude']})")

    # 测试按经纬度查询
    print("\n测试按经纬度查询...")
    coord_results = query_by_coordinates(116.481181, 39.989792)
    print(f"找到 {len(coord_results)} 个结果")
    for i, result in enumerate(coord_results[:3]):  # 只显示前3个结果
        print(f"{i+1}. {result['name']} ({result['longitude']}, {result['latitude']})")


def _fallback_to_geocoding(api_key: str, name: str) -> List[Dict[str, Any]]:
    """
    回退到地理编码API的函数

    Args:
        api_key (str): API密钥
        name (str): 住宅区名称

    Returns:
        List[Dict[str, Any]]: 查询结果列表
    """
    try:
        # 使用高德地图API进行地理编码
        url = "https://restapi.amap.com/v3/geocode/geo"
        params = {
            "key": api_key,
            "address": name,
            "city": "全国",  # 使用"全国"作为默认值，让API自动匹配城市
        }

        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] == "1" and int(data["count"]) > 0:
            results = []
            for geocode in data["geocodes"]:
                # 提取经纬度
                location_parts = geocode["location"].split(",")
                if len(location_parts) >= 2:
                    longitude = float(location_parts[0])
                    latitude = float(location_parts[1])
                else:
                    print(f"警告：位置格式不正确: {geocode['location']}")
                    continue

                # 构建结果
                # 使用adcode和经纬度构造一个临时ID，避免使用可能不存在的towncode字段
                town_code = (
                    geocode.get("towncode", "")[:6] if "towncode" in geocode else ""
                )
                result = {
                    "id": f"L{geocode['adcode']}{town_code}",  # 构造一个临时ID
                    "name": geocode["formatted_address"],
                    "address": geocode["formatted_address"],
                    "longitude": longitude,
                    "latitude": latitude,
                    "adcode": geocode["adcode"],
                    "level": geocode["level"],
                }
                results.append(result)

            return results
        else:
            return []
    except Exception as e:
        # 不再打印地理编码查询失败信息
        return []


if __name__ == "__main__":
    main()
