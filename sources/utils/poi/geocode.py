"""
地理编码工具模块
提供地址转坐标的功能
"""

import requests
import sys, os
from typing import Dict, Any, Optional, Tuple

# 处理导入问题
try:
    # 获取项目根目录的绝对路径
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
            ROOT_DIR,
            "data",
            "poi_code",
            "高德POI分类与编码（中英文）_V1.06_20230208.csv",
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
except Exception as e:
    print(f"无法加载API密钥: {e}")
    GAODE_KEY = None


def geocode(address: str = "安徽省淮南市田家庵区") -> Tuple[float, float]:
    """地址转坐标, 默认使用田家庵区"""
    if not GAODE_KEY:
        raise ValueError("API密钥未加载, 无法执行地理编码")

    url: str = "https://restapi.amap.com/v3/geocode/geo"
    params: Dict[str, str] = {"key": GAODE_KEY, "address": address}
    r: Dict[str, Any] = requests.get(url, params=params, timeout=10).json()

    if r.get("status") == "1" and int(r.get("count", 0)) > 0:
        loc: str = r["geocodes"][0]["location"]
        return tuple(map(float, loc.split(",")))
    raise ValueError(f"Geocode失败: {address} - {r.get('info', '未知错误')}")


if __name__ == "__main__":
    # 当文件直接运行时执行测试代码
    print("地理编码工具")
    print("=" * 40)

    if not GAODE_KEY:
        print("错误: 无法加载API密钥, 请检查密钥文件")
        sys.exit(1)

    # 测试地址, 默认使用田家庵区
    test_address = "北京市朝阳区"
    print(f"测试地址: {test_address}")

    try:
        # 执行地理编码
        longitude, latitude = geocode(test_address)
        print(f"经度: {longitude}")
        print(f"纬度: {latitude}")
        print(f"坐标: {longitude}, {latitude}")
    except Exception as e:
        print(f"地理编码失败: {str(e)}")
        sys.exit(1)
