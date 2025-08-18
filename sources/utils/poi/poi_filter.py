#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POI权重过滤模块

该模块负责处理POI权重的过滤和查询逻辑, 包括:
1. 根据权重阈值过滤POI类型
2. 确定查询时使用的POI类型代码(NEW_TYPE)
3. 避免重复请求
4. 输出保留的大类信息

NEW_TYPE编码特点:
- 6位编码: 前2位是大类代码, 中间2位是中类代码, 后2位是小类代码
- 不足6位的按6位理解
- 单独的大类代码后面四位都是0
- 单独的中类代码后面2位都是0
- 小类代码从01开始编号

使用示例:
from sources.utils.poi.poi_filter import filter_poi_types
filtered_types, kept_categories = filter_poi_types(poi_types_file)
"""

import os
import pandas as pd
from typing import Dict, List, Tuple, Set, Any, Optional, Union
from collections import defaultdict

# 导入配置文件中的权重文件路径
try:
    from config import WEIGHT_FILE
except ImportError:
    # 如果无法导入配置文件，则使用默认路径
    ROOT_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    WEIGHT_FILE = os.path.join(ROOT_DIR, "data", "poi_weights", "高德POI_加权.csv")


def build_category_hierarchy(df: pd.DataFrame) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    构建大类-中类-小类层级结构

    参数:
    df : pandas.DataFrame - 包含分类数据的DataFrame

    返回:
    dict - 嵌套字典结构 {大类代码: {中类代码: {小类代码: 名称}}}
    """
    # 初始化三层嵌套字典
    category_tree = defaultdict(lambda: defaultdict(lambda: {}))

    # 遍历每一行数据
    for _, row in df.iterrows():
        # 将NEW_TYPE转换为6位字符串（左侧补零）
        full_code = str(row["NEW_TYPE"]).zfill(6)

        # 分解代码
        big_code = full_code[:2]  # 大类代码
        mid_code = full_code[2:4]  # 中类代码
        sub_code = full_code[4:6]  # 小类代码

        # 获取中文名称（根据编码级别）
        if mid_code == "00" and sub_code == "00":  # 大类级别
            name = row["大类"]
        elif sub_code == "00":  # 中类级别
            name = row["中类"]
        else:  # 小类级别
            name = row["小类"]

        # 更新层级结构
        category_tree[big_code][mid_code][sub_code] = name

    return dict(category_tree)


