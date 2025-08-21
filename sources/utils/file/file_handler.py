"""
文件处理模块
提供读取和保存CSV/JSON文件的功能
"""

import pandas as pd
import json
import os
from typing import Dict, List, Any, Union, Optional, Final


def read_poi_file(poi_file: str) -> Optional[pd.DataFrame]:
    """
    读取POI文件（支持CSV和JSON格式）

    根据文件扩展名自动判断文件格式，并读取POI数据。

    Args:
        poi_file (str): POI文件路径，支持CSV和JSON格式

    Returns:
        Optional[pandas.DataFrame]: 包含POI数据的DataFrame，如果读取失败则返回None

    Raises:
        ValueError: 当文件格式不支持时抛出此异常
    """
    if poi_file.endswith(".csv"):
        return pd.read_csv(poi_file)
    elif poi_file.endswith(".json"):
        with open(poi_file, "r", encoding="utf-8") as f:
            data: Any = json.load(f)
            return pd.DataFrame(data)
    else:
        raise ValueError(f"不支持的文件格式: {poi_file}")


def save_poi_file(poi_data: pd.DataFrame, output_file: str) -> None:
    """
    保存POI文件（支持CSV和JSON格式）

    根据文件扩展名自动判断文件格式，并保存POI数据。

    Args:
        poi_data (pandas.DataFrame): POI数据
        output_file (str): 输出文件路径，支持CSV和JSON格式

    Raises:
        ValueError: 当文件格式不支持时抛出此异常
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if output_file.endswith(".csv"):
        poi_data.to_csv(output_file, index=False, encoding="utf-8")
    elif output_file.endswith(".json"):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(poi_data.to_dict("records"), f, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"不支持的文件格式: {output_file}")


def save_category_stats(
    big_category: pd.DataFrame,
    mid_category: pd.DataFrame,
    small_category: pd.DataFrame,
    output_dir: str,
    residential_id: str,
) -> None:
    """
    保存分类统计信息（支持CSV和JSON格式）

    将分类统计信息保存为CSV和JSON格式。

    Args:
        big_category (pandas.DataFrame): 大类统计数据
        mid_category (pandas.DataFrame): 中类统计数据
        small_category (pandas.DataFrame): 小类统计数据
        output_dir (str): 输出目录路径
        residential_id (str): 住宅区ID，用于生成文件名
    """
    os.makedirs(output_dir, exist_ok=True)

    # 合并所有分类统计数据
    all_stats = pd.concat(
        [big_category, mid_category, small_category], ignore_index=True
    )

    # 保存CSV格式
    csv_file: Final[str] = os.path.join(output_dir, f"stats_{residential_id}.csv")
    all_stats.to_csv(csv_file, index=False, encoding="utf-8")

    # 保存JSON格式
    json_file: Final[str] = os.path.join(output_dir, f"stats_{residential_id}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_stats.to_dict("records"), f, ensure_ascii=False, indent=2)
