#!/usr/bin/env python3
"""
CityVeins 主运行脚本

该脚本是整个CityVeins项目的主入口点, 
负责协调各个模块的执行顺序,
实现从行政区验证到最终评分计算的完整流程。

功能：
1. 支持分步骤运行, 可以选择执行到特定步骤
2. 支持从既有数据继续执行, 避免重复处理
3. 提供灵活的命令行参数控制

依赖模块：
- config.py: 项目配置文件, 定义了各种路径和常量
- sources.get_residential_areas: 获取住宅区数据模块
- sources.get_batch_residential_poi: 批量获取住宅区周边POI数据模块
- sources.calculate_score: 计算得分模块
- utils.get_district_boundary: 行政区边界获取和验证模块

使用示例:
# 验证行政区是否合法
python run.py 田家庵区 --step=validate

# 获取行政区边界数据
python run.py 田家庵区 --step=boundary

# 获取住宅区POI数据并保存为CSV
python run.py 田家庵区 --step=residential

# 获取并保存每个住宅区周边POI数据
python run.py 田家庵区 --step=poi

# 生成统计报告和详细评估报告
python run.py 田家庵区 --step=score

# 从既有住宅区数据开始, 获取POI数据
python run.py 田家庵区 --step=poi --use-existing-res

# 从既有POI数据开始, 计算得分
python run.py 田家庵区 --step=score --use-existing-poi

# 完整流程
python run.py 田家庵区 --step=all
"""

import argparse, os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, RESIDENTIAL_OUT, WEIGHT_FILE
from sources.get_residential_areas import main as run_batch_res
from sources.get_batch_residential_poi import POIProcessor
from sources.calculate_batch_scores import main as run_score
from sources.utils.poi.get_district_boundary import (
    validate_district_name,
    get_valid_boundary,
)


