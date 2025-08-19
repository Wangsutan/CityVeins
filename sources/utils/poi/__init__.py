"""POI处理工具包

该子包提供了CityVeins项目中与POI数据处理相关的工具函数和类。

模块结构:
- geocode: 地理编码工具
- get_district_boundary: 行政区边界获取工具
- poi_fetcher: POI数据获取工具
- poi_filter: POI过滤工具
- poi_analysis: POI处理和统计工具

使用示例:
from . import geocode, get_district_boundary, poi_fetcher, poi_filter, poi_analysis
"""

from .geocode import geocode
from .get_district_boundary import get_district_boundary
from .poi_fetcher import get_pois
from .poi_filter import filter_poi_types, get_poi_type_stats
from .poi_analysis import calculate_weighted_score, generate_score_report

__all__ = [
    "geocode",
    "get_district_boundary",
    "get_valid_boundary",
    "get_pois",
    "filter_poi_types",
    "get_poi_type_stats",
    "calculate_weighted_score",
    "generate_score_report",
]
