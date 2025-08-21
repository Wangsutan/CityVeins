"""
地理编码工具模块
提供地址转坐标的功能
"""

import requests
import sys, os
from typing import Dict, Any, Optional, Tuple, Callable, Final, Union

# 处理导入问题
try:
    # 获取项目根目录的绝对路径
    PROJECT_ROOT: Final[str] = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    sys.path.insert(0, PROJECT_ROOT)

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
        ROOT_DIR: Final[str] = PROJECT_ROOT
        DATA_DIR: Final[str] = os.path.join(ROOT_DIR, "data")
        OUTPUT_DIR: Final[str] = os.path.join(ROOT_DIR, "output")
        KEY_FILE: Final[str] = os.path.join(ROOT_DIR, "data", "key", "key.txt")
        WEIGHT_FILE: Final[str] = os.path.join(
            ROOT_DIR, "data", "poi_weights", "高德POI_加权.csv"
        )
        POI_CODE_FILE: Final[str] = os.path.join(
            ROOT_DIR,
            "data",
            "poi_code",
            "高德POI分类与编码（中英文）_V1.06_20230208.csv",
        )
        RESIDENTIAL_OUT: Callable[[str], str] = lambda d: os.path.join(
            ROOT_DIR, "data", "residential", f"residential_{d}.csv"
        )
        POI_OUT: Callable[[str], str] = lambda rid: os.path.join(
            ROOT_DIR, "output", "poi", f"poi_{rid}.csv"
        )

    # 尝试导入key_loader
    try:
        from ..file.key_loader import load_key
    except (ImportError, ValueError):
        # 如果相对导入失败，尝试直接导入key_loader模块
        key_loader_path: str = os.path.join(PROJECT_ROOT, "sources", "utils", "file")
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

    GAODE_KEY: Optional[str] = load_key(KEY_FILE)
except Exception as e:
    print(f"无法加载API密钥: {e}")
    GAODE_KEY: Optional[str] = None


def geocode(address: str = "安徽省淮南市田家庵区") -> Tuple[float, float]:
    """地址转坐标, 默认使用田家庵区"""
    if not GAODE_KEY:
        raise ValueError("API密钥未加载, 无法执行地理编码")

    url: str = "https://restapi.amap.com/v3/geocode/geo"
    params: Dict[str, str] = {"key": GAODE_KEY, "address": address}
    response: requests.Response = requests.get(url, params=params, timeout=10)
    r: Dict[str, Any] = response.json()

    if r.get("status") == "1" and int(r.get("count", 0)) > 0:
        loc: str = r["geocodes"][0]["location"]
        loc_parts = loc.split(",")
        if len(loc_parts) >= 2:
            lng, lat = float(loc_parts[0]), float(loc_parts[1])
            return (lng, lat)
        else:
            raise ValueError(f"位置格式不正确: {loc}")
    raise ValueError(f"Geocode失败: {address} - {r.get('info', '未知错误')}")


if __name__ == "__main__":
    # 当文件直接运行时执行测试代码
    print("地理编码工具")
    print("=" * 40)

    if not GAODE_KEY:
        print("错误: 无法加载API密钥, 请检查密钥文件")
        sys.exit(1)

    test_address: str = "北京市朝阳区"
    print(f"测试地址: {test_address}")

    try:
        # 执行地理编码
        longitude: float
        latitude: float
        longitude, latitude = geocode(test_address)
        print(f"经度: {longitude}")
        print(f"纬度: {latitude}")
        print(f"坐标: {longitude}, {latitude}")
    except Exception as e:
        print(f"地理编码失败: {str(e)}")
        sys.exit(1)
