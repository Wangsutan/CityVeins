"""
批量处理管道脚本

该脚本负责自动化处理住宅区POI数据的完整流程：
1. 计算生活圈评分
2. 生成可视化
3. 生成报告

使用示例:
python batch_process_pipeline.py --limit 10
python batch_process_pipeline.py --limit 0  # 处理所有记录
"""

import os
import sys
import argparse
import glob
import subprocess
import pandas as pd
from tqdm import tqdm


def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="批量处理住宅区POI数据管道")

    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parser.add_argument(
        "--input-dir",
        help="输入POI数据目录",
        default=os.path.join(project_root, "output", "poi"),
    )
    parser.add_argument(
        "--output-dir",
        help="输出目录路径",
        default=os.path.join(project_root, "output"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="限制处理的记录数量，默认为10条。设置为0或负数表示处理所有记录",
    )
    parser.add_argument("--skip-scores", action="store_true", help="跳过评分计算步骤")
    parser.add_argument(
        "--skip-visualization", action="store_true", help="跳过可视化步骤"
    )
    parser.add_argument("--skip-report", action="store_true", help="跳过报告生成步骤")

    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    # 获取所有POI文件（只处理后缀为unique的CSV文件）
    poi_files = glob.glob(os.path.join(args.input_dir, "*_unique.csv"))
    print(f"找到 {len(poi_files)} 个POI文件")

    # 限制处理的文件数量
    if args.limit > 0:
        poi_files = poi_files[: args.limit]
        print(f"限制处理数量: 选取前 {len(poi_files)} 个文件")

    # 1. 批量计算评分
    if not args.skip_scores:
        print("=== 步骤1: 计算生活圈评分 ===")
        score_script = os.path.join(
            project_root, "sources", "calculate_batch_scores.py"
        )

        # 创建评分命令
        cmd = [
            "python",
            score_script,
            "--poi-dir",
            args.input_dir,
            "--output-file",
            os.path.join(args.output_dir, "住宅区得分汇总.csv"),
        ]

        try:
            print(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("错误信息:", result.stderr)
            print("✅ 评分计算完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 评分计算失败: {e}")
            print("错误输出:", e.stderr)
            return
    else:
        print("⏭️  跳过评分计算步骤")

    # 2. 生成可视化
    if not args.skip_visualization:
        print("\n=== 步骤2: 生成可视化 ===")

        # 使用POI文件获取住宅区ID
        residential_ids = []
        for poi_file in poi_files:
            filename = os.path.basename(poi_file)
            residential_id = filename.replace("poi_", "").replace(".csv", "")
            residential_ids.append(residential_id)

        if not residential_ids:
            print("⚠️  未找到住宅区ID，跳过可视化步骤")
        else:
            success_count = 0
            for residential_id in tqdm(residential_ids, desc="生成可视化"):
                # 检查stats目录是否存在
                stats_dir = os.path.join(args.input_dir, f"stats_poi_{residential_id}")
                if not os.path.exists(stats_dir):
                    print(
                        f"⚠️  未找到统计数据目录 {stats_dir}，跳过可视化: {residential_id}"
                    )
                    continue

                # 直接使用Python调用可视化函数，而不是通过命令行
                cmd = [
                    "python",
                    "-c",
                    f"""
import sys
sys.path.insert(0, '{project_root}')
from sources.visualize_poi import visualize_poi
residential_id = '{residential_id}'
output_dir = '{stats_dir}'
visualize_poi(residential_id, output_dir, show_plots=False)
""",
                ]

                try:
                    result = subprocess.run(
                        cmd, check=True, capture_output=True, text=True
                    )
                    success_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"❌ 可视化失败 {residential_id}: {e.stderr}")

            print(f"✅ 可视化生成完成，成功: {success_count}/{len(residential_ids)}")
    else:
        print("⏭️  跳过可视化步骤")

    # 3. 生成报告
    if not args.skip_report:
        print("\n=== 步骤3: 生成报告 ===")

        # 使用POI文件获取住宅区ID
        residential_ids = []
        for poi_file in poi_files:
            filename = os.path.basename(poi_file)
            residential_id = filename.replace("poi_", "").replace(".csv", "")
            residential_ids.append(residential_id)

        if not residential_ids:
            print("⚠️  未找到住宅区ID，跳过报告生成步骤")
        else:
            success_count = 0
            for residential_id in tqdm(residential_ids, desc="生成报告"):
                # 检查stats目录是否存在
                stats_dir = os.path.join(args.input_dir, f"stats_poi_{residential_id}")
                if not os.path.exists(stats_dir):
                    print(
                        f"⚠️  未找到统计数据目录 {stats_dir}，跳过报告生成: {residential_id}"
                    )
                    continue

                # 检查summary文件是否存在
                summary_file = os.path.join(stats_dir, "summary.json")
                if not os.path.exists(summary_file):
                    print(
                        f"⚠️  未找到汇总文件 {summary_file}，跳过报告生成: {residential_id}"
                    )
                    continue

                # 创建临时修复的generate_report.py脚本，修复pandoc标题问题
                fixed_report_script = os.path.join(
                    project_root, "sources", "generate_report_fixed.py"
                )

                # 检查修复后的脚本是否存在，不存在则创建
                if not os.path.exists(fixed_report_script):
                    # 读取原始脚本
                    with open(
                        os.path.join(project_root, "sources", "generate_report.py"),
                        "r",
                        encoding="utf-8",
                    ) as f:
                        original_content = f.read()

                    # 替换markdown_to_html函数中的pandoc命令
                    fixed_content = original_content.replace(
                        """cmd = [
            "pandoc",
            markdown_file,
            "-o",
            output_file,
            "--standalone",
            "--css=https://cdn.jsdelivr.net/npm/github-markdown-css@4.0.0/github-markdown.min.css",
        ]""",
                        """# 从文件名提取标题
        title = os.path.splitext(os.path.basename(output_file))[0]
        # 使用pandoc转换Markdown到HTML，添加标题参数
        cmd = [
            "pandoc",
            markdown_file,
            "-o",
            output_file,
            "--standalone",
            "--css=https://cdn.jsdelivr.net/npm/github-markdown-css@4.0.0/github-markdown.min.css",
            "--metadata", f"title={title}",
        ]""",
                    )

                    # 写入修复后的脚本
                    with open(fixed_report_script, "w", encoding="utf-8") as f:
                        f.write(fixed_content)

                # 创建报告命令，使用修复后的脚本
                cmd = [
                    "python",
                    fixed_report_script,
                    residential_id,
                    "--stats_dir",
                    stats_dir,
                    "--output",
                    os.path.join(args.output_dir, f"report_{residential_id}.html"),
                ]

                try:
                    print(f"执行命令: {' '.join(cmd)}")
                    result = subprocess.run(
                        cmd, check=True, capture_output=True, text=True
                    )
                    print(result.stdout)
                    if result.stderr:
                        print("错误信息:", result.stderr)
                    print(f"✅ 报告生成完成: {residential_id}")
                    success_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"❌ 报告生成失败 {residential_id}: {e.stderr}")

            print(f"✅ 报告生成完成，成功: {success_count}/{len(residential_ids)}")
    else:
        print("⏭️  跳过报告生成步骤")

    print("\n=== 批量处理完成 ===")
    print(f"处理了 {len(poi_files)} 个住宅区的数据")
    print(f"结果保存在: {args.output_dir}")


if __name__ == "__main__":
    main()
