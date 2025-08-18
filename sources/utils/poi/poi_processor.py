"""
POI数据处理和统计模块
提供POI数据处理和统计功能，包括加权得分计算和汇总报告生成
"""

import pandas as pd
import numpy as np
import json
import sys, os
from typing import Dict, List, Tuple, Union, Any, Optional


class NumpyEncoder(json.JSONEncoder):
    """自定义JSON编码器，用于处理numpy类型"""

    def default(self, obj: Any) -> Any:
        if isinstance(
            obj,
            (
                np.int_,
                np.intc,
                np.intp,
                np.int8,
                np.int16,
                np.int32,
                np.int64,
                np.uint8,
                np.uint16,
                np.uint32,
                np.uint64,
            ),
        ):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from ..file.file_handler import save_category_stats


def calculate_weighted_score(
    poi_file: str, weight_map: Dict[str, Union[Dict[str, Any], float]]
) -> Tuple[float, int, pd.DataFrame]:
    """
    计算加权得分并生成详细统计（容错版）

    读取POI文件，根据权重映射计算加权得分，并生成大类、中类和小类的详细统计。
    该函数具有容错机制，能够处理POI数据中缺失分类信息的情况。

    处理流程：
    1. 读取POI文件（支持CSV和JSON格式）
    2. 统一列名并检查缺失列
    3. 如果缺失分类列，根据POI类型创建分类信息
    4. 根据POI类型映射权重
    5. 计算总分和POI数量
    6. 按大类、中类和小类进行分组统计

    Args:
        poi_file (str): POI文件路径，支持CSV和JSON格式
        weight_map (dict): POI类型到权重的映射字典

    Returns:
        tuple: (total_score, poi_count, category_stats)
            total_score (float): 总加权得分
            poi_count (int): POI总数
            category_stats (pandas.DataFrame): 分类统计信息
    """
    # 读取POI文件
    df: pd.DataFrame
    if poi_file.endswith(".csv"):
        df = pd.read_csv(poi_file)
    elif poi_file.endswith(".json"):
        with open(poi_file, "r", encoding="utf-8") as f:
            data: pd.DataFrame = pd.json_normalize(json.load(f))
        df = data
    else:
        raise ValueError(f"不支持的文件格式: {poi_file}")

    # 统一列名
    column_mapping: Dict[str, str] = {
        "住宅区ID": "residential_id",
        "住宅区名称": "residential_name",
        "POI类型": "poi_type",
        "POI大类": "category",
        "POI中类": "subcategory",
        "POI小类": "small_category",
        "POI名称": "name",
        "POI地址": "address",
        "经度": "longitude",
        "纬度": "latitude",
        "距离(米)": "distance",
        "默认权重": "weight",
    }

    # 重命名列
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            df = df.rename(columns={old_name: new_name})

    # 检查缺失列
    missing_columns: List[str] = []
    required_columns: List[str] = ["residential_id", "poi_type"]

    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)

    # 如果缺失分类列，尝试根据POI类型创建分类信息
    if "category" in missing_columns:
        # 根据POI类型创建分类信息
        df["category"] = df["poi_type"].apply(
            lambda x: weight_map.get(x, {}).get("大类", "")
        )
        missing_columns.remove("category")

    if "subcategory" in missing_columns:
        # 根据POI类型创建分类信息
        df["subcategory"] = df["poi_type"].apply(
            lambda x: weight_map.get(x, {}).get("中类", "")
        )
        missing_columns.remove("subcategory")

    if "small_category" in missing_columns:
        # 根据POI类型创建分类信息
        df["small_category"] = df["poi_type"].apply(
            lambda x: weight_map.get(x, {}).get("小类", "")
        )
        missing_columns.remove("small_category")

    # 如果仍然有缺失列，则使用默认值填充
    for col in missing_columns:
        if col == "residential_name":
            df[col] = "未知住宅区"
        elif col == "name":
            df[col] = "未知POI"
        elif col == "address":
            df[col] = ""
        elif col in ["longitude", "latitude", "distance"]:
            df[col] = 0
        elif col == "weight":
            df[col] = 0

    # 根据POI类型映射权重
    def get_weight(poi_type):
        # 将POI类型转换为字符串
        poi_type_str = str(poi_type)
        # 首先尝试直接获取权重值（为了向后兼容）
        direct_weight = weight_map.get(poi_type_str + "_weight", None)
        if direct_weight is not None:
            return direct_weight
        # 然后尝试从字典中获取权重值
        weight_dict = weight_map.get(poi_type_str, {})
        if isinstance(weight_dict, dict) and "权重" in weight_dict:
            return weight_dict["权重"]
        # 如果都没有找到，返回0
        return 0

    df["weight"] = df["poi_type"].apply(get_weight)

    # 计算总分和POI数量
    total_score: float = float(df["weight"].sum())
    poi_count: int = len(df)

    # 按大类、中类和小类进行分组统计
    category_stats: List[Dict[str, Any]] = []

    # 按大类统计
    # 确保category列存在
    if "category" not in df.columns:
        df["category"] = "未分类"
    category_groups = df.groupby("category")
    category: str
    group: pd.DataFrame
    for category, group in category_groups:
        category_stats.append(
            {
                "类型": "大类",
                "名称": category,
                "POI数量": len(group),
                "加权得分": group["weight"].sum(),
                "平均权重": group["weight"].mean(),
                "子类型数量": len(
                    group.get("subcategory", pd.Series(["未分类"])).unique()
                ),
            }
        )

        # 按中类统计
        # 确保subcategory列存在
        if "subcategory" not in group.columns:
            group["subcategory"] = "未分类"
        subcategory_groups = group.groupby("subcategory")
        subcategory: str
        sub_group: pd.DataFrame
        for subcategory, sub_group in subcategory_groups:
            category_stats.append(
                {
                    "类型": "中类",
                    "名称": subcategory,
                    "POI数量": len(sub_group),
                    "加权得分": sub_group["weight"].sum(),
                    "平均权重": sub_group["weight"].mean(),
                    "子类型数量": len(
                        sub_group.get("small_category", pd.Series(["未分类"])).unique()
                    ),
                }
            )

            # 按小类统计
            # 确保small_category列存在
            if "small_category" not in sub_group.columns:
                sub_group["small_category"] = "未分类"
            small_category_groups = sub_group.groupby("small_category")
            small_category: str
            small_group: pd.DataFrame
            for small_category, small_group in small_category_groups:
                if small_category:  # 确保小类不为空
                    category_stats.append(
                        {
                            "类型": "小类",
                            "名称": small_category,
                            "POI数量": len(small_group),
                            "加权得分": small_group["weight"].sum(),
                            "平均权重": small_group["weight"].mean(),
                            "子类型数量": 0,
                        }
                    )

    # 转换为DataFrame
    category_stats_df: pd.DataFrame = pd.DataFrame(category_stats)

    return total_score, poi_count, category_stats_df