def filter_poi_types(
    poi_types_file: str,
    filter_category: bool = True,
    filter_subcategory: bool = False,
    filter_smallcategory: bool = False,
    category_threshold: float = 0.4,
    subcategory_threshold: float = 0.4,
    smallcategory_threshold: float = 0.4,
) -> Tuple[List[str], Set[str], Dict[str, Dict[str, Union[str, float]]]]:
    """
    过滤POI类型, 根据权重和类别进行筛选

    处理流程:
    1. 读取POI分类体系CSV文件
    2. 根据NEW_TYPE解析大类、中类和小类代码
    3. 根据大类权重筛选, 大类权重低则不考虑其中的中类和小类
    4. 如果筛选中类, 则根据中类权重筛选, 中类权重低则不考虑其中的小类
    5. 如果筛选小类, 则根据小类权重筛选
    6. 确定查询时使用的POI类型代码(NEW_TYPE)
    7. 避免重复请求
    8. 输出保留的大类信息

    Args:
        poi_types_file (str): POI分类体系CSV文件路径
        filter_category (bool): 是否筛选大类, 默认为True
        filter_subcategory (bool): 是否筛选中类, 默认为False
        filter_smallcategory (bool): 是否筛选小类, 默认为False
        category_threshold (float): 大类权重阈值, 默认为0.4
        subcategory_threshold (float): 中类权重阈值, 默认为0.4
        smallcategory_threshold (float): 小类权重阈值, 默认为0.4

    Returns:
        tuple: (filtered_types, kept_categories, type_mapping)
            filtered_types (list): 过滤后的POI类型代码列表, 用于查询
            kept_categories (set): 保留的大类集合
            type_mapping (dict): POI类型编码到分类信息的映射字典
    """
    # 读取POI分类体系
    df: pd.DataFrame = pd.read_csv(poi_types_file)

    # 构建分类层级结构
    category_tree = build_category_hierarchy(df)

    # 创建权重字典，便于快速查找
    weight_dict: Dict[str, float] = {}
    for _, row in df.iterrows():
        weight_dict[str(row["NEW_TYPE"]).zfill(6)] = row["权重"]

    # 初始化结果集合
    valid_big_codes: Set[str] = set()
    valid_mid_codes: Set[str] = set()
    valid_sub_codes: Set[str] = set()

    # 第一步：根据大类权重筛选
    if filter_category:
        # 遍历所有大类代码
        for big_code in category_tree:
            # 构建大类NEW_TYPE (XX0000)
            big_type = big_code + "0000"
            # 检查权重
            if big_type in weight_dict and weight_dict[big_type] >= category_threshold:
                valid_big_codes.add(big_code)
                # 如果大类有效，则其下所有中类和小类都暂定为有效
                for mid_code in category_tree[big_code]:
                    valid_mid_codes.add(big_code + mid_code)
                    for sub_code in category_tree[big_code][mid_code]:
                        valid_sub_codes.add(big_code + mid_code + sub_code)
    else:
        # 不筛选大类，所有大类都有效
        for big_code in category_tree:
            valid_big_codes.add(big_code)
            for mid_code in category_tree[big_code]:
                valid_mid_codes.add(big_code + mid_code)
                for sub_code in category_tree[big_code][mid_code]:
                    valid_sub_codes.add(big_code + mid_code + sub_code)

    # 第二步：如果筛选中类，则根据中类权重筛选
    if filter_subcategory:
        # 重置中类和小类有效集合
        valid_mid_codes: Set[str] = set()
        valid_sub_codes: Set[str] = set()

        # 只考虑有效大类下的中类
        for big_code in valid_big_codes:
            for mid_code in category_tree[big_code]:
                # 构建中类NEW_TYPE (XXYY00)
                mid_type = big_code + mid_code + "00"
                # 检查权重
                if (
                    mid_type in weight_dict
                    and weight_dict[mid_type] >= subcategory_threshold
                ):
                    valid_mid_codes.add(big_code + mid_code)
                    # 如果中类有效，则其下所有小类都有效
                    for sub_code in category_tree[big_code][mid_code]:
                        valid_sub_codes.add(big_code + mid_code + sub_code)

    # 第三步：如果筛选小类，则根据小类权重筛选
    if filter_smallcategory:
        # 重置小类有效集合
        valid_sub_codes: Set[str] = set()

        # 只考虑有效中类下的小类
        for big_mid_code in valid_mid_codes:
            big_code = big_mid_code[:2]
            mid_code = big_mid_code[2:4]

            for sub_code in category_tree[big_code][mid_code]:
                # 构建小类NEW_TYPE (XXYYZZ)
                sub_type = big_code + mid_code + sub_code
                # 检查权重
                if (
                    sub_type in weight_dict
                    and weight_dict[sub_type] >= smallcategory_threshold
                ):
                    valid_sub_codes.add(big_code + mid_code + sub_code)

    # 根据筛选结果构建DataFrame
    filtered_rows = []
    for _, row in df.iterrows():
        new_type = str(row["NEW_TYPE"]).zfill(6)
        # 判断是否应该保留该记录
        should_keep = False

        # 提取代码部分
        big_code = new_type[:2]
        mid_code = new_type[2:4]
        sub_code = new_type[4:6]

        # 检查是否为小类级别
        if mid_code != "00" and sub_code != "00":
            should_keep = (big_code + mid_code + sub_code) in valid_sub_codes
        # 检查是否为中类级别
        elif mid_code != "00" and sub_code == "00":
            should_keep = (big_code + mid_code) in valid_mid_codes
        # 检查是否为大类级别
        else:
            should_keep = big_code in valid_big_codes

        if should_keep:
            # 添加解析后的代码信息
            filtered_rows.append(
                {
                    **row.to_dict(),
                    "大类代码": big_code + "0000",
                    "中类代码": big_code + mid_code + "00",
                    "小类代码": new_type,
                }
            )

    # 创建筛选后的DataFrame
    filtered_df: pd.DataFrame = pd.DataFrame(filtered_rows)

    # 确定查询时使用的POI类型代码（使用NEW_TYPE）
    filtered_df = filtered_df.copy()  # 避免SettingWithCopyWarning
    filtered_df.loc[:, "查询代码"] = filtered_df["NEW_TYPE"]

    # 去重，避免重复请求
    filtered_df: pd.DataFrame = filtered_df.drop_duplicates("查询代码")

    # 获取过滤后的POI类型代码列表
    filtered_types: List[str] = filtered_df["查询代码"].tolist()

    # 获取保留的大类集合
    kept_categories: Set[str] = set(filtered_df["大类"].unique())

    # 构建POI类型编码到分类信息的映射字典
    type_mapping: Dict[str, Dict[str, Union[str, float]]] = {}
    for _, row in filtered_df.iterrows():
        type_mapping[row["查询代码"]] = {
            "大类": row["大类"],
            "中类": row["中类"],
            "小类": row["小类"],
            "权重": row["权重"],
            "NEW_TYPE": row["NEW_TYPE"],
            "大类代码": row["大类代码"],
            "中类代码": row["中类代码"],
            "小类代码": row["小类代码"],
        }

    return filtered_types, kept_categories, type_mapping


