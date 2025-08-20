
"""
批量获取住宅区POI数据（修复版）

该脚本负责批量获取住宅区周边的POI数据，基于高德地图API和分类体系。
支持全量POI类型获取，并将结果保存为CSV和JSON格式，便于后续处理和分析。

修改内容：
1. 直接使用CSV文件中已有的经纬度坐标，不再进行地理编码
2. 优化错误处理，提高处理成功率
3. 只传递住宅区ID作为参数，让get_single_residential_poi_fixed.py自己从CSV文件中获取经纬度
4. 更新模块导入路径，去掉sources前缀

使用示例:
python simple_batch_residential_poi.py --limit 10
python simple_batch_residential_poi.py --limit 0  # 处理所有记录
"""

import os
import sys
import argparse
import pandas as pd
from tqdm import tqdm

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import RESIDENTIAL_OUT
from utils.file.key_loader import load_key
from utils.poi.poi_filter import filter_poi_types

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="批量获取住宅区POI数据")

    # 获取行政区名称
    district = "田家庵区"

    parser.add_argument("--input-file", help="输入CSV文件路径", 
                       default=RESIDENTIAL_OUT(district))
    parser.add_argument("--limit", type=int, default=10, 
                       help="限制处理的记录数量，默认为10条。设置为0或负数表示处理所有记录")

    args = parser.parse_args()

    # 确保输出目录存在
    # 注意：get_single_residential_poi_fixed.py会自动在其OUTPUT_DIR下创建poi子目录
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    print(f"确保输出目录存在: {output_dir}")
    
    # 确保POI子目录存在
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

    # 限制处理的记录数量
    if args.limit > 0:
        df = df.head(args.limit)
        print(f"📊 限制处理数量: 选取前 {len(df)} 条记录")

    # 处理每条记录
    success_count = 0
    fail_count = 0

    for _, row in tqdm(df.iterrows(), total=len(df), desc="处理进度"):
        residential_id = row["id"]
        name = row["name"]
        lng = row.get("lng", None)
        lat = row.get("lat", None)

        # 检查是否有经纬度信息
        if lng is None or lat is None:
            print(f"❌ 住宅区 {name} ({residential_id}) 缺少经纬度信息，跳过处理")
            fail_count += 1
            continue

        try:
            # 调用单个住宅区POI获取脚本，只传递住宅区ID
            script_path = os.path.join(project_root, "sources", "get_single_residential_poi_fixed.py")
            cmd = [
                "python", 
                script_path,
                residential_id
            ]

            # 使用subprocess运行脚本
            import subprocess
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
    print(f"成功: {success_count} ({success_count/len(df)*100:.1f}%)")
    print(f"失败: {fail_count} ({fail_count/len(df)*100:.1f}%)")

if __name__ == "__main__":
    main()
