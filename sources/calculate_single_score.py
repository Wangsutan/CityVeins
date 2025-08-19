#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单个POI文件15分钟生活圈打分模块

该模块负责对单个住宅区的POI文件进行15分钟生活圈打分，计算加权总分并生成详细统计。
支持CSV和JSON格式的POI文件输入，输出得分文件和分类统计文件。

功能：
1. 读取POI文件并统一列名
2. 加载POI权重配置
3. 计算加权总分和分类统计
4. 保存大类、中类和小类的统计结果
5. 生成得分汇总文件

依赖模块：
- pandas: 数据处理和保存
- utils.poi_analysis: 得分计算和统计生成工具
- config: 项目配置文件

使用示例:
python calculate_single_score.py poi_xxxxx.csv
输出: stats_poi_xxxxx/score_xxxxx.csv + 各类统计文件
"""

import os
import sys
import pandas as pd
import argparse
import json
from typing import Dict, List, Any, Optional, Tuple

# 把项目根目录加入 sys.path，确保能导入所需模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sources.utils.poi.poi_analysis import calculate_weighted_score
from sources.utils.file.file_handler import save_category_stats
from sources.utils.file.weight_loader import load_weight_config
from config import WEIGHT_FILE

# ---------- 列名容错映射 ----------
COL_MAP: Dict[str, str] = {
    "POI类型": "POI类型",
    "POI大类": "POI大类",
    "POI中类": "POI中类",
    "POI小类": "POI小类",
}


def main(poi_path: str, stats_dir: Optional[str] = None) -> None:
    """
    对单个 POI 文件打分并落地结果

    读取单个POI文件，计算15分钟生活圈加权得分，并保存得分结果和分类统计。

    处理流程：
    1. 检查POI文件是否存在
    2. 创建统计目录
    3. 加载POI权重配置
    4. 计算加权得分和分类统计
    5. 保存得分结果和分类统计
    6. 生成汇总JSON文件

    Args:
        poi_path (str): POI文件路径
        stats_dir (str, optional): 统计目录路径，如果为None则自动创建

    Returns:
        None: 结果直接保存到文件
    """
    # 检查POI文件是否存在
    if not os.path.exists(poi_path):
        print(f"POI文件不存在: {poi_path}")
        return

    # 从文件路径提取住宅区ID
    base_name: str = os.path.basename(poi_path)
    if base_name.startswith("poi_") and base_name.endswith(".csv"):
        residential_id: str = base_name[4:-4]
    else:
        # 如果文件名不符合预期格式，使用整个文件名（不含扩展名）作为ID
        residential_id: str = os.path.splitext(base_name)[0]

    # 创建统计目录
    if stats_dir is None:
        stats_dir: str = os.path.join(
            os.path.dirname(poi_path), f"stats_poi_{residential_id}"
        )
    os.makedirs(stats_dir, exist_ok=True)

    print(f"处理住宅区: {residential_id}")
    print(f"POI文件: {poi_path}")
    print(f"统计目录: {stats_dir}")

    try:
        # 加载权重配置
        weight_map: Dict[str, Any] = load_weight_config(WEIGHT_FILE)

        # 计算加权得分和分类统计
        total_score: float
        poi_count: int
        category_stats: pd.DataFrame
        total_score, poi_count, category_stats = calculate_weighted_score(
            poi_path, weight_map
        )

        # 从category_stats中提取大类、中类和小类的统计信息
        big_category = category_stats[category_stats["类型"] == "大类"]
        mid_category = category_stats[category_stats["类型"] == "中类"]
        small_category = category_stats[category_stats["类型"] == "小类"]

        # 保存得分结果
        score_file: str = os.path.join(stats_dir, f"score_{residential_id}.csv")
        score_data: Dict[str, List[Any]] = {
            "住宅区ID": [residential_id],
            "加权总分": [total_score],
            "POI总数": [poi_count],
        }
        pd.DataFrame(score_data).to_csv(score_file, index=False, encoding="utf-8-sig")
        print(f"得分结果已保存: {score_file}")

        # 保存分类统计
        save_category_stats(
            big_category, mid_category, small_category, stats_dir, residential_id
        )

        # 生成汇总JSON文件
        summary: Dict[str, Any] = {
            "residential_id": residential_id,
            "total_score": total_score,
            "poi_count": poi_count,
            "big_category_count": len(big_category) if not big_category.empty else 0,
            "mid_category_count": len(mid_category) if not mid_category.empty else 0,
            "small_category_count": (
                len(small_category) if not small_category.empty else 0
            ),
            "stats_dir": stats_dir,
        }

        summary_file: str = os.path.join(stats_dir, "summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"汇总信息已保存: {summary_file}")

        print(
            f"处理完成: {residential_id} - 总分: {total_score:.2f}, POI数量: {poi_count}"
        )

    except Exception as e:
        print(f"处理失败: {str(e)}")
        # 保存错误信息
        error_summary: Dict[str, Any] = {
            "residential_id": residential_id,
            "error": str(e),
            "stats_dir": stats_dir,
        }
        error_file = os.path.join(stats_dir, "error.json")
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_summary, f, ensure_ascii=False, indent=2)
        print(f"错误信息已保存: {error_file}")


if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="计算单个住宅区15分钟生活圈得分")
    parser.add_argument("poi_path", help="POI文件路径")
    parser.add_argument("--stats-dir", help="统计目录路径")
    args = parser.parse_args()

    # 调用主函数
    main(args.poi_path, args.stats_dir)
