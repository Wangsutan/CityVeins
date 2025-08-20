"""
住宅区15分钟生活圈加权得分计算模块

该模块负责计算住宅区15分钟生活圈的加权得分，
基于POI数据和权重配置文件，
提供大类、中类和小类的详细统计分析。
支持CSV和JSON格式的POI数据输入，
并生成详细的统计报告和Markdown格式的评估报告。

功能：
1. 加载POI权重配置，支持客制化权重
2. 计算每个住宅区的加权得分
3. 生成大类、中类和小类的详细统计
4. 输出TOP10排名和详细评估报告
5. 支持多种POI数据格式（CSV和JSON）

依赖模块：
- config.py: 项目配置文件，提供路径和常量
- utils.weight_loader: 权重配置加载工具
- utils.poi_analyzer: POI数据分析工具
- utils.file_handler: 文件处理工具
- pandas: 数据处理和分析
- tqdm: 进度条显示

使用示例:
python calculate_batch_scores.py output/poi data/poi_weights/高德POI_客制化权重.csv output/stats/住宅区得分汇总.csv
"""

import os
import sys
from tqdm import tqdm
import sys, os
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *
from sources.utils.file.weight_loader import load_weight_config
from sources.utils.poi.poi_analysis import generate_summary_report
from sources.utils.file.file_handler import save_category_stats
from calculate_single_score import main as score_single_main


def process_single_residential(file_path: str, residential_id: str) -> Dict[str, Any]:
    """
    处理单个住宅区的POI数据

    调用calculate_single_score模块处理单个住宅区的POI数据，并返回处理结果。

    Args:
        file_path (str): POI文件路径
        residential_id (str): 住宅区ID

    Returns:
        dict: 包含处理结果的字典，包括得分、POI数量和统计目录等信息
    """
    # 创建统计目录
    stats_dir: str = os.path.join(
        os.path.dirname(file_path), "stats_poi_" + residential_id
    )
    os.makedirs(stats_dir, exist_ok=True)

    # 调用单个住宅区评分模块
    score_single_main(file_path, stats_dir)

    # 读取生成的统计文件
    summary_file: str = os.path.join(stats_dir, "summary.json")
    if os.path.exists(summary_file):
        import json

        with open(summary_file, "r", encoding="utf-8") as f:
            summary: Dict[str, Any] = json.load(f)
        return summary
    else:
        # 检查是否有错误文件
        error_file: str = os.path.join(stats_dir, "error.json")
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                error_data: Dict[str, Any] = json.load(f)
            return {
                "residential_id": residential_id,
                "total_score": 0,
                "poi_count": 0,
                "stats_dir": stats_dir,
                "error": error_data.get("error", "未知错误"),
            }
        return {
            "residential_id": residential_id,
            "total_score": 0,
            "poi_count": 0,
            "stats_dir": stats_dir,
        }


def main(
    poi_dir: Optional[str] = None,
    weight_file: Optional[str] = None,
    output_file: Optional[str] = None,
    residential_ids: Optional[List[str]] = None,
) -> None:
    """
    主函数，批量计算住宅区得分

    Args:
        poi_dir (str, optional): POI数据目录路径，默认为OUTPUT_DIR/poi
        weight_file (str, optional): 权重配置文件路径，默认为WEIGHT_FILE
        output_file (str, optional): 输出文件路径，默认为OUTPUT_DIR/住宅区得分汇总.csv
        residential_ids (list, optional): 指定要处理的住宅区ID列表，如果为None则处理所有住宅区
    """
    # 设置默认参数
    if poi_dir is None:
        poi_dir: str = os.path.join(OUTPUT_DIR, "poi")
    if weight_file is None:
        weight_file: str = WEIGHT_FILE
    if output_file is None:
        output_file: str = os.path.join(OUTPUT_DIR, "住宅区得分汇总.csv")

    # 加载权重配置
    print(f"加载权重配置: {weight_file}")
    weight_map: Dict[str, Any] = load_weight_config(weight_file)
    print(f"已加载 {len(weight_map)} 种POI类型的权重配置")

    # 获取POI文件列表
    poi_files: List[str] = []
    if residential_ids:
        # 如果指定了住宅区ID列表，只处理这些ID对应的文件
        for residential_id in residential_ids:
            file_path: str = os.path.join(poi_dir, f"poi_{residential_id}.csv")
            if os.path.exists(file_path):
                poi_files.append((file_path, residential_id))
            else:
                print(f"警告: 未找到住宅区 {residential_id} 的POI文件: {file_path}")
    else:
        # 否则处理所有POI文件
        for file_name in os.listdir(poi_dir):
            if file_name.startswith("poi_") and file_name.endswith(".csv"):
                residential_id: str = file_name[4:-4]  # 提取住宅区ID
                poi_files.append((os.path.join(poi_dir, file_name), residential_id))

    if not poi_files:
        print("未找到POI文件，请检查输入目录")
        return

    print(f"找到 {len(poi_files)} 个POI文件")

    # 处理每个住宅区的POI数据
    all_results: List[Dict[str, Any]] = []
    file_path: str
    residential_id: str
    for file_path, residential_id in tqdm(poi_files, desc="计算得分"):
        try:
            result: Dict[str, Any] = process_single_residential(
                file_path, residential_id
            )
            all_results.append(result)
        except Exception as e:
            print(f"处理住宅区 {residential_id} 失败: {str(e)}")
            all_results.append(
                {
                    "residential_id": residential_id,
                    "total_score": 0,
                    "poi_count": 0,
                    "error": str(e),
                }
            )

    # 生成汇总报告
    if all_results:
        generate_summary_report(all_results, output_file)
    else:
        print("未生成有效结果")


if __name__ == "__main__":
    import argparse

    # 创建命令行参数解析器
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="批量计算住宅区15分钟生活圈加权得分"
    )
    parser.add_argument("--poi-dir", help="POI数据目录路径")
    parser.add_argument("--weight-file", help="权重配置文件路径")
    parser.add_argument("--output-file", help="输出文件路径")
    parser.add_argument("--residential-ids", nargs="+", help="指定要处理的住宅区ID列表")
    args: argparse.Namespace = parser.parse_args()

    # 调用主函数
    main(
        poi_dir=args.poi_dir,
        weight_file=args.weight_file,
        output_file=args.output_file,
        residential_ids=args.residential_ids,
    )