def cli():
    """
    命令行接口函数, 解析参数并按指定步骤执行各处理模块

    该函数实现了CityVeins的分步骤工作流程：
    1. 解析命令行参数, 获取要处理的行政区名称和执行步骤
    2. 根据指定的步骤参数, 执行相应的处理模块
    3. 支持从既有数据继续执行, 避免重复处理

    Args:
        无直接参数, 通过argparse解析命令行参数

    Returns:
        无返回值, 结果直接输出到文件和控制台
    """
    parser = argparse.ArgumentParser(description="CityVeins 分步骤运行脚本")
    parser.add_argument("district", help="行政区名称, 如 田家庵区")

    # 步骤参数
    parser.add_argument(
        "--step",
        choices=["validate", "boundary", "residential", "poi", "score", "all"],
        default="all",
        help="执行到哪个步骤: validate(验证行政区), boundary(获取边界), residential(获取住宅区), poi(获取POI), score(计算得分), all(完整流程)",
    )

    # 使用既有数据参数
    parser.add_argument(
        "--use-existing-res",
        action="store_true",
        help="使用已有的住宅区数据, 不重新获取",
    )
    parser.add_argument(
        "--use-existing-poi", action="store_true", help="使用已有的POI数据, 不重新获取"
    )

    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 步骤1：验证行政区是否合法
    if args.step in ["validate", "boundary", "residential", "poi", "score", "all"]:
        print(f"验证行政区: {args.district}")
        if not validate_district_name(args.district):
            print(f"❌ 行政区名称不合法: {args.district}")
            return
        print(f"✅ 行政区名称合法: {args.district}")

        if args.step == "validate":
            print("验证完成")
            return

    # 步骤2：获取行政区边界数据
    if args.step in ["boundary", "residential", "poi", "score", "all"]:
        print(f"获取行政区边界: {args.district}")
        try:
            boundary = get_valid_boundary(args.district)
            print(f"✅ 成功获取行政区边界, 边界点数: {len(boundary.exterior.coords)}")

            if args.step == "boundary":
                print("边界获取完成")
                return
        except Exception as e:
            print(f"❌ 获取行政区边界失败: {str(e)}")
            return

    # 步骤3：获取住宅区POI数据并保存为CSV
    if args.step in ["residential", "poi", "score", "all"]:
        residential_file = RESIDENTIAL_OUT(args.district)

        if args.use_existing_res and os.path.exists(residential_file):
            print(f"使用已有的住宅区数据: {residential_file}")
        else:
            print(f"获取住宅区数据: {args.district}")
            try:
                run_batch_res(args.district)
                print(f"✅ 成功获取住宅区数据: {residential_file}")
            except Exception as e:
                print(f"❌ 获取住宅区数据失败: {str(e)}")
                return

        if args.step == "residential":
            print("住宅区数据获取完成")
            return

    # 步骤4：获取并保存每个住宅区周边POI数据
    if args.step in ["poi", "score", "all"]:
        poi_dir = os.path.join(OUTPUT_DIR, "poi")

        if (
            args.use_existing_poi
            and os.path.exists(poi_dir)
            and len(os.listdir(poi_dir)) > 0
        ):
            print(f"使用已有的POI数据: {poi_dir}")
        else:
            print(f"获取住宅区周边POI数据: {args.district}")
            try:
                processor = POIProcessor(
                    input_file=RESIDENTIAL_OUT(args.district), output_dir=poi_dir
                )
                processor.process_all(overwrite=False)
                print(f"✅ 成功获取住宅区周边POI数据: {poi_dir}")
            except Exception as e:
                print(f"❌ 获取住宅区周边POI数据失败: {str(e)}")
                return

        if args.step == "poi":
            print("POI数据获取完成")
            return

    # 步骤5：生成统计报告和详细评估报告
    if args.step in ["score", "all"]:
        stats_dir = os.path.join(OUTPUT_DIR, "stats")
        os.makedirs(stats_dir, exist_ok=True)

        print(f"计算住宅区得分: {args.district}")
        try:
            run_score(
                poi_dir,
                WEIGHT_FILE,
                os.path.join(stats_dir, f"{args.district}_得分汇总.csv"),
            )
            print(f"✅ 成功计算住宅区得分: {stats_dir}")

            # 生成Markdown格式的详细报告
            summary_file = os.path.join(stats_dir, f"{args.district}_得分汇总.csv")
            if os.path.exists(summary_file):
                md_file = os.path.join(stats_dir, f"{args.district}_评估报告.md")
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(f"# {args.district}住宅区15分钟生活圈评估报告\n\n")

                    # 读取汇总数据
                    summary_df = pd.read_csv(summary_file)
                    f.write(f"共评估了 {len(summary_df)} 个住宅区\n\n")

                    # TOP10排名
                    f.write("## TOP10 住宅区排名\n\n")
                    f.write("| 排名 | 住宅区ID | 住宅区名称 | 加权总分 | POI总数 |\n")
                    f.write("|------|---------|-----------|---------|--------|\n")

                    for i, (_, row) in enumerate(summary_df.head(10).iterrows()):
                        f.write(
                            f"| {i+1} | {row['id']} | {row['name']} | {row['加权总分']} | {row['POI总数']} |\n"
                        )

                    # 评估概况
                    f.write("\n## 评估概况\n\n")
                    f.write(f"- 平均得分: {summary_df['加权总分'].mean():.2f}\n")
                    f.write(f"- 最高得分: {summary_df['加权总分'].max():.2f}\n")
                    f.write(f"- 最低得分: {summary_df['加权总分'].min():.2f}\n")
                    f.write(f"- 平均POI数量: {summary_df['POI总数'].mean():.1f}\n")

                print(f"✅ 详细评估报告已生成: {md_file}")

        except Exception as e:
            print(f"❌ 计算住宅区得分失败: {str(e)}")
            return

        if args.step == "score":
            print("评分计算完成")
            return

    print("🎉 全流程完成！")


if __name__ == "__main__":
    cli()
