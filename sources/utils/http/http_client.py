"""
HTTP客户端工具模块

提供带重试和限速机制的HTTP请求功能，适用于高频率API调用场景。
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional


def make_session(
    total_retries: int = 5,
    backoff_factor: float = 1,
    status_forcelist: Optional[list] = None,
    allowed_methods: Optional[set] = None,
    raise_on_status: bool = False,
) -> requests.Session:
    """
    创建带有重试机制的HTTP会话

    该函数创建一个配置了重试策略的requests.Session对象，
    用于处理网络请求中可能出现的临时性错误，
    如服务器错误(5xx)和网络问题。

    Args:
        total_retries (int): 最多重试次数，默认为5
        backoff_factor (float): 退避因子，默认为1，表示1s, 2s, 4s...
        status_forcelist (list, optional): 需要重试的HTTP状态码列表，默认为[500, 502, 503, 504]
        allowed_methods (set, optional): 需要重试的HTTP方法集合，默认为{"GET"}
        raise_on_status (bool): 重试失败后是否抛出异常，默认为False

    Returns:
        requests.Session: 配置好重试策略的会话对象
    """
    if status_forcelist is None:
        status_forcelist = [500, 502, 503, 504]

    if allowed_methods is None:
        allowed_methods = {"GET"}

    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
        raise_on_status=raise_on_status,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    # 全局限速标记
    s.last_req = 0.0
    return s


class RateLimitedSession:
    """
    带限速的HTTP会话类

    该类封装了requests.Session，并添加了限速功能，确保两次请求之间
    至少间隔指定的时间，避免API请求频率过高导致被限流。
    """

    def __init__(self, min_interval: float = 0.2, **session_kwargs):
        """
        初始化限速会话

        Args:
            min_interval (float): 两次请求之间的最小间隔时间（秒），默认为0.2秒
            **session_kwargs: 传递给make_session的参数
        """
        self.session = make_session(**session_kwargs)
        self.min_interval = min_interval

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        带限速的GET请求

        确保两次请求之间至少间隔min_interval秒，避免API请求频率过高。

        Args:
            url (str): 请求的URL
            **kwargs: 传递给requests.get的其他参数

        Returns:
            requests.Response: HTTP响应对象
        """
        elapsed = time.time() - self.session.last_req
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        # 设置默认超时
        if "timeout" not in kwargs:
            kwargs["timeout"] = 15

        resp = self.session.get(url, **kwargs)
        self.session.last_req = time.time()
        return resp

    def post(self, url: str, **kwargs) -> requests.Response:
        """
        带限速的POST请求

        确保两次请求之间至少间隔min_interval秒，避免API请求频率过高。

        Args:
            url (str): 请求的URL
            **kwargs: 传递给requests.post的其他参数

        Returns:
            requests.Response: HTTP响应对象
        """
        elapsed = time.time() - self.session.last_req
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        # 设置默认超时
        if "timeout" not in kwargs:
            kwargs["timeout"] = 15

        resp = self.session.post(url, **kwargs)
        self.session.last_req = time.time()
        return resp
