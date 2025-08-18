"""
高德API密钥加载工具

该模块提供了从文件中加载高德API密钥的功能，支持自定义密钥文件路径。
密钥文件应仅包含一行密钥，不含多余空格或换行符。

功能：
1. 从指定文件路径加载API密钥
2. 验证文件存在性和内容有效性
3. 提供错误处理和异常提示

使用示例:
from . import load_key
api_key = load_key("path/to/keyfile.txt")
"""

import os
import sys
from typing import Optional

# 尝试从config导入KEY_FILE，如果失败则使用默认值
try:
    from config import KEY_FILE
except ImportError:
    # 如果无法导入config，使用默认路径
    ROOT_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    KEY_FILE = os.path.join(ROOT_DIR, "data", "key", "key.txt")


def load_key(path: str = KEY_FILE) -> str:
    """
    从指定文本文件读取高德API密钥

    文件需仅含一行Key，不含多余空格/换行。
    若文件不存在或为空，将抛出FileNotFoundError/ValueError。

    Args:
        path (str): 密钥文件路径，默认从config中读取KEY_FILE

    Returns:
        str: 高德API密钥字符串

    Raises:
        FileNotFoundError: 当密钥文件不存在时抛出此异常
        ValueError: 当密钥文件为空或内容无效时抛出此异常
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"密钥文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        key: str = f.read().strip()

    if not key:
        raise ValueError(f"密钥文件为空: {path}")

    return key


if __name__ == "__main__":
    try:
        key = load_key()
        print(f"高德API密钥: {key}")
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
