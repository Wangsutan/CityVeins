"""
批量获取住宅区POI数据（修复版）

该脚本负责批量获取住宅区周边的 POI 数据，基于高德地图 API 和分类体系。
支持全量 POI 类型获取，并将结果保存为 CSV 和 JSON 格式，便于后续处理和分析。

修改内容：
1. 直接使用 CSV 文件中已有的经纬度坐标，不再进行地理编码
2. 优化错误处理，提高处理成功率
3. 只传递住宅区 ID 作为参数，让 get_single_residential_poi_fixed.py 自己从 CSV 文件中获取经纬度
4. 更新模块导入路径，去掉 sources 前缀
5. --limit 支持范围写法，如 1-100、50、0（全部）

使用示例:
python simple_batch_residential_poi.py --limit 1-100
python simple_batch_residential_poi.py --limit 50
python simple_batch_residential_poi.py --limit 0        # 处理所有记录
"""

import os
import sys
import argparse
import subprocess
import pandas as pd
from tqdm import tqdm

# 添加项目根目录到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import RESIDENTIAL_OUT


# ------------------ 新增：范围解析函数 ------------------
def parse_range(range_str: str):
    """
    解析形如 '1-100' 或 '50' 的范围字符串。
    返回 (start, end) 元组，两边都是闭区间，1-based。
    输入 '0' 返回 (0, 0) 代表“全部”。
    """
    range_str = str(range_str).strip()
    if range_str == "0":
        return 0, 0

    if "-" in range_str:
        start, end = map(int, range_str.split("-", 1))
        if start > end or start < 1:
            raise ValueError("范围格式错误，起始应小于等于结束且为正整数")
        return start, end
    else:
        single = int(range_str)
        if single < 1:
            raise ValueError("单数字必须大于 0")
        return 1, single
# -------------------------------------------------------


def main():
    # ------------------ 命令行参数 ------------------
    parser = argparse.ArgumentParser(description="批量获取住宅区POI数据")
    parser.add_argument("--district", default="田家庵区", help="行政区名称，默认为田家庵区")
    parser.add_argument("--input-file", help="输入CSV文件路径")
    parser.add_argument(
        "--limit",
        type=str,
        default="10",
        help="处理记录范围，支持 '1-100'、'50' 或 '0'(全部)，默认为 '10'",
    )
    args = parser.parse_args()
    # ----------------------------------------------

    district = args.district

    # 如果用户没指定 input-file，则用默认路径
    if not args.input_file:
        args.input_file = RESIDENTIAL_OUT(district)

    # 确保输出目录存在
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    print(f"确保输出目录存在: {output_dir}")

    poi_dir = os.path.join(output_dir, "poi")
    os.makedirs(poi_dir, exist_ok=True)
    print(f"确保POI子目录存在: {poi_dir}")

    # 加载输入数据
    try:
        df = pd.read_csv(args.input_file)
        print(f"✅ 已加载输入文件: {args.input_file}")
        print(f"共 {len(df)} 条记录")
    except Exception as e:
        print(f"❌ 加载输入文件失败: {e}")
        return

    # ------------------ 解析 limit 并切片 ------------------
    try:
        start_idx, end_idx = parse_range(args.limit)
    except ValueError as e:
        print(f"❌ 参数错误: {e}")
        return

    if start_idx == 0 and end_idx == 0:
        # 处理全部
        pass
    else:
        df = df.iloc[start_idx - 1 : end_idx]
        print(f"📊 选取记录范围: 第 {start_idx} 条 ~ 第 {end_idx} 条，共 {len(df)} 条")
    # ------------------------------------------------------

    # 处理每条记录
    success_count = 0
    fail_count = 0

    for _, row in tqdm(df.iterrows(), total=len(df), desc="处理进度"):
        residential_id = row["id"]
        name = row["name"]
        lng = row.get("lng", None)
        lat = row.get("lat", None)

        if lng is None or lat is None:
            print(f"❌ 住宅区 {name} ({residential_id}) 缺少经纬度信息，跳过处理")
            fail_count += 1
            continue

        try:
            script_path = os.path.join(
                project_root, "sources", "get_single_residential_poi_fixed.py"
            )
            cmd = ["python", script_path, residential_id]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ 成功处理: {name} ({residential_id})")
                success_count += 1
            else:
                print(f"❌ 处理失败: {name} ({residential_id}) - {result.stderr}")
                fail_count += 1

        except Exception as e:
            print(f"❌ 处理失败: {name} ({residential_id}) - {str(e)}")
            fail_count += 1

    print("\n=== 处理结果统计 ===")
    print(f"总记录数: {len(df)}")
    print(f"成功: {success_count} ({success_count/len(df)*100:.1f}%)" if len(df) else "成功: 0")
    print(f"失败: {fail_count} ({fail_count/len(df)*100:.1f}%) " if len(df) else "失败: 0")


if __name__ == "__main__":
    main()