#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生成住宅区15分钟生活圈评估报告
"""

import os
import sys
import json
import pandas as pd
from typing import Dict, List, Any
import argparse
from datetime import datetime
import subprocess

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from utils.poi.poi_filter import filter_poi_types, build_category_hierarchy


def markdown_to_html(markdown_file: str, output_file: str = None) -> bool:
    """
    将Markdown文件转换为HTML格式

    Args:
        markdown_file (str): Markdown文件路径
        output_file (str, optional): 输出HTML文件路径，如果不提供则在Markdown文件所在目录生成同名HTML文件

    Returns:
        bool: 转换是否成功
    """
    # 检查pandoc是否可用
    try:
        subprocess.run(
            ["pandoc", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("错误：未找到pandoc命令，无法进行Markdown到HTML的转换。")
        print("请安装pandoc：https://pandoc.org/installing.html")
        return False

    # 确定输出文件路径，默认在Markdown文件所在目录生成同名HTML文件
    if not output_file:
        output_file = os.path.splitext(markdown_file)[0] + ".html"

    try:
        # 使用pandoc转换Markdown到HTML
        # 从文件名提取标题，并去掉可能包含的ID
        filename = os.path.basename(output_file)
        title = os.path.splitext(filename)[0]

        # 如果标题中包含下划线，可能是"社区名_评估报告"格式，去掉后面的"_评估报告"
        if "_" in title:
            title = title.split("_")[0]
        # 使用pandoc转换Markdown到HTML，添加标题参数
        cmd = [
            "pandoc",
            markdown_file,
            "-o",
            output_file,
            "--standalone",
            "--css=https://cdn.jsdelivr.net/npm/github-markdown-css@4.0.0/github-markdown.min.css",
            "--metadata",
            f"title={title}",
        ]
        subprocess.run(cmd, check=True)
        print(f"已成功将 {markdown_file} 转换为 {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"转换失败: {str(e)}")
        return False


def generate_markdown_report(
    residential_id: str, stats_dir: str, community_name: str = None
) -> str:
    """
    生成Markdown格式的评估报告

    Args:
        residential_id (str): 住宅区ID
        stats_dir (str): 统计数据目录路径
        community_name (str, optional): 社区名称，从CSV文件自动读取，如果不提供则使用residential_id

    Returns:
        str: 生成的Markdown报告内容
    """
    # 读取汇总数据
    summary_file = os.path.join(stats_dir, "summary.json")
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # 读取分类统计数据
    stats_file = os.path.join(stats_dir, f"stats_{residential_id}.json")
    with open(stats_file, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    # 读取得分数据
    score_file = os.path.join(stats_dir, f"score_{residential_id}.csv")
    score_df = pd.read_csv(score_file)

    # 提取基本信息
    total_score = summary.get("total_score", 0)
    poi_count = summary.get("poi_count", 0)
    big_category_count = summary.get("big_category_count", 0)
    mid_category_count = summary.get("mid_category_count", 0)
    small_category_count = summary.get("small_category_count", 0)

    # 按类型分类统计数据
    big_categories = [item for item in stats_data if item["类型"] == "大类"]
    mid_categories = [item for item in stats_data if item["类型"] == "中类"]
    small_categories = [item for item in stats_data if item["类型"] == "小类"]

    # 按加权得分排序
    big_categories_sorted = sorted(
        big_categories, key=lambda x: x["加权得分"], reverse=True
    )
    mid_categories_sorted = sorted(
        mid_categories, key=lambda x: x["加权得分"], reverse=True
    )
    small_categories_sorted = sorted(
        small_categories, key=lambda x: x["加权得分"], reverse=True
    )

    # 读取权重配置文件
    weight_config_file = os.path.join(BASE_DIR, 'data', 'poi_weights', '高德POI_加权.csv')
    weight_config_df = pd.read_csv(weight_config_file)

    # 使用poi_filter.py中的函数构建类别层级结构
    category_hierarchy = build_category_hierarchy(weight_config_df)

    # 使用poi_filter.py中的函数过滤POI类型并获取映射
    filtered_types, kept_categories, type_mapping = filter_poi_types(weight_config_file)

    # 创建类别名称到NEW_TYPE的映射
    category_to_types = {"大类": {}, "中类": {}, "小类": {}}

    # 反向映射：从类别名称到NEW_TYPE
    for new_type, info in type_mapping.items():
        big_category = info["大类"]
        mid_category = info["中类"]
        small_category = info["小类"]

        if big_category not in category_to_types["大类"]:
            category_to_types["大类"][big_category] = set()
        category_to_types["大类"][big_category].add(new_type)

        if mid_category not in category_to_types["中类"]:
            category_to_types["中类"][mid_category] = set()
        category_to_types["中类"][mid_category].add(new_type)

        if small_category and small_category not in category_to_types["小类"]:
            category_to_types["小类"][small_category] = set()
        if small_category:  # 确保小类不为空
            category_to_types["小类"][small_category].add(new_type)

    # 使用社区名称或住宅区ID作为标题
    display_name = community_name if community_name else residential_id
    # 生成Markdown报告
    report = f"""# {display_name} 15 分钟生活圈评估报告