def generate_score_report(
    poi_file: str,
    weight_map: Dict[str, Union[Dict[str, Any], float]],
    output_dir: str,
    residential_id: str,
) -> Tuple[float, int]:
    """
    生成得分报告

    读取POI文件，计算加权得分，并生成详细的得分报告。

    Args:
        poi_file (str): POI文件路径，支持CSV和JSON格式
        weight_map (dict): POI类型到权重的映射字典
        output_dir (str): 输出目录路径
        residential_id (str): 住宅区ID，用于生成文件名

    Returns:
        tuple: (total_score, poi_count)
            total_score (float): 总加权得分
            poi_count (int): POI总数
    """
    # 计算加权得分
    total_score: float
    poi_count: int
    category_stats: pd.DataFrame
    total_score, poi_count, category_stats = calculate_weighted_score(
        poi_file, weight_map
    )

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 保存分类统计信息
    save_category_stats(category_stats, output_dir, residential_id)

    # 保存得分结果
    score_file: str = os.path.join(output_dir, f"score_{residential_id}.csv")
    score_data: Dict[str, List[Any]] = {
        "住宅区ID": [residential_id],
        "POI总数": [poi_count],
        "加权得分": [total_score],
        "平均权重": [total_score / poi_count if poi_count > 0 else 0],
    }
    score_df: pd.DataFrame = pd.DataFrame(score_data)
    score_df.to_csv(score_file, index=False, encoding="utf-8-sig")

    # 生成汇总报告
    summary_file: str = os.path.join(output_dir, f"summary_{residential_id}.json")

    # 转换numpy类型为Python原生类型，以便JSON序列化
    def convert_numpy_types(obj: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
        if isinstance(obj, dict):
            return {key: convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (np.int64, np.float64)):
            return obj.item()
        else:
            return obj

    summary: Dict[str, Any] = {
        "residential_id": residential_id,
        "poi_count": int(poi_count),
        "total_score": float(total_score),
        "average_weight": float(total_score / poi_count if poi_count > 0 else 0),
        "category_stats": convert_numpy_types(category_stats.to_dict("records")),
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

    return total_score, poi_count
