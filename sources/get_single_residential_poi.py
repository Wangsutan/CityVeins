"""
获取单个住宅区15分钟生活圈全量POI数据

该模块负责获取单个住宅区周边指定半径内的所有POI数据, 基于高德地图API和分类体系。
支持全量POI类型获取, 并将结果保存为CSV和JSON格式, 便于后续处理和分析。

功能：
1. 地址转坐标：将住宅区地址转换为经纬度坐标
2. POI分类体系加载：从配置文件加载POI分类体系和权重信息
3. 周边POI获取：获取指定半径内所有类型的POI数据
4. 数据格式化与保存：将获取的POI数据格式化并保存为CSV和JSON文件

依赖模块：
- requests: HTTP请求库, 用于调用高德地图API
- pandas: 数据处理和保存
- tqdm: 进度条显示
- utils.key_loader: API密钥加载工具
- config: 项目配置文件

使用示例:
python get_single_residential_poi.py B0J2DUYF0J
python get_single_residential_poi.py B0J2DUYF0J 淮南职业技术学院 洞山西路2号
"""

import requests
import pandas as pd
from tqdm import tqdm
import time
import sys
import os
from sources.utils.poi.poi_dedup import dedup_poi_file
import os
import json
import argparse
from typing import Dict, List, Any, Optional, Tuple, Set, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *
from sources.utils.file.key_loader import load_key
from sources.utils.poi.poi_filter import filter_poi_types
from sources.utils import geocode
from sources.utils.residential import get_residential_info

# 配置参数
GAODE_KEY: str = load_key(KEY_FILE)
RADIUS: int = 1200
OUTPUT_DIR: str = OUTPUT_DIR
POI_TYPES_FILE: str = WEIGHT_FILE  # POI分类权重文件
# POI过滤开关，默认开启，过滤掉权重较低且非生活常规需要的POI类型
FILTER_LOW_WEIGHT_POI: bool = True
# 权重阈值，低于此值的POI类型将被过滤掉（当FILTER_LOW_WEIGHT_POI为True时）
POI_WEIGHT_THRESHOLD: float = 0.4
# POI筛选级别配置，默认只筛选大类，不筛选中类和小类
FILTER_CATEGORY: bool = True
FILTER_SUBCATEGORY: bool = False
FILTER_SMALLCATEGORY: bool = False


def load_poi_types() -> (
    Tuple[List[str], Set[str], Dict[str, Dict[str, Union[str, float]]]]
):
    """
    加载POI分类体系并过滤POI类型

    从CSV文件中加载POI分类体系和权重信息, 使用poi_filter模块进行过滤。
    根据FILTER_LOW_WEIGHT_POI开关和POI_WEIGHT_THRESHOLD阈值，过滤掉低权重的POI类型。
    动态调整特定类别的权重，将汽车服务、汽车销售、汽车维修、摩托车服务、生活服务（除了邮局和物流速递）、住宿服务和餐饮服务的权重调低到0.3以下。
    先判断大类，大类如果权重低，就不再考虑其中的小类。

    处理流程：
    1. 使用poi_filter模块过滤POI类型
    2. 获取过滤后的POI类型列表和保留的大类集合
    3. 获取POI类型映射

    Returns:
        tuple: (filtered_types, kept_categories, type_mapping)
            filtered_types (list): 过滤后的POI类型代码列表，用于查询
            kept_categories (set): 保留的大类集合
            type_mapping (dict): POI类型编码到分类信息的映射字典
    """
    # 使用poi_filter模块过滤POI类型
    filtered_types: List[str]
    kept_categories: Set[str]
    type_mapping: Dict[str, Dict[str, Union[str, float]]]

    # 根据FILTER_LOW_WEIGHT_POI设置是否进行筛选
    if FILTER_LOW_WEIGHT_POI:
        # 如果需要过滤低权重POI，则使用权重阈值
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            POI_TYPES_FILE,
            filter_category=True,
            filter_subcategory=True,
            filter_smallcategory=True,
            category_threshold=POI_WEIGHT_THRESHOLD,
            subcategory_threshold=POI_WEIGHT_THRESHOLD,
            smallcategory_threshold=POI_WEIGHT_THRESHOLD,
        )
    else:
        # 如果不需要过滤低权重POI，则获取所有POI类型
        filtered_types, kept_categories, type_mapping = filter_poi_types(
            POI_TYPES_FILE,
            filter_category=False,
            filter_subcategory=False,
            filter_smallcategory=False,
        )

    return filtered_types, kept_categories, type_mapping


