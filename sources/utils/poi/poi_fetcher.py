"""
POI数据获取模块
提供从高德地图API获取POI数据的功能
"""

import requests
import time
import sys, os
import argparse
import json
from typing import Dict, Any, List, Optional

# 获取项目根目录
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, project_root)

# 尝试导入config
try:
    from config import (
        ROOT_DIR,
        DATA_DIR,
        OUTPUT_DIR,
        KEY_FILE,
        WEIGHT_FILE,
        POI_CODE_FILE,
        RESIDENTIAL_OUT,
        POI_OUT,
    )
except ImportError:
    # 如果导入失败，手动设置配置变量
    ROOT_DIR = project_root
    DATA_DIR = os.path.join(ROOT_DIR, "data")
    OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
    KEY_FILE = os.path.join(ROOT_DIR, "data", "key", "key.txt")
    WEIGHT_FILE = os.path.join(ROOT_DIR, "data", "poi_weights", "高德POI_加权.csv")
    POI_CODE_FILE = os.path.join(
        ROOT_DIR, "data", "poi_code", "高德POI分类与编码（中英文）_V1.06_20230208.csv"
    )
    RESIDENTIAL_OUT = lambda d: os.path.join(
        ROOT_DIR, "data", "residential", f"residential_{d}.csv"
    )
    POI_OUT = lambda rid: os.path.join(ROOT_DIR, "output", "poi", f"poi_{rid}.csv")

# 尝试导入key_loader
try:
    from ..file.key_loader import load_key
except (ImportError, ValueError):
    # 如果相对导入失败，尝试直接导入key_loader模块
    key_loader_path = os.path.join(project_root, "sources", "utils", "file")
    if key_loader_path not in sys.path:
        sys.path.append(key_loader_path)
    try:
        import key_loader

        load_key = key_loader.load_key
    except (ImportError, ValueError):
        # 如果还是失败，直接实现load_key函数
        def load_key(path: str = KEY_FILE) -> str:
            if not os.path.exists(path):
                raise FileNotFoundError(f"密钥文件不存在: {path}")

            with open(path, "r", encoding="utf-8") as f:
                key: str = f.read().strip()

            if not key:
                raise ValueError(f"密钥文件为空: {path}")

            return key


GAODE_KEY = load_key(KEY_FILE)