def get_poi_type_stats(
    type_mapping: Dict[str, Dict[str, Union[str, float]]],
    filtered_types: List[str],
    kept_categories: Set[str],
) -> List[Dict[str, Union[str, int]]]:
    """
    获取POI类型统计信息

    Args:
        type_mapping (dict): POI类型编码到分类信息的映射字典
        filtered_types (list): 过滤后的POI类型代码列表
        kept_categories (set): 保留的大类集合

    Returns:
        list: POI类型统计信息列表，每个元素是一个包含统计信息的字典
    """
    stats: List[Dict[str, Union[str, int]]] = []

    # 按大类统计
    for category in kept_categories:
        # 获取该大类下的所有POI类型
        category_types: List[str] = [
            t for t in filtered_types if type_mapping[t]["大类"] == category
        ]
        # 获取该大类下的所有中类
        subcategories: Set[str] = set(type_mapping[t]["中类"] for t in category_types)

        # 添加大类统计
        stats.append(
            {
                "类型": "大类",
                "名称": category,
                "数量": len(category_types),
                "子类型数量": len(subcategories),
            }
        )

        # 按中类统计
        for subcategory in subcategories:
            # 获取该中类下的所有POI类型
            subcategory_types: List[str] = [
                t for t in category_types if type_mapping[t]["中类"] == subcategory
            ]
            # 获取该中类下的所有小类
            small_categories: Set[str] = set(
                type_mapping[t]["小类"]
                for t in subcategory_types
                if pd.notna(type_mapping[t]["小类"]) and type_mapping[t]["小类"] != ""
            )

            # 添加中类统计
            stats.append(
                {
                    "类型": "中类",
                    "名称": subcategory,
                    "数量": len(subcategory_types),
                    "子类型数量": len(small_categories),
                }
            )

            # 按小类统计
            for small_category in small_categories:
                if small_category:  # 确保小类不为空
                    # 获取该小类下的所有POI类型
                    small_category_types: List[str] = [
                        t
                        for t in subcategory_types
                        if type_mapping[t]["小类"] == small_category
                    ]

                    # 添加小类统计
                    stats.append(
                        {
                            "类型": "小类",
                            "名称": small_category,
                            "数量": len(small_category_types),
                            "子类型数量": 0,
                        }
                    )

    return stats