## 评估概况

- **社区ID**: {residential_id}
- **评估日期**: {datetime.now().strftime('%Y年%m月%d日')}
- **POI总数**: {poi_count} 个
- **加权总分**: {total_score:.2f} 分
- **平均权重**: {total_score/poi_count if poi_count > 0 else 0:.2f}
- **大类数量**: {big_category_count} 个
- **中类数量**: {mid_category_count} 个
- **小类数量**: {small_category_count} 个

## 大类分析

| 排名 | 类别名称 | POI数量 | 加权得分 | 平均权重 | 中类数量 |
|------|---------|--------|---------|---------|----------|
"""

    for i, category in enumerate(big_categories_sorted):
        report += f"| {i+1} | {category['名称']} | {category['POI数量']} | {category['加权得分']:.2f} | {category['平均权重']:.2f} | {category['子类型数量']} |\n"

    report += "\n## 中类分析\n\n"
    report += "| 排名 | 类别名称 | POI数量 | 加权得分 | 平均权重 | 所属大类 |\n"
    report += "|------|---------|--------|---------|---------|----------|\n"

    for i, category in enumerate(mid_categories_sorted):
        # 查找所属大类
        parent_big = None
        mid_name = category["名称"]

        # 通过type_mapping直接确定所属大类
        for type_id, info in type_mapping.items():
            if info["中类"] == mid_name:
                parent_big = info["大类"]
                break

        report += f"| {i+1} | {category['名称']} | {category['POI数量']} | {category['加权得分']:.2f} | {category['平均权重']:.2f} | {parent_big or '未知'} |\n"

    report += "\n## 小类分析（TOP10）\n\n"
    report += "| 排名 | 类别名称 | POI数量 | 加权得分 | 平均权重 | 所属中类 |\n"
    report += "|------|---------|--------|---------|---------|----------|\n"

    for i, category in enumerate(small_categories_sorted[:10]):
        # 查找所属中类
        parent_mid = None
        small_name = category["名称"]

        # 通过type_mapping直接确定所属中类
        for type_id, info in type_mapping.items():
            if info["小类"] == small_name:
                parent_mid = info["中类"]
                break

        report += f"| {i+1} | {category['名称']} | {category['POI数量']} | {category['加权得分']:.2f} | {category['平均权重']:.2f} | {parent_mid or '未知'} |\n"

    report += f"""
## 评估结论

1. **POI分布情况**:
   - 该社区周边共有 {poi_count} 个POI，覆盖 {big_category_count} 个大类、{mid_category_count} 个中类和 {small_category_count} 个小类。
   - POI数量最多的类别是 {big_categories_sorted[0]['名称']}，共有 {big_categories_sorted[0]['POI数量']} 个POI。

