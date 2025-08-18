"""
住宅区信息处理模块

提供住宅区信息获取和处理的工具函数。
"""

import os
import pandas as pd
from typing import Optional, Tuple
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)
from config import RESIDENTIAL_OUT


def get_residential_info(
    residential_id: str, district: str = "田家庵区"
) -> Tuple[Optional[str], Optional[str]]:
    """
    从住宅区数据文件中获取指定ID的住宅区信息

    Args:
        residential_id (str): 住宅区ID
        district (str): 行政区名称，默认为"田家庵区"

    Returns:
        tuple: (住宅区名称, 住宅区地址) 或 (None, None) 如果未找到
    """
    try:
        # 尝试从多个可能的位置查找住宅区数据文件
        possible_paths = [
            RESIDENTIAL_OUT(district),  # 使用配置文件中的路径
            os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                ),
                "data",
                "residential",
                f"residential_{district}.csv",
            ),
        ]

        residential_file = None
        for path in possible_paths:
            if os.path.exists(path):
                residential_file = path
                break

        if not residential_file:
            print("未找到住宅区数据文件")
            return None, None

        df = pd.read_csv(residential_file)
        residential = df[df["id"] == residential_id]

        if residential.empty:
            print(f"未找到ID为 {residential_id} 的住宅区")
            return None, None

        name = residential.iloc[0]["name"]
        address = residential.iloc[0].get("address", "")
        return name, address
    except Exception as e:
        print(f"获取住宅区信息失败: {str(e)}")
        return None, None
