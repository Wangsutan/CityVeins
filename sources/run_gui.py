#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CityVeins GUI启动脚本
用于启动CityVeins图形用户界面
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """主函数"""
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
