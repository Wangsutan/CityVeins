"""
CityVeins 项目配置文件

该文件定义了整个项目使用的各种路径和常量，
包括数据目录、输出目录、API密钥文件路径、POI权重文件路径等。
集中管理这些配置，
便于项目维护和路径调整。

配置项说明：
- ROOT_DIR: 项目根目录
- DATA_DIR: 数据存储目录，包含权重文件、密钥文件等
- OUTPUT_DIR: 输出结果目录，包含处理后的CSV文件和统计结果
- KEY_FILE: 高德地图API密钥文件路径
- WEIGHT_FILE: POI权重配置文件路径，用于计算生活圈得分
- POI_CODE_FILE: POI分类编码文件路径，包含高德POI分类与编码信息
- RESIDENTIAL_OUT: 住宅区数据输出路径生成函数
- POI_OUT: 单个住宅区POI数据输出路径生成函数

使用方法:
其他模块通过导入此文件获取配置，例如:
from config import DATA_DIR, OUTPUT_DIR
"""

import os
from typing import Callable, Final


# 项目根目录
ROOT_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))

# 数据目录，存储权重文件、密钥文件等
DATA_DIR: Final[str] = os.path.join(ROOT_DIR, "data")

# 输出目录，存储处理结果和统计数据
OUTPUT_DIR: Final[str] = os.path.join(ROOT_DIR, "output")

# 高德地图API密钥文件路径
KEY_FILE: Final[str] = os.path.join(DATA_DIR, "key", "key.txt")

# POI权重配置文件路径，包含各类POI的权重
WEIGHT_FILE: Final[str] = os.path.join(DATA_DIR, "poi_weights", "高德POI_加权.csv")

# POI分类编码文件路径，包含高德POI分类与编码信息
POI_CODE_FILE: Final[str] = os.path.join(
    DATA_DIR, "poi_code", "高德POI分类与编码（中英文）_V1.06_20230208.csv"
)

# 住宅区数据输出路径生成函数
# 参数: d - 行政区名称
# 返回: 该行政区住宅区数据CSV文件的完整路径
RESIDENTIAL_OUT: Callable[[str], str] = lambda d: os.path.join(
    DATA_DIR, "residential", f"residential_{d}.csv"
)

# 单个住宅区POI数据输出路径生成函数
# 参数: rid - 住宅区ID
# 返回: 该住宅区POI数据CSV文件的完整路径
POI_OUT: Callable[[str], str] = lambda rid: os.path.join(
    OUTPUT_DIR, "poi", f"poi_{rid}.csv"
)
