"""
CityVeins项目工具包
包含各种数据处理和API调用的工具模块

该包已重构为子包结构，相关功能被分类到file、poi、http和residential子包中。

子包结构:
- file: 文件处理相关功能
  - file_handler: 文件读写工具
  - key_loader: API密钥加载工具
  - weight_loader: 权重配置加载工具
- poi: POI数据处理相关功能
  - geocode: 地理编码工具
  - get_district_boundary: 行政区边界获取工具
  - poi_fetcher: POI数据获取工具
  - poi_filter: POI过滤工具
  - poi_processor: POI处理和统计工具
- http: HTTP请求相关功能
  - http_client: 带重试和限速机制的HTTP客户端
- residential: 住宅区信息处理相关功能
  - residential_info: 住宅区信息获取工具

使用示例:
# 导入文件处理工具
from .file import file_handler, key_loader, weight_loader

# 导入POI处理工具
from .poi import geocode, get_district_boundary, poi_fetcher, poi_filter, poi_processor

# 导入HTTP请求工具
from .http import make_session, RateLimitedSession

# 导入住宅区信息处理工具
from .residential import get_residential_info
"""

# 为了保持向后兼容性，这里导入常用函数
from .poi.geocode import geocode
from .poi.poi_fetcher import get_pois
from .file.weight_loader import load_weight_config
from .file.file_handler import read_poi_file, save_category_stats
from .poi.poi_processor import calculate_weighted_score
from .http.http_client import make_session, RateLimitedSession
from .residential.residential_info import get_residential_info

__all__ = [
    "geocode",
    "get_pois",
    "load_weight_config",
    "read_poi_file",
    "save_category_stats",
    "calculate_weighted_score",
    "make_session",
    "RateLimitedSession",
    "get_residential_info",
]