def get_pois(
    lng: float, lat: float, poi_type: str, max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    获取指定类型的所有POI

    通过高德地图周边搜索API, 获取指定坐标点周围指定半径内某一类型的所有POI数据。
    支持分页获取, 确保获取所有符合条件的POI。

    处理流程：
    1. 构建API请求参数
    2. 循环获取每一页的POI数据
    3. 检查响应状态, 失败则重试
    4. 将POI数据添加到结果列表
    5. 如果返回的POI数量少于请求的数量, 说明已经是最后一页, 退出循环
    6. 增加页码并短暂等待后继续获取下一页

    Args:
        lng (float): 中心点经度
        lat (float): 中心点纬度
        poi_type (str): POI类型代码
        max_retries (int): 最大重试次数，默认为3

    Returns:
        list[dict]: POI数据列表, 每个元素是一个包含POI信息的字典

    Raises:
        Exception: 当获取POI数据失败且超过最大重试次数时抛出异常
    """
    pois: List[Dict[str, Any]] = []
    page: int = 1
    retry_count: int = 0

    while True:
        try:
            url: str = "https://restapi.amap.com/v3/place/around"
            params: Dict[str, Any] = {
                "key": GAODE_KEY,
                "location": f"{lng},{lat}",
                "types": poi_type,
                "radius": RADIUS,
                "page": page,
                "offset": 25,
            }
            resp: requests.Response = requests.get(url, params=params, timeout=10)
            resp_json: Dict[str, Any] = resp.json()

            if resp_json.get("status") != "1":
                raise Exception(f"API返回错误: {resp_json.get('info', '未知错误')}")

            page_pois: List[Dict[str, Any]] = resp_json.get("pois", [])
            pois.extend(page_pois)
            if len(page_pois) < 25:
                break

            page += 1
            retry_count = 0  # 重置重试计数
            time.sleep(0.1)

        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f"获取POI数据失败 (类型: {poi_type}): {str(e)}")

            print(
                f"获取POI数据失败 (类型: {poi_type}), 重试 {retry_count}/{max_retries}: {str(e)}"
            )
            time.sleep(2)  # 失败后等待更长时间

    return pois


def main(residential_id: str, name: str, address: str) -> None:
    """
    主处理函数

    获取指定住宅区周边的所有POI数据, 并保存为CSV和JSON格式。
    按优先级抓取POI数据：优先抓取小类，其次中类，最后大类。
    支持断点续传，失败的类别会被删除。

    处理流程：
    1. 创建输出目录和临时目录
    2. 加载POI分类体系
    3. 将住宅区地址转换为经纬度坐标
    4. 按优先级（小类->中类->大类）获取POI数据
    5. 格式化POI数据, 添加分类信息和权重
    6. 将结果保存为CSV和JSON格式文件
    7. 处理异常情况, 失败时删除可能不完整的文件

    Args:
        residential_id (str): 住宅区ID
        name (str): 住宅区名称
        address (str): 住宅区地址

    Returns:
        None: 结果直接保存到文件
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 创建临时目录用于存储每个类别的POI数据
    temp_dir: str = os.path.join(OUTPUT_DIR, f"temp_{residential_id}")
    os.makedirs(temp_dir, exist_ok=True)

    output_file: str = os.path.join(OUTPUT_DIR, f"poi_{residential_id}.csv")

    try:
        # 加载POI分类体系并过滤POI类型
        filtered_types: List[str]
        kept_categories: Set[str]
        type_mapping: Dict[str, Dict[str, Union[str, float]]]
        filtered_types, kept_categories, type_mapping = load_poi_types()

        lng: float
        lat: float
        lng, lat = geocode(address)

        # 按优先级分类POI类型：小类 -> 中类 -> 大类
        smallcategory_types = []
        subcategory_types = []
        category_types = []

        # 建立类别映射关系
        category_to_subcategories = {}  # 大类 -> 中类列表
        subcategory_to_smallcategories = {}  # 中类 -> 小类列表

        # 先遍历所有类型，建立类别映射关系
        for type_code in filtered_types:
            type_info = type_mapping.get(type_code, {})
            category = type_info.get("大类", "")
            subcategory = type_info.get("中类", "")
            smallcategory = type_info.get("小类", "")

            # 建立大类到中类的映射
            if category and subcategory:
                if category not in category_to_subcategories:
                    category_to_subcategories[category] = set()
                category_to_subcategories[category].add(subcategory)

            # 建立中类到小类的映射
            if subcategory and smallcategory:
                if subcategory not in subcategory_to_smallcategories:
                    subcategory_to_smallcategories[subcategory] = set()
                subcategory_to_smallcategories[subcategory].add(smallcategory)

            # 分类POI类型
            if smallcategory:
                smallcategory_types.append(type_code)
            elif subcategory:
                subcategory_types.append(type_code)
            elif category:
                category_types.append(type_code)

        # 按优先级处理POI类型
        all_types = []
        processed_categories = set()  # 记录已处理的大类
        processed_subcategories = set()  # 记录已处理的中类

        # 1. 处理小类
        for type_code in smallcategory_types:
            type_info = type_mapping.get(type_code, {})
            category = type_info.get("大类", "")
            subcategory = type_info.get("中类", "")

            # 标记这个大类和中类已处理
            if category:
                processed_categories.add(category)
            if subcategory:
                processed_subcategories.add(subcategory)

            all_types.append(type_code)

        # 2. 处理未覆盖的中类
        for type_code in subcategory_types:
            type_info = type_mapping.get(type_code, {})
            category = type_info.get("大类", "")
            subcategory = type_info.get("中类", "")

            # 如果这个中类存在且未被小类覆盖，则添加到处理列表
            if subcategory and subcategory not in processed_subcategories:
                # 检查这个中类下是否有小类
                has_smallcategory = (
                    subcategory in subcategory_to_smallcategories
                    and len(subcategory_to_smallcategories[subcategory]) > 0
                )

                # 只有当中类下没有小类，或者小类都获取失败时，才处理这个中类
                if not has_smallcategory:
                    if category:
                        processed_categories.add(category)
                    processed_subcategories.add(subcategory)
                    all_types.append(type_code)

        # 3. 处理未覆盖的大类
        for type_code in category_types:
            type_info = type_mapping.get(type_code, {})
            category = type_info.get("大类", "")

            # 如果这个大类存在且未被小类或中类覆盖，则添加到处理列表
            if category and category not in processed_categories:
                # 检查这个大类下是否有中类
                has_subcategory = (
                    category in category_to_subcategories
                    and len(category_to_subcategories[category]) > 0
                )

                # 只有当大类下没有中类，或者中类都获取失败时，才处理这个大类
                if not has_subcategory:
                    processed_categories.add(category)
                    all_types.append(type_code)

        # 统计实际会被处理的各类别数量
        processed_smallcategory_count = len(smallcategory_types)
        processed_subcategory_count = len(
            [
                t
                for t in subcategory_types
                if type_mapping.get(t, {}).get("中类") in processed_subcategories
            ]
        )
        processed_category_count = len(
            [
                t
                for t in category_types
                if type_mapping.get(t, {}).get("大类") in processed_categories
            ]
        )

        print(
            f"按优先级排序后的POI类型: 小类({processed_smallcategory_count}) -> 中类({processed_subcategory_count}) -> 大类({processed_category_count})"
        )

        # 处理每个POI类型
        success_count = 0
        fail_count = 0

        # 进度条显示
        pbar: tqdm = tqdm(all_types, desc=f"获取POI: {name[:15]}")

        for type_code in pbar:
            type_info: Dict[str, Union[str, float]] = type_mapping.get(type_code, {})
            type_name = (
                type_info.get("小类")
                or type_info.get("中类")
                or type_info.get("大类", "未知")
            )
            pbar.set_postfix(类型=type_name[:10])

            # 每个类型的临时文件
            type_file: str = os.path.join(temp_dir, f"{type_code}.csv")

            try:
                # 获取POI数据
                pois = get_pois(lng, lat, type_code)

                if pois:
                    # 格式化POI数据
                    type_records = []
                    for poi in pois:
                        type_records.append(
                            {
                                "住宅区ID": residential_id,
                                "住宅区名称": name,
                                "POI类型": type_code,
                                "POI大类": type_info.get("大类", ""),
                                "POI中类": type_info.get("中类", ""),
                                "POI小类": type_info.get("小类", ""),
                                "POI名称": poi["name"],
                                "POI地址": poi.get("address", ""),
                                "经度": poi["location"].split(",")[0],
                                "纬度": poi["location"].split(",")[1],
                                "距离(米)": poi["distance"],
                                "默认权重": type_info.get("权重", 0),
                            }
                        )

                    # 保存到临时文件
                    type_df = pd.DataFrame(type_records)
                    type_df.to_csv(type_file, index=False, encoding="utf-8-sig")
                    success_count += 1
                else:
                    # 不创建空文件，只记录成功处理
                    success_count += 1

            except Exception as e:
                print(f"\n处理POI类型 {type_code} ({type_name}) 失败: {str(e)}")
                # 删除可能存在的临时文件
                if os.path.exists(type_file):
                    os.remove(type_file)
                fail_count += 1

        # 合并所有成功的POI数据
        records: List[Dict[str, Any]] = []
        for type_code in all_types:
            type_file = os.path.join(temp_dir, f"{type_code}.csv")
            if os.path.exists(type_file):
                try:
                    type_df = pd.read_csv(type_file)
                    if not type_df.empty:
                        records.extend(type_df.to_dict("records"))
                except Exception as e:
                    print(f"读取POI类型 {type_code} 的数据失败: {str(e)}")

        # 清理临时目录
        import shutil

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        if records:
            df: pd.DataFrame = pd.DataFrame(records)
            df.to_csv(output_file, index=False, encoding="utf-8-sig")
            print(
                f"成功生成: {output_file} (共 {len(records)} 条POI, 成功处理 {success_count} 种类型, 失败 {fail_count} 种类型)"
            )

            # 对生成的POI数据进行去重
            try:
                dedup_poi_file(output_file)
                print(f"POI数据去重完成")
            except Exception as e:
                print(f"POI数据去重失败: {str(e)}")

            # 同时保存JSON格式以便后续处理
            json_file: str = os.path.join(OUTPUT_DIR, f"poi_{residential_id}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            print(f"同时生成JSON格式: {json_file}")

        else:
            print(f"⚠️ 未找到POI数据: {name}")

    except Exception as e:
        print(f"处理失败[{residential_id}]: {str(e)}")
        # 清理临时目录
        import shutil

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        # 删除可能不完整的输出文件
        if os.path.exists(output_file):
            os.remove(output_file)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="获取单个住宅区15分钟生活圈全量POI数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python get_single_residential_poi.py B0J2DUYF0J
  python get_single_residential_poi.py B0J2DUYF0J 淮南职业技术学院 洞山西路2号
  python get_single_residential_poi.py B0J2DUYF0J --no-filter
  python get_single_residential_poi.py B0J2DUYF0J --filter-level=subcategory
  python get_single_residential_poi.py B0J2DUYF0J --threshold=0.5""",
    )

    parser.add_argument("residential_id", help="住宅区ID")
    parser.add_argument("name", nargs="?", help="住宅区名称 (可选)")
    parser.add_argument("address", nargs="?", help="住宅区地址 (可选)")
    parser.add_argument(
        "--no-filter", action="store_true", help="禁用POI过滤，获取所有类型的POI数据"
    )
    parser.add_argument(
        "--filter-level",
        choices=["category", "subcategory", "smallcategory"],
        default="category",
        help="设置POI筛选级别 (默认: category)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="设置权重阈值，0.0-1.0之间的浮点数 (默认: 0.4)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # 解析命令行参数
    args = parse_args()

    # 根据参数设置全局变量
    if args.no_filter:
        FILTER_LOW_WEIGHT_POI = False
        print("POI过滤已禁用，将获取所有类型的POI数据")

    POI_WEIGHT_THRESHOLD = args.threshold
    print(f"设置权重阈值为: {POI_WEIGHT_THRESHOLD}")

    # 根据筛选级别设置筛选参数
    if args.filter_level == "category":
        FILTER_CATEGORY, FILTER_SUBCATEGORY, FILTER_SMALLCATEGORY = True, False, False
        print("筛选级别设置为: 大类")
    elif args.filter_level == "subcategory":
        FILTER_CATEGORY, FILTER_SUBCATEGORY, FILTER_SMALLCATEGORY = True, True, False
        print("筛选级别设置为: 大类和中类")
    elif args.filter_level == "smallcategory":
        FILTER_CATEGORY, FILTER_SUBCATEGORY, FILTER_SMALLCATEGORY = True, True, True
        print("筛选级别设置为: 大类、中类和小类")

    # 获取住宅区信息
    residential_id = args.residential_id
    if args.name and args.address:
        # 命令行提供了名称和地址
        name, address = args.name, args.address
    else:
        # 只提供ID的情况，从数据文件中查找名称和地址
        name, address = get_residential_info(residential_id)
        if name is None or address is None:
            sys.exit(1)
        print(f"找到住宅区: {name}, 地址: {address}")

    # 调用主函数
    main(residential_id, name, address)
