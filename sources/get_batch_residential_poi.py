"""
住宅区周边POI数据处理系统

该模块负责批量处理住宅区周边POI数据，通过调用get_single_residential_poi.py
脚本获取每个住宅区周边的POI数据，并保存为CSV文件。支持断点续传、失败重试等
功能，确保数据处理的完整性和可靠性。

功能：
1. 批量处理住宅区周边POI数据
2. 支持断点续传，避免重复处理已成功的数据
3. 支持失败重试，提高数据获取成功率
4. 记录处理状态和失败原因，便于排查问题
5. 支持多种处理模式：重试失败、全覆盖、增量处理
6. 分析POI处理结果，提供详细的统计信息和失败记录分析

依赖模块：
- config.py: 项目配置文件，提供路径和常量
- get_single_residential_poi.py: 获取单个住宅区周边POI数据的脚本
- pandas: 数据处理和保存
- tqdm: 进度条显示

使用示例:
python get_batch_residential_poi.py --input residential_田家庵区.csv --output output/poi
python get_batch_residential_poi.py --retry  # 仅重试之前失败的记录
python get_batch_residential_poi.py --overwrite  # 覆盖已有记录
python get_batch_residential_poi.py --summary  # 分析处理结果
"""

import pandas as pd
import subprocess
import time
from tqdm import tqdm
import os
import argparse
from datetime import datetime
import sys
from typing import Dict, List, Any, Optional, Tuple, Set, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

# 配置常量
DEFAULT_INPUT: str = RESIDENTIAL_OUT("田家庵区")  # 默认输入文件路径
DEFAULT_OUTPUT_DIR: str = OUTPUT_DIR  # 默认输出目录路径
RETRY_LIMIT: int = 3  # 最大重试次数
WAIT_TIME: int = 5  # 重试等待时间(秒)


