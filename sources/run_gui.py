#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CityVeins GUI启动脚本
用于启动CityVeins图形用户界面

该脚本是CityVeins项目的入口点，负责初始化并启动图形用户界面。
它会检查必要的依赖项，并处理可能出现的导入错误。

使用方法:
    python sources/run_gui.py

依赖:
    - PyQt5: 用于构建图形用户界面
    - 其他CityVeins项目模块
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    """
    主函数 - 启动CityVeins GUI应用
    
    本函数负责创建Qt应用程序实例，初始化主窗口，并启动事件循环。
    它还处理可能出现的导入错误和其他异常，提供友好的错误信息。
    
    异常:
        ImportError: 当缺少必要的依赖库时抛出
        Exception: 当启动GUI应用过程中出现其他错误时抛出
    """
    try:
        from PyQt5.QtWidgets import QApplication
        from cityveins_gui import CityVeinsGUI

        # 创建应用
        app = QApplication(sys.argv)
        app.setApplicationName("CityVeins")
        app.setApplicationVersion("1.0")

        # 创建主窗口
        window = CityVeinsGUI()

        # 运行应用
        sys.exit(app.exec_())

    except ImportError as e:
        print(f"错误：缺少必要的依赖库: {str(e)}")
        print("请安装必要的依赖：pip install pyqt5")
        sys.exit(1)
    except Exception as e:
        print(f"启动GUI应用失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