2. **服务得分情况**:
   - 该社区15分钟生活圈加权总分为 {total_score:.2f} 分。
   - 得分最高的服务类别是 {big_categories_sorted[0]['名称']}，得分为 {big_categories_sorted[0]['加权得分']:.2f} 分。
   - 平均权重最高的服务类别是 {sorted(big_categories, key=lambda x: x['平均权重'], reverse=True)[0]['名称']}，平均权重为 {sorted(big_categories, key=lambda x: x['平均权重'], reverse=True)[0]['平均权重']:.2f}。

3. **生活便利性评估**:
   - 根据POI分布和得分情况，该住宅区的15分钟生活圈便利性为{'较高' if total_score/poi_count > 0.8 else '中等' if total_score/poi_count > 0.6 else '一般'}。
   - {'各类服务设施较为齐全，能够满足居民日常需求。' if big_category_count >= 5 else '部分服务设施较为缺乏，建议进一步完善。'}

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="生成住宅区15分钟生活圈评估报告")
    parser.add_argument("residential_id", help="住宅区ID")
    parser.add_argument(
        "--stats_dir",
        help="统计数据目录路径",
        default=None,
    )
    parser.add_argument("--output", help="输出文件路径", default=None)
    parser.add_argument(
        "--no-html", action="store_true", help="不生成HTML文件，只生成Markdown文件"
    )
    parser.add_argument("--open", action="store_true", help="生成HTML文件后自动打开")

    args = parser.parse_args()

    # 如果没有提供统计数据目录，则根据住宅区ID自动确定
    if not args.stats_dir:
        args.stats_dir = f"output/stats_poi_{args.residential_id}"
        print(f"自动确定统计数据目录: {args.stats_dir}")

    # 自动从CSV文件中读取社区名称
    community_name = None
    try:
        # 尝试从POI数据文件中获取住宅区名称
        poi_file = os.path.join(
            os.path.dirname(args.stats_dir), f"poi_{args.residential_id}.csv"
        )
        if os.path.exists(poi_file):
            poi_df = pd.read_csv(poi_file)
            if "住宅区名称" in poi_df.columns:
                community_name = poi_df["住宅区名称"].iloc[0]  # 取第一个住宅区名称
                print(f"已从CSV文件读取到社区名称: {community_name}")
            else:
                print("警告：CSV文件中未找到'住宅区名称'列")
        else:
            print(f"警告：未找到POI数据文件: {poi_file}")
    except Exception as e:
        print(f"警告：无法从CSV文件读取住宅区名称: {str(e)}")

    # 生成Markdown报告
    report = generate_markdown_report(
        args.residential_id, args.stats_dir, community_name
    )

    # 确定Markdown输出文件路径
    if args.output:
        md_file = args.output
        if not md_file.endswith(".md"):
            md_file = os.path.splitext(md_file)[0] + ".md"
    else:
        # 使用社区名称作为文件名，如果没有社区名称则使用ID
        if community_name:
            md_file = os.path.join(args.stats_dir, f"{community_name}_评估报告.md")
        else:
            md_file = os.path.join(args.stats_dir, f"{args.residential_id}_评估报告.md")

    # 写入Markdown报告文件
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Markdown评估报告已生成: {md_file}")

    # 如果没有指定不生成HTML文件，则默认生成HTML文件
    if not args.no_html:
        # 确定HTML输出文件路径
        html_file = os.path.splitext(md_file)[0] + ".html"

        # 转换Markdown到HTML
        success = markdown_to_html(md_file, html_file)
        if success:
            print(f"HTML评估报告已生成: {html_file}")
            # 如果指定了--open参数，则尝试自动打开生成的HTML文件
            if args.open:
                try:
                    if sys.platform == "win32":
                        os.startfile(html_file)
                    elif sys.platform == "darwin":  # macOS
                        subprocess.run(["open", html_file])
                    else:  # Linux
                        subprocess.run(["xdg-open", html_file])
                    print(f"已自动打开HTML文件: {html_file}")
                except Exception as e:
                    print(f"无法自动打开HTML文件: {str(e)}")
    return


if __name__ == "__main__":
    main()
