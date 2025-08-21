"""
行政区边界获取模块

该模块负责从高德地图API获取中国各级行政区的边界数据，返回多边形对象。
主要用于验证行政区名称的合法性。

依赖模块：
- requests: HTTP请求库
- shapely: 地理空间数据处理
- utils.file.key_loader: API密钥加载工具
- config: 项目配置文件

使用示例:
# 验证行政区是否存在
try:
    boundary = get_district_boundary("田家庵区", "淮南市")
    print(f"行政区存在: {boundary}")
except ValueError:
    print("行政区不存在")
"""

import requests
import argparse
from shapely.geometry import Polygon
import sys
import os
from typing import Dict, Any, List, Optional, Union, Final, Callable


# 获取项目根目录
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, PROJECT_ROOT)


# 直接导入key_loader函数
def load_key(key_file: str) -> str:
    """加载API密钥"""
    with open(key_file, "r", encoding="utf-8") as f:
        return f.read().strip()


# 直接定义配置变量
ROOT_DIR: Final[str] = PROJECT_ROOT
DATA_DIR: Final[str] = os.path.join(ROOT_DIR, "data")
OUTPUT_DIR: Final[str] = os.path.join(ROOT_DIR, "output")
KEY_FILE: Final[str] = os.path.join(DATA_DIR, "key", "key.txt")
WEIGHT_FILE: Final[str] = os.path.join(DATA_DIR, "poi_weights", "高德POI_加权.csv")
POI_CODE_FILE: Final[str] = os.path.join(
    DATA_DIR, "poi_code", "高德POI分类与编码（中英文）_V1.06_20230208.csv"
)
RESIDENTIAL_OUT: Callable[[str], str] = lambda d: os.path.join(
    DATA_DIR, "residential", f"residential_{d}.csv"
)
POI_OUT: Callable[[str], str] = lambda rid: os.path.join(
    OUTPUT_DIR, "poi", f"poi_{rid}.csv"
)

GAODE_KEY: str = load_key(KEY_FILE)


# 从配置文件中读取默认城市和行政区
DEFAULT_CITY: str = "淮南市"
DEFAULT_DISTRICT: str = "田家庵区"


def get_district_boundary(
    district_name: str = DEFAULT_DISTRICT, city_name: str = DEFAULT_CITY
) -> Optional[Polygon]:
    """
    获取行政区边界数据

    通过高德地图API获取指定行政区的边界数据，并转换为shapely Polygon对象。

    处理流程：
    1. 构建API请求参数，包含城市名称和行政区名称
    2. 发送HTTP请求获取边界数据
    3. 检查响应状态和结果数量
    4. 解析边界坐标并构建Polygon对象

    Args:
        district_name (str): 行政区名称，默认为"田家庵区"
        city_name (str): 城市名称，默认为"淮南市"

    Returns:
        Polygon: 表示行政区边界的多边形对象

    Raises:
        ValueError: 当获取边界数据失败时抛出此异常
    """
    url: str = "https://restapi.amap.com/v3/config/district"
    params: Dict[str, Any] = {
        "keywords": district_name,
        "subdistrict": 0,
        "extensions": "base",
        "key": GAODE_KEY,
        "output": "JSON",
        "filter": f"city={city_name}",
    }
    r: Dict[str, Any] = requests.get(url, params=params).json()

    if r.get("status") == "1" and int(r.get("count", 0)) > 0:
        district: Dict[str, Any] = r["districts"][0]
        # 获取边界数据
        url: str = "https://restapi.amap.com/v3/config/district"
        params: Dict[str, Any] = {
            "keywords": district["adcode"],  # 使用adcode获取完整边界数据
            "subdistrict": 0,
            "extensions": "all",
            "key": GAODE_KEY,
            "output": "JSON",
        }
        r: Dict[str, Any] = requests.get(url, params=params).json()

        if r.get("status") == "1" and int(r.get("count", 0)) > 0:
            district: Dict[str, Any] = r["districts"][0]
            polyline: str = district["polyline"]
            # 解析边界坐标
            coordinates: List[List[Tuple[float, float]]] = []
            part: str
            for part in polyline.split("|"):
                coords: List[Tuple[float, float]] = []
                point: str
                for point in part.split(";"):
                    lng: float
                    lat: float
                    point_parts = point.split(",")
                    if len(point_parts) >= 2:
                        lng, lat = float(point_parts[0]), float(point_parts[1])
                    else:
                        print(f"警告：位置格式不正确: {point}")
                        continue
                    coords.append((lng, lat))
                if coords:  # 确保不是空列表
                    coordinates.append(coords)

            if coordinates:
                return Polygon(coordinates[0])  # 使用第一个多边形

    raise ValueError(f"获取边界数据失败: {city_name}{district_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="行政区边界获取工具")
    parser.add_argument(
        "district",
        nargs="?",
        default=DEFAULT_DISTRICT,
        help=f"行政区名称，默认为 {DEFAULT_DISTRICT}",
    )
    parser.add_argument(
        "--city", default=DEFAULT_CITY, help=f"城市名称，默认为 {DEFAULT_CITY}"
    )
    parser.add_argument("--json", action="store_true", help="以JSON格式输出结果")

    args = parser.parse_args()

    try:
        boundary = get_district_boundary(args.district, args.city)
        if args.json:
            import json

            result = {
                "district": args.district,
                "city": args.city,
                "exists": True,
                "area": float(boundary.area),
                "centroid": [float(boundary.centroid.x), float(boundary.centroid.y)],
                "bounds": [float(coord) for coord in boundary.bounds],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"✅ 行政区存在: {args.district}")
            print(f"   城市: {args.city}")
            print(f"   边界面积: {boundary.area:.6f} 平方度")
            print(
                f"   边界中心: ({boundary.centroid.x:.6f}, {boundary.centroid.y:.6f})"
            )
            print(
                f"   边界坐标范围: ({boundary.bounds[0]:.6f}, {boundary.bounds[1]:.6f}) - ({boundary.bounds[2]:.6f}, {boundary.bounds[3]:.6f})"
            )
    except ValueError as e:
        if args.json:
            import json

            result = {
                "district": args.district,
                "city": args.city,
                "exists": False,
                "error": str(e),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 行政区不存在: {args.district}")
            print(f"   错误信息: {str(e)}")
