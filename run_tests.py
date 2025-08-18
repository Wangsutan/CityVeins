"""
测试运行脚本

该脚本用于运行CityVeins项目的所有单元测试，包括utils模块下所有子模块的测试。
"""

import unittest
import sys
import os
from typing import Final

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests() -> bool:
    """运行所有测试"""
    # 发现并运行所有测试
    loader: unittest.TestLoader = unittest.TestLoader()
    start_dir: Final[str] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "tests"
    )
    suite: unittest.TestSuite = loader.discover(start_dir, pattern="test_*.py")

    # 运行测试
    runner: unittest.TextTestRunner = unittest.TextTestRunner(verbosity=2)
    result: unittest.TestResult = runner.run(suite)

    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    # 运行测试并输出结果
    success: bool = run_tests()
    sys.exit(0 if success else 1)