def get_pois(
    lng: float, lat: float, poi_type: str, radius: int = 1200
) -> List[Dict[str, Any]]:
    """获取指定类型的所有POI"""
    pois: List[Dict[str, Any]] = []
    page: int = 1

    while True:

        url: str = "https://restapi.amap.com/v3/place/around"
        params: Dict[str, Any] = {
            "key": GAODE_KEY,
            "location": f"{lng},{lat}",
            "types": poi_type,
            "radius": radius,
            "page": page,
            "offset": 25,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            resp: Dict[str, Any] = response.json()

            # 检查API响应状态
            if resp.get("status") != "1":
                error_info = resp.get("info", "未知错误")
                error_code = resp.get("infocode", "无错误代码")

                # 检查特定错误代码
                if error_code == "10001":  # 无效的KEY
                    raise ValueError(f"无效的API密钥: {error_info}")
                elif error_code == "10002":  # 无效的请求
                    raise ValueError(f"无效的请求参数: {error_info}")
                elif error_code == "10003":  # 权限不足
                    raise ValueError(f"API权限不足: {error_info}")
                elif error_code == "10004":  # 配额超限
                    raise ValueError(f"API调用配额已用完: {error_info}")
                elif error_code == "10008":  # 请求过于频繁
                    print(f"警告: 请求过于频繁，等待1秒后重试...")
                    time.sleep(1)
                    continue
                elif error_code == "10009":  # 请求过于频繁
                    print(f"警告: 请求过于频繁，等待5秒后重试...")
                    time.sleep(5)
                    continue
                else:
                    print(
                        f"警告: API请求失败，错误代码: {error_code}, 错误信息: {error_info}"
                    )
                    break

            # 成功获取数据
            current_pois = resp.get("pois", [])
            if not current_pois:
                print(f"提示: 第 {page} 页没有返回POI数据")
                break

            pois.extend(current_pois)
            print(f"成功获取第 {page} 页数据，当前POI总数: {len(pois)}")

            # 如果返回的POI数量小于请求的数量，说明没有更多数据了
            if len(current_pois) < 25:
                break

            page += 1
            time.sleep(0.2)  # 稍微增加请求间隔，避免触发频率限制

        except requests.exceptions.Timeout:
            print("警告: 请求超时，重试中...")
            time.sleep(1)
            continue
        except requests.exceptions.RequestException as e:
            print(f"警告: 网络请求异常: {str(e)}")
            break
        except ValueError as e:
            print(f"错误: {str(e)}")
            raise  # 重新抛出关键错误
        except Exception as e:
            print(f"警告: 处理请求时发生未知错误: {str(e)}")
            break

    return pois


if __name__ == "__main__":
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="POI数据获取工具")
    parser.add_argument("lng", type=float, help="中心点经度")
    parser.add_argument("lat", type=float, help="中心点纬度")
    parser.add_argument("poi_type", help="POI类型代码")
    parser.add_argument(
        "--radius", type=int, default=1200, help="搜索半径(米)，默认为1200"
    )
    parser.add_argument("--output", help="输出文件路径(可选)")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出结果")

    args = parser.parse_args()

    try:
        # 获取POI数据
        print(f"正在获取位置 ({args.lng}, {args.lat}) 周围的POI数据...")
        print(f"POI类型: {args.poi_type}")
        print(f"搜索半径: {args.radius}米")

        pois = get_pois(args.lng, args.lat, args.poi_type, args.radius)

        print(f"找到 {len(pois)} 个POI")

        # 如果有POI数据，打印第一个POI的完整结构
        if pois:
            print("\n第一个POI的完整结构:")
            print("-" * 80)
            print(json.dumps(pois[0], ensure_ascii=False, indent=2))
            print("-" * 80)

        # 如果指定了输出文件，保存结果
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.json:
                    json.dump(pois, f, ensure_ascii=False, indent=2)
                else:
                    # 简单的CSV格式输出
                    f.write("名称,类型,地址,经度,纬度,距离")
                    for poi in pois:
                        name = poi.get("name", "").replace(",", "，")
                        poi_type = poi.get("type", "").replace(",", "，")
                        address = poi.get("address", "").replace(",", "，")
                        location = poi.get("location", ",").split(",")
                        lng_poi = location[0] if len(location) > 0 else ""
                        lat_poi = location[1] if len(location) > 1 else ""
                        distance = poi.get("distance", "")
                        f.write(
                            f"{name},{poi_type},{address},{lng_poi},{lat_poi},{distance}"
                        )
            print(f"结果已保存到: {args.output}")

        # 输出结果
        if args.json:
            print(json.dumps(pois, ensure_ascii=False, indent=2))
        else:
            print("前10个POI结果:")
            print("-" * 80)
            print(f"{'序号':<4}{'名称':<20}{'类型':<15}{'地址':<25}{'距离(米)':<10}")
            print("-" * 80)
            for i, poi in enumerate(pois[:10]):
                name = poi.get("name", "")[:19]  # 限制名称长度
                poi_type = poi.get("type", "")[:14]  # 限制类型长度
                address = poi.get("address", "")[:24]  # 限制地址长度
                distance = poi.get("distance", "")
                print(f"{i+1:<4}{name:<20}{poi_type:<15}{address:<25}{distance:<10}")

            if len(pois) > 10:
                print(f"还有 {len(pois) - 10} 个POI未显示")

    except Exception as e:
        print(f"获取POI数据时出错: {str(e)}")
        sys.exit(1)
