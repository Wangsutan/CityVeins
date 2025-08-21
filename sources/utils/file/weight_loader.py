"""
权重配置加载模块
提供加载POI权重配置的功能
"""

import sys
import os
import pandas as pd
from typing import Dict, Any, Union, Optional, Final

# 添加项目根目录到Python路径
PROJECT_ROOT: Final[str] = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, PROJECT_ROOT)

try:
    from config import (
        ROOT_DIR,
        DATA_DIR,
        OUTPUT_DIR,
        KEY_FILE,
        WEIGHT_FILE,
        POI_CODE_FILE,
    )
except ImportError:
    # 如果无法导入config，使用默认路径
    DATA_DIR: Final[str] = os.path.join(PROJECT_ROOT, "data")
    WEIGHT_FILE: Final[str] = os.path.join(DATA_DIR, "poi_weights", "高德POI_加权.csv")


def load_weight_config(
    weight_file: str = WEIGHT_FILE,
) -> Optional[Dict[str, Union[Dict[str, Union[str, float]], float]]]:
    """
    加载权重配置

    从CSV文件中加载POI权重配置，优先使用客制化权重，如果没有客制化权重则使用权重。

    处理流程：
    1. 读取权重配置CSV文件
    2. 遍历每一行，提取POI类型和权重值
    3. 优先使用客制化权重，如果客制化权重为空或不存在，则使用权重
    4. 构建POI类型到权重的映射字典

    Args:
        weight_file (str): 权重配置文件路径，CSV格式

    Returns:
        Optional[dict]: POI类型到权重的映射字典，键为POI类型，值为对应的权重值，如果加载失败则返回None
    """
    df: pd.DataFrame = pd.read_csv(weight_file)
    weight_map: Dict[str, Union[Dict[str, Union[str, float]], float]] = {}

    for _, row in df.iterrows():
        poi_type: str = str(row["NEW_TYPE"])
        # 优先使用客制化权重，如果没有则使用权重
        custom_weight: Union[float, None] = row.get("客制化权重", None)
        default_weight: float = float(row["权重"])
        weight: float = custom_weight if pd.notna(custom_weight) else default_weight

        # 构建权重映射，包含所有分类信息
        weight_map[poi_type] = {
            "权重": weight,
            "大类": row.get("大类", ""),
            "中类": row.get("中类", ""),
            "小类": row.get("小类", ""),
        }

        # 同时为了向后兼容，直接存储权重值
        weight_map[poi_type + "_weight"] = weight

    return weight_map


if __name__ == "__main__":
    # 当文件直接运行时执行测试代码
    print("POI权重配置加载模块")
    print("=" * 40)

    try:
        # 加载权重配置
        weight_map = load_weight_config()
        print(f"成功加载权重配置文件: {WEIGHT_FILE}")

        # 显示前5个POI类型的权重信息
        print("\n前5个POI类型的权重信息:")
        count = 0
        for key, value in weight_map.items():
            if not key.endswith("_weight"):  # 只显示主条目，不显示_weight后缀的条目
                print(f"POI类型: {key}")
                print(f"  权重: {value['权重']}")
                print(f"  大类: {value['大类']}")
                print(f"  中类: {value['中类']}")
                print(f"  小类: {value['小类']}")
                print()
                count += 1
                if count >= 5:
                    break

    except Exception as e:
        print(f"加载权重配置失败: {str(e)}")