if __name__ == "__main__":
    # 使用配置文件中的POI权重文件路径
    poi_types_file: str = WEIGHT_FILE

    # 使用默认设置（筛选大类但不筛选中类和小类）
    print("使用默认设置（筛选大类但不筛选中类和小类）:")
    filtered_types: List[str]
    kept_categories: Set[str]
    type_mapping: Dict[str, Dict[str, Union[str, float]]]
    filtered_types, kept_categories, type_mapping = filter_poi_types(poi_types_file)

    # 获取统计信息
    stats: List[Dict[str, Union[str, int]]] = get_poi_type_stats(
        type_mapping, filtered_types, kept_categories
    )

    # 输出结果
    print(f"过滤后的POI类型数量: {len(filtered_types)}")
    print(f"保留的大类数量: {len(kept_categories)}")
    print(f"保留的大类: {kept_categories}")

    # 输出统计信息
    print("\n统计信息:")
    for stat in stats:
        if stat["类型"] == "大类":
            print()  # 大类前添加空行
            # 获取该大类的NEW_TYPE和权重
            big_code = None
            big_weight = None
            for t in filtered_types:
                # 大类特征：NEW_TYPE末尾4位为0
                new_type_str = str(type_mapping[t]["NEW_TYPE"])
                if (
                    type_mapping[t]["大类"] == stat["名称"]
                    and new_type_str[-4:] == "0000"
                ):
                    big_code = type_mapping[t]["NEW_TYPE"]
                    big_weight = type_mapping[t]["权重"]
                    break
            print(
                f"{stat['类型']}: {stat['名称']}, NEW_TYPE: {big_code}, 权重: {big_weight}, 数量: {stat['数量']}, 子类型数量: {stat['子类型数量']}"
            )
        elif stat["类型"] == "中类":
            print()  # 中类前添加空行
            # 获取该中类的NEW_TYPE和权重
            mid_code = None
            mid_weight = None
            for t in filtered_types:
                # 中类特征：NEW_TYPE末尾2位为0，但非0000
                new_type_str = str(type_mapping[t]["NEW_TYPE"])
                if (
                    type_mapping[t]["中类"] == stat["名称"]
                    and new_type_str[-2:] == "00"
                    and new_type_str[-4:] != "0000"
                ):
                    mid_code = type_mapping[t]["NEW_TYPE"]
                    mid_weight = type_mapping[t]["权重"]
                    break
            print(
                f"{stat['类型']}: {stat['名称']}, NEW_TYPE: {mid_code}, 权重: {mid_weight}, 数量: {stat['数量']}, 子类型数量: {stat['子类型数量']}"
            )
        else:
            # 获取该小类的NEW_TYPE和权重
            small_code = None
            small_weight = None
            for t in filtered_types:
                if type_mapping[t]["小类"] == stat["名称"]:
                    small_code = type_mapping[t]["NEW_TYPE"]
                    small_weight = type_mapping[t]["权重"]
                    break
            print(
                f"{stat['类型']}: {stat['名称']}, NEW_TYPE: {small_code}, 权重: {small_weight}, 数量: {stat['数量']}, 子类型数量: {stat['子类型数量']}"
            )

    # 尝试不同的筛选设置
    print("\n使用不同设置（筛选大类和中类但不筛选小类）:")
    filtered_types2: List[str]
    kept_categories2: Set[str]
    type_mapping2: Dict[str, Dict[str, Union[str, float]]]
    filtered_types2, kept_categories2, type_mapping2 = filter_poi_types(
        poi_types_file,
        filter_category=True,
        filter_subcategory=True,
        filter_smallcategory=False,
    )

    print(f"过滤后的POI类型数量: {len(filtered_types2)}")
    print(f"保留的大类数量: {len(kept_categories2)}")