class POIProcessor:
    """
    住宅区周边POI数据处理器

    该类负责批量处理住宅区周边POI数据，包括数据加载、处理、结果保存等功能。
    支持断点续传、失败重试等机制，确保数据处理的完整性和可靠性。
    同时提供分析功能，可以分析处理结果并提供重试建议。

    属性:
        input_file (str): 输入CSV文件路径
        output_dir (str): 输出目录路径
        summary_file (str): 处理摘要文件路径
        failed_file (str): 失败记录文件路径
    """

    def __init__(self, input_file: str, output_dir: str) -> None:
        """
        初始化POI数据处理器

        Args:
            input_file (str): 输入CSV文件路径，包含住宅区数据
            output_dir (str): 输出目录路径，用于保存POI数据和处理摘要
        """
        self.input_file: str = input_file
        self.output_dir: str = output_dir
        # 处理摘要文件路径，记录每个住宅区的处理状态
        self.summary_file: str = os.path.join(output_dir, "processing_summary.csv")
        # 失败记录文件路径，记录处理失败的住宅区
        self.failed_file: str = os.path.join(output_dir, "failed_records.csv")
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

    def load_data(self) -> Optional[pd.DataFrame]:
        """
        加载输入数据（强制类型转换）

        从CSV文件加载住宅区数据，并对关键字段进行强制类型转换，确保数据格式正确。

        Returns:
            pandas.DataFrame: 包含住宅区数据的DataFrame，如果加载失败则返回None
        """
        try:
            # 加载CSV文件，并对关键字段进行强制类型转换
            df: pd.DataFrame = pd.read_csv(
                self.input_file,
                dtype={
                    "id": str,  # 住宅区ID强制转为字符串
                    "name": str,  # 住宅区名称强制转为字符串
                    "address": str,  # 住宅区地址强制转为字符串
                },
            )
            print(f"✅ 已加载输入文件: {self.input_file} (共 {len(df)} 条记录)")
            return df
        except Exception as e:
            print(f"❌ 文件加载失败: {str(e)}")
            print("请确保文件存在且包含以下列：id, name, address")
            return None

    def load_summary(self) -> pd.DataFrame:
        """
        加载或初始化处理摘要

        如果处理摘要文件存在，则加载该文件；否则创建一个空的DataFrame。
        处理摘要用于记录每个住宅区的处理状态，支持断点续传功能。

        Returns:
            pandas.DataFrame: 包含处理摘要的DataFrame
        """
        if os.path.exists(self.summary_file):
            return pd.read_csv(self.summary_file)
        # 创建空的摘要DataFrame
        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "status",
                "retry_count",
                "timestamp",
                "output_file",
                "message",
            ]
        )

    def get_todo_list(
        self, df: pd.DataFrame, retry_failed: bool = False, overwrite: bool = False
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        确定待处理记录列表

        根据处理摘要和参数，确定需要处理的住宅区列表。支持三种模式：
        1. 重试模式：只处理之前失败的记录
        2. 增量模式：跳过已成功处理的记录
        3. 全覆盖模式：处理所有记录

        Args:
            df (pandas.DataFrame): 包含所有住宅区数据的DataFrame
            retry_failed (bool): 是否只重试失败的记录
            overwrite (bool): 是否覆盖已成功处理的记录

        Returns:
            tuple: (待处理记录DataFrame, 处理摘要DataFrame)
        """
        summary_df: pd.DataFrame = self.load_summary()

        if retry_failed:
            # 重试模式：只处理之前失败的
            failed_ids: Set[str] = set(summary_df[summary_df["status"] != "成功"]["id"])
            todo_df: pd.DataFrame = df[df["id"].isin(failed_ids)]
            print(f"🔁 重试模式：待处理 {len(todo_df)} 条失败记录")
        elif not overwrite:
            # 不覆盖模式：跳过已成功的
            success_ids: Set[str] = set(
                summary_df[summary_df["status"] == "成功"]["id"]
            )
            todo_df: pd.DataFrame = df[~df["id"].isin(success_ids)]
            print(f"🔄 增量模式：待处理 {len(todo_df)} 条新记录")
        else:
            # 全覆盖模式：处理所有记录
            todo_df: pd.DataFrame = df
            print(f"🆕 全覆盖模式：处理全部 {len(todo_df)} 条记录")

        return todo_df, summary_df

    def process_single(self, row: pd.Series, retry_count: int = 0) -> Dict[str, Any]:
        """
        处理单个住宅区（带类型检查和重试机制）

        调用get_single_residential_poi.py脚本获取单个住宅区周边的POI数据，
        并返回处理结果。包含类型检查、错误处理和重试机制。

        Args:
            row (pandas.Series): 包含住宅区数据的行
            retry_count (int): 当前重试次数，默认为0

        Returns:
            dict: 包含处理结果的字典，包括状态、输出文件、错误信息等
        """
        try:
            # 强制类型转换和验证
            residential_id: str = str(row["id"]).strip()
            name: str = str(row["name"]).strip()
            address: str = str(row.get("address", name)).strip()

            if not residential_id:
                raise ValueError("ID不能为空")

            # 构建命令行参数，调用get_single_residential_poi.py脚本
            cmd: List[str] = [
                "python",
                "get_single_residential_poi.py",
                residential_id,
                name,
                address,
            ]

            # 运行子进程执行脚本
            result: subprocess.CompletedProcess = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,  # 添加超时限制，防止脚本卡死
            )

            # 返回成功结果
            return {
                "id": residential_id,
                "name": name,
                "status": "成功",
                "retry_count": retry_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "output_file": f"poi_{residential_id}.csv",
                "message": "",
            }

        except subprocess.CalledProcessError as e:
            # 处理子进程调用失败的情况
            error_msg: str = e.stderr.strip() if e.stderr else str(e)
            return {
                "id": residential_id if "residential_id" in locals() else "未知",
                "name": name if "name" in locals() else "未知",
                "status": "失败",
                "retry_count": retry_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "output_file": "",
                "message": error_msg[:200],  # 截断过长的错误信息
            }
        except Exception as e:
            # 处理其他异常情况
            # 确保变量在异常处理中可用
            res_id: str
            res_name: str
            try:
                res_id = residential_id
            except NameError:
                res_id = "未知"

            try:
                res_name = name
            except NameError:
                res_name = "未知"

            return {
                "id": res_id,
                "name": res_name,
                "status": "失败",
                "retry_count": retry_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "output_file": "",
                "message": f"预处理错误: {str(e)}",
            }

    def process_all(
        self,
        df: Optional[pd.DataFrame] = None,
        retry_failed: bool = False,
        overwrite: bool = False,
    ) -> None:
        """
        主处理流程

        批量处理所有住宅区的POI数据，支持断点续传和失败重试。

        Args:
            df (pandas.DataFrame, optional): 包含住宅区数据的DataFrame，如果为None则从文件加载
            retry_failed (bool): 是否只重试失败的记录
            overwrite (bool): 是否覆盖已成功处理的记录

        Returns:
            None: 结果直接保存到文件
        """
        # 如果没有提供DataFrame，则从文件加载
        if df is None:
            loaded_df: Optional[pd.DataFrame] = self.load_data()
            if loaded_df is None:
                return
            df = loaded_df

        # 获取待处理记录列表
        todo_df: pd.DataFrame
        summary_df: pd.DataFrame
        todo_df, summary_df = self.get_todo_list(df, retry_failed, overwrite)

        # 如果没有需要处理的记录，直接返回
        if todo_df.empty:
            print("✅ 没有需要处理的记录")
            return

        # 处理每个住宅区
        results: List[Dict[str, Any]] = []
        for _, row in tqdm(todo_df.iterrows(), total=len(todo_df), desc="处理进度"):
            result: Optional[Dict[str, Any]] = None
            # 尝试处理，最多重试RETRY_LIMIT次
            for attempt in range(RETRY_LIMIT):
                result = self.process_single(row, attempt)
                if result["status"] == "成功":
                    break
                # 失败后等待一段时间再重试，等待时间随重试次数增加
                time.sleep(WAIT_TIME * (attempt + 1))

            if result is not None:
                results.append(result)
            # 更新处理摘要
            self.update_summary(results, summary_df)

        # 保存失败记录
        self.save_failed_records(results)

    def update_summary(
        self, new_results: List[Dict[str, Any]], existing_summary: pd.DataFrame
    ) -> None:
        """
        更新处理摘要（去重保留最新）

        将新的处理结果合并到现有的处理摘要中，并去重保留最新的记录。

        Args:
            new_results (list): 新的处理结果列表
            existing_summary (pandas.DataFrame): 现有的处理摘要

        Returns:
            None: 结果直接保存到文件
        """
        new_df: pd.DataFrame = pd.DataFrame(new_results)
        # 合并新旧结果
        updated_summary: pd.DataFrame = pd.concat([existing_summary, new_df])
        # 去重，保留每个ID的最新记录
        updated_summary = updated_summary.drop_duplicates("id", keep="last")
        # 保存到文件
        updated_summary.to_csv(self.summary_file, index=False, encoding="utf-8-sig")

    def save_failed_records(self, results: List[Dict[str, Any]]) -> None:
        """
        保存失败记录供后续处理

        从处理结果中筛选出失败的记录，并保存到CSV文件中，便于后续排查问题和重试。

        Args:
            results (list): 所有处理结果的列表

        Returns:
            None: 结果直接保存到文件
        """
        # 筛选失败的记录
        failed_records: List[Dict[str, Any]] = [
            r for r in results if r["status"] != "成功"
        ]
        if failed_records:
            # 保存到CSV文件
            pd.DataFrame(failed_records).to_csv(
                self.failed_file, index=False, encoding="utf-8-sig"
            )
            print(f"❌ 保存失败记录: {self.failed_file} (共 {len(failed_records)} 条)")

    def print_summary(self) -> None:
        """
        打印处理摘要统计

        从处理摘要文件中读取处理结果，并统计成功、失败和待处理的记录数量，
        打印汇总信息。同时提供重试建议和重新处理所有记录的命令建议。

        Returns:
            None: 结果直接打印到控制台
        """
        if not os.path.exists(self.summary_file):
            print("❌ 没有找到处理摘要文件")
            return

        summary_df: pd.DataFrame = pd.read_csv(self.summary_file)

        # 基本统计
        total: int = len(summary_df)  # 总记录数
        success: int = len(summary_df[summary_df["status"] == "成功"])  # 成功记录数
        failed: int = total - success  # 失败记录数

        # 输出基本统计信息
        print("=== 处理结果统计 ===")
        print(f"总记录数: {total}")
        print(f"成功: {success} ({success/total:.1%})")
        print(f"失败: {failed} ({failed/total:.1%})")

        # 失败详情
        if failed > 0:
            print("=== 失败记录 ===")
            # 显示失败记录的详细信息，按重试次数降序排列
            print(
                summary_df[summary_df["status"] != "成功"][
                    ["id", "name", "retry_count", "message"]
                ]
                .sort_values("retry_count", ascending=False)
                .to_string(index=False)
            )

            # 如果存在失败记录文件，提供重试建议
            if os.path.exists(self.failed_file):
                print(f"可执行以下命令重试失败记录:")
                print(
                    f"python get_batch_residential_poi.py --retry --output {self.output_dir}"
                )

        # 成功但有重试的记录
        retried_success: pd.DataFrame = summary_df[
            (summary_df["status"] == "成功") & (summary_df["retry_count"] > 0)
        ]
        if not retried_success.empty:
            print("=== 重试后成功的记录 ===")
            # 显示重试后成功的记录，按重试次数降序排列
            print(
                retried_success[["id", "name", "retry_count"]]
                .sort_values("retry_count", ascending=False)
                .to_string(index=False)
            )

        # 覆盖建议
        if success > 0:
            print(f"可执行以下命令重新处理所有记录（覆盖已有结果）:")
            print(
                f"python get_batch_residential_poi.py --overwrite --output {self.output_dir}"
            )

    def analyze_results(self) -> None:
        """
        分析POI处理结果

        读取处理摘要文件，分析处理结果并输出统计信息和失败记录详情。
        该方法会计算处理成功率，显示失败记录的详细信息，并提供重试建议。

        处理流程：
        1. 检查并读取处理摘要文件
        2. 计算总记录数、成功数和失败数，计算成功率
        3. 输出基本统计信息
        4. 如果存在失败记录，显示失败详情和重试建议
        5. 如果存在重试后成功的记录，显示这些记录
        6. 提供重新处理所有记录的命令建议

        Returns:
            None: 分析结果直接输出到控制台

        Raises:
            FileNotFoundError: 当处理摘要文件不存在时抛出此异常
        """
        self.print_summary()


def main() -> None:
    """
    主函数，解析命令行参数并启动处理流程

    支持以下命令行参数：
    --input: 指定输入文件路径
    --output: 指定输出目录路径
    --retry: 仅重试之前失败的记录
    --overwrite: 覆盖已成功处理的记录
    --summary: 打印处理摘要统计

    Returns:
        None: 结果直接保存到文件或打印到控制台
    """
    # 创建命令行参数解析器
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="批量处理住宅区周边POI数据"
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="输入文件路径")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="输出目录路径")
    parser.add_argument("--retry", action="store_true", help="仅重试之前失败的记录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已成功处理的记录")
    parser.add_argument("--summary", action="store_true", help="打印处理摘要统计")
    args: argparse.Namespace = parser.parse_args()

    # 创建处理器
    processor: POIProcessor = POIProcessor(args.input, args.output)

    # 如果只需要打印摘要，则直接调用相关方法并返回
    if args.summary:
        processor.analyze_results()
        return

    # 启动处理流程
    processor.process_all(retry_failed=args.retry, overwrite=args.overwrite)
    processor.print_summary()


if __name__ == "__main__":
    main()
