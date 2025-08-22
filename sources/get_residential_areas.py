"""
住宅区数据获取模块

该模块负责从高德地图API获取指定行政区内的所有住宅区（小区和公寓等）数据。
通过网格切分的方式将大区域划分为小网格，逐个网格获取POI数据，
避免单次请求区域过大导致数据不完整。

功能：
1. 创建带重试和限速机制的HTTP会话，防止API请求频率过高
2. 将行政区边界切分为小网格，确保数据获取的完整性
3. 调用高德地图API获取每个网格内的住宅区POI数据
4. 将获取的数据保存为CSV文件，供后续处理使用

依赖模块：
- key_loader: 加载高德地图API密钥
- utils.get_district_boundary: 获取行政区边界数据
- config: 项目配置文件，提供路径和常量
- shapely: 处理地理空间数据
- pandas: 数据处理和保存

使用示例:
python get_residential_areas.py 田家庵区
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from tqdm import tqdm
import sys, os
from typing import Dict, List, Any, Generator, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *
from sources.utils.file.key_loader import load_key
from sources.utils.poi.get_district_boundary import get_valid_boundary as get_boundary
from sources.utils.http import RateLimitedSession

# GAODE_KEY不再在模块级别初始化，而是在需要时加载
def get_gaode_key():
    """获取高德API密钥，如果密钥文件不存在则返回空字符串"""
    try:
        return load_key(KEY_FILE)
    except Exception as e:
        print(f"警告: 无法加载API密钥: {e}")
        return ""

# 创建带限速的HTTP会话对象
session: RateLimitedSession = RateLimitedSession(min_interval=0.2)


# ---------- 2. 网格切分 ----------
def grid_split(
    polygon: Polygon, stride: float = 0.009
) -> Generator[Polygon, None, None]:
    """
    将多边形区域切分为网格

    该函数将给定的多边形区域切分为一系列小网格，用于分批获取POI数据。
    网格切分可以避免单次请求区域过大导致API返回数据不完整的问题。
    注意：这种方法容易导致多余覆盖，如需更精准的住宅区数据，还需手动检查。

    Args:
        polygon (Polygon): 要切分的多边形区域，通常是行政区边界
        stride (float): 网格大小，单位为度，默认0.009度(约1公里)

    Yields:
        Polygon: 与原多边形相交的网格多边形
    """
    minx: float
    miny: float
    maxx: float
    maxy: float
    minx, miny, maxx, maxy = polygon.bounds  # 获取多边形边界
    xs: np.ndarray = np.arange(minx, maxx + stride, stride)  # 生成x坐标序列
    ys: np.ndarray = np.arange(miny, maxy + stride, stride)  # 生成y坐标序列

    # 遍历所有网格
    for x0 in xs:
        for y0 in ys:
            # 创建网格多边形
            cell: Polygon = Polygon(
                [
                    (x0, y0),
                    (x0 + stride, y0),
                    (x0 + stride, y0 + stride),
                    (x0, y0 + stride),
                ]
            )
            # 只返回与原多边形相交的网格
            if cell.intersects(polygon):
                yield cell


# ---------- 3. 搜索 POI ----------
def search_in_rect(
    rect: Polygon, types_code: str, kw: str
) -> Generator[Dict[str, Any], None, None]:
    """
    在指定矩形区域内搜索POI数据

    该函数调用高德地图API，在给定的矩形区域内搜索指定类型的POI数据。
    支持分页获取，确保获取所有符合条件的POI。

    Args:
        rect (Polygon): 搜索区域的矩形多边形
        types_code (str): POI类型代码，多个代码用|分隔
        kw (str): 搜索关键词

    Yields:
        dict: POI数据字典，包含id、name、category、lng、lat、address等字段
    """
    url: str = "https://restapi.amap.com/v5/place/polygon"  # 高德地图POI搜索API
    # 将矩形坐标转换为字符串格式
    # [:-1]的作用是去除多边形顶点列表中重复的闭合点
    coords: str = ",".join(f"{x},{y}" for x, y in rect.exterior.coords[:-1])
    page: int = 1

    # 分页获取POI数据
    while True:
        params: Dict[str, Any] = {
            "key": get_gaode_key(),  # API密钥
            "polygon": coords,  # 搜索区域多边形
            "types": types_code,  # POI类型代码
            "keywords": kw,  # 搜索关键词
            "offset": 25,  # 每页返回数量
            "page": page,  # 页码
        }
        r: requests.Response = session.get(url, params=params)
        r_json: Dict[str, Any] = r.json()  # 发送请求

        # 检查响应状态
        if r_json.get("status") != "1":
            break

        pois: List[Dict[str, Any]] = r_json.get("pois", [])
        # 处理每个POI数据
        for p in pois:
            # 解析POI数据并返回
            location: List[str] = p["location"].split(",")
            yield {
                "id": p["id"],
                "name": p["name"],
                "category": p["typecode"],
                "lng": float(location[0]),  # 经度
                "lat": float(location[1]),  # 纬度
                "address": p.get("address", ""),
            }

        # 如果返回的POI数量少于请求的数量，说明已经是最后一页
        if len(pois) < 25:
            break
        page += 1


# ---------- 4. 主流程 ----------
def main(district: str = "田家庵区") -> None:
    """
    主函数，获取指定行政区的住宅区数据

    该函数实现了获取住宅区数据的完整流程：
    1. 检查输出文件是否已存在，避免重复处理
    2. 获取行政区边界数据
    3. 将边界区域切分为网格
    4. 对每个网格搜索住宅区POI数据
    5. 去重并保存为CSV文件

    Args:
        district (str): 行政区名称，默认为"田家庵区"

    Returns:
        None: 结果直接保存到CSV文件
    """
    # 处理行政区名称中的特殊字符，生成安全的文件名
    safe: str = "".join(c if c.isalnum() else "_" for c in district)
    csv_path: str = f"residential_{safe}.csv"

    # 检查文件是否已存在，避免重复处理
    if os.path.isfile(csv_path):
        print(f"✅ {csv_path} 已存在，跳过生成。")
        return

    # 获取行政区边界
    boundary: Polygon
    try:
        boundary = get_boundary(district)
    except ValueError as e:
        print(f"错误: {str(e)}")
        return
    except Exception as e:
        print(f"获取行政区边界失败: {str(e)}")
        return

    # 遍历所有网格，获取住宅区POI数据
    records: List[Dict[str, Any]] = []
    cell: Polygon
    for cell in tqdm(list(grid_split(boundary)), desc="网格"):
        # 住宅类POI类型代码：
        # 120100(商务住宅大类-产业园区中类-产业园区小类)
        # 120200(商务住宅大类-楼宇中类-楼宇相关小类)
        # 120300(商务住宅大类-住宅区中类-住宅区小类)
        for p in search_in_rect(cell, "120300|120200|120100", ""):
            records.append(p)

    # 去重并保存为CSV文件
    df: pd.DataFrame = pd.DataFrame(records).drop_duplicates("id")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"✅ 共抓取 {len(df)} 条记录，已保存 {csv_path}")


if __name__ == "__main__":
    import sys

    # 从命令行参数获取行政区名称，如果没有提供则使用默认值
    main(sys.argv[1] if len(sys.argv) > 1 else "田家庵区")
