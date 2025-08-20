#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CityVeins GUI应用
使用PyQt开发的图形用户界面，用于调用CityVeins后端功能
"""

import os
import sys
import json
import pandas as pd
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTabWidget,
        QTextEdit,
        QFileDialog,
        QComboBox,
        QCheckBox,
        QSpinBox,
        QDoubleSpinBox,
        QProgressBar,
        QMessageBox,
        QGroupBox,
        QFormLayout,
        QRadioButton,
        QButtonGroup,
        QSplitter,
        QFrame,
        QStatusBar,
        QAction,
        QMenu,
        QMenuBar,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
    from PyQt5.QtGui import QIcon, QFont, QPixmap, QTextCursor
except ImportError:
    print("错误：未找到PyQt5库，请先安装：pip install pyqt5")
    sys.exit(1)

# 导入项目模块
from generate_report_fixed import markdown_to_html, generate_markdown_report
from utils.poi.poi_filter import filter_poi_types
from utils.poi.poi_analysis import calculate_weighted_score
from utils.file.weight_loader import load_weight_config
from utils.file.file_handler import save_category_stats
from config import WEIGHT_FILE, OUTPUT_DIR


# 工作线程类，用于执行耗时操作，避免阻塞GUI
class WorkerThread(QThread):
    """工作线程基类"""

    progress_updated = pyqtSignal(int, str)  # 进度更新信号
    finished = pyqtSignal(dict)  # 完成信号
    error_occurred = pyqtSignal(str)  # 错误信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def stop(self):
        """停止线程"""
        self._is_running = False
        self.wait()


class POIFetchWorker(WorkerThread):
    """获取POI数据的工作线程"""

    def __init__(
        self,
        residential_id,
        name=None,
        address=None,
        filter_poi=True,
        filter_level="category",
        threshold=0.4,
        radius=1200,
    ):
        super().__init__()
        self.residential_id = residential_id
        self.name = name
        self.address = address
        self.filter_poi = filter_poi
        self.filter_level = filter_level
        self.threshold = threshold
        self.radius = radius

    def run(self):
        """执行获取POI数据的任务"""
        try:
            self.progress_updated.emit(10, "初始化参数...")

            # 导入必要的模块
            from get_single_residential_poi_fixed import (
                main as get_residential_poi_data,
            )

            # 设置过滤参数
            filter_category = True
            filter_subcategory = False
            filter_smallcategory = False

            if self.filter_level == "subcategory":
                filter_subcategory = True
            elif self.filter_level == "smallcategory":
                filter_subcategory = True
                filter_smallcategory = True

            self.progress_updated.emit(30, "获取住宅区信息...")

            # 获取住宅区POI数据
            # 注意：main函数不支持直接传递所有参数，需要通过全局变量设置
            import get_single_residential_poi_fixed as poi_module

            # 设置全局变量
            poi_module.FILTER_LOW_WEIGHT_POI = self.filter_poi
            poi_module.FILTER_CATEGORY = filter_category
            poi_module.FILTER_SUBCATEGORY = filter_subcategory
            poi_module.FILTER_SMALLCATEGORY = filter_smallcategory
            poi_module.POI_WEIGHT_THRESHOLD = self.threshold
            poi_module.RADIUS = self.radius

            # 调用main函数
            get_residential_poi_data(
                residential_id=self.residential_id, name=self.name, address=self.address
            )

            # 构造返回结果
            poi_file = os.path.join(
                poi_module.OUTPUT_DIR, "poi", f"poi_{self.residential_id}.csv"
            )
            result = {"poi_file": poi_file, "stats": {}}

            self.progress_updated.emit(90, "完成处理...")

            # 返回结果
            self.finished.emit(
                {
                    "success": True,
                    "message": "POI数据获取成功",
                    "poi_file": result.get("poi_file"),
                    "stats": result.get("stats", {}),
                }
            )

        except Exception as e:
            self.error_occurred.emit(
                f"获取POI数据失败: {str(e)}\n{traceback.format_exc()}"
            )


class ScoreCalcWorker(WorkerThread):
    """计算得分的工作线程"""

    def __init__(self, poi_file, stats_dir=None):
        super().__init__()
        self.poi_file = poi_file
        self.stats_dir = stats_dir

    def run(self):
        """执行计算得分的任务"""
        try:
            self.progress_updated.emit(10, "检查POI文件...")

            # 检查POI文件是否存在
            if not os.path.exists(self.poi_file):
                raise FileNotFoundError(f"POI文件不存在: {self.poi_file}")

            # 从文件路径提取住宅区ID
            base_name = os.path.basename(self.poi_file)
            if base_name.startswith("poi_") and base_name.endswith(".csv"):
                residential_id = base_name[4:-4]
            else:
                residential_id = os.path.splitext(base_name)[0]

            # 创建统计目录
            if self.stats_dir is None:
                stats_dir = os.path.join(
                    os.path.dirname(self.poi_file), f"stats_poi_{residential_id}"
                )
            else:
                stats_dir = self.stats_dir

            os.makedirs(stats_dir, exist_ok=True)

            self.progress_updated.emit(30, "加载权重配置...")

            # 加载权重配置
            weight_map = load_weight_config(WEIGHT_FILE)

            self.progress_updated.emit(50, "计算加权得分...")

            # 计算加权得分和分类统计
            total_score, poi_count, category_stats_df = calculate_weighted_score(
                self.poi_file, weight_map
            )

            # 将DataFrame转换为字典格式，以便保存为JSON
            category_stats = {
                "all": category_stats_df.to_dict("records"),
                "big": category_stats_df[category_stats_df["类型"] == "大类"].to_dict(
                    "records"
                ),
                "mid": category_stats_df[category_stats_df["类型"] == "中类"].to_dict(
                    "records"
                ),
                "small": category_stats_df[category_stats_df["类型"] == "小类"].to_dict(
                    "records"
                ),
            }

            self.progress_updated.emit(70, "保存统计结果...")

            # 保存分类统计
            # 从DataFrame中提取不同级别的分类统计
            big_category_df = category_stats_df[category_stats_df["类型"] == "大类"]
            mid_category_df = category_stats_df[category_stats_df["类型"] == "中类"]
            small_category_df = category_stats_df[category_stats_df["类型"] == "小类"]

            # 调用save_category_stats函数
            save_category_stats(
                big_category_df,
                mid_category_df,
                small_category_df,
                stats_dir,
                residential_id,
            )

            # 保存得分结果
            score_file = os.path.join(stats_dir, f"score_{residential_id}.csv")
            score_data = {
                "住宅区ID": [residential_id],
                "POI总数": [poi_count],
                "加权得分": [total_score],
                "平均权重": [total_score / poi_count if poi_count > 0 else 0],
            }
            score_df = pd.DataFrame(score_data)
            score_df.to_csv(score_file, index=False, encoding="utf-8-sig")

            # 生成汇总JSON文件
            summary = {
                "residential_id": residential_id,
                "total_score": total_score,
                "poi_count": poi_count,
                "big_category_count": len(category_stats.get("big", [])),
                "mid_category_count": len(category_stats.get("mid", [])),
                "small_category_count": len(category_stats.get("small", [])),
                "timestamp": datetime.now().isoformat(),
            }

            summary_file = os.path.join(stats_dir, "summary.json")
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            self.progress_updated.emit(90, "完成处理...")

            # 返回结果
            self.finished.emit(
                {
                    "success": True,
                    "message": "得分计算成功",
                    "stats_dir": stats_dir,
                    "summary": summary,
                }
            )

        except Exception as e:
            self.error_occurred.emit(
                f"计算得分失败: {str(e)}\n{traceback.format_exc()}"
            )


def get_community_name(residential_id: str, stats_dir: str) -> Optional[str]:
    """
    从CSV文件中读取社区名称

    Args:
        residential_id (str): 住宅区ID
        stats_dir (str): 统计数据目录路径

    Returns:
        Optional[str]: 社区名称，如果找不到则返回None
    """
    try:
        # 尝试从POI数据文件中获取住宅区名称
        poi_file = os.path.join(os.path.dirname(stats_dir), f"poi_{residential_id}.csv")
        if os.path.exists(poi_file):
            poi_df = pd.read_csv(poi_file)
            if "住宅区名称" in poi_df.columns:
                community_name = poi_df["住宅区名称"].iloc[0]  # 取第一个住宅区名称
                print(f"已从CSV文件读取到社区名称: {community_name}")
                return community_name
            else:
                print("警告：CSV文件中未找到'住宅区名称'列")
        else:
            print(f"警告：未找到POI数据文件: {poi_file}")
    except Exception as e:
        print(f"警告：无法从CSV文件读取住宅区名称: {str(e)}")

    return None


class ReportGenerateWorker(WorkerThread):
    """生成报告的工作线程"""

    def __init__(self, residential_id, stats_dir, output_file=None, generate_html=True):
        super().__init__()
        self.residential_id = residential_id
        self.stats_dir = stats_dir
        self.output_file = output_file
        self.generate_html = generate_html

    def run(self):
        """执行生成报告的任务"""
        try:
            self.progress_updated.emit(10, "初始化参数...")

            # 自动从CSV文件中读取社区名称
            community_name = get_community_name(self.residential_id, self.stats_dir)

            self.progress_updated.emit(30, "生成Markdown报告...")

            # 生成Markdown报告
            report = generate_markdown_report(
                self.residential_id, self.stats_dir, community_name
            )

            # 确定Markdown输出文件路径
            if self.output_file:
                md_file = self.output_file
                if not md_file.endswith(".md"):
                    md_file = os.path.splitext(md_file)[0] + ".md"
            else:
                md_file = os.path.join(
                    self.stats_dir, f"{self.residential_id}_评估报告.md"
                )

            # 写入Markdown报告文件
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(report)

            self.progress_updated.emit(60, "保存报告文件...")

            result = {"markdown": md_file}

            # 如果需要生成HTML文件
            if self.generate_html:
                self.progress_updated.emit(80, "转换为HTML格式...")

                # 确定HTML输出文件路径
                html_file = os.path.splitext(md_file)[0] + ".html"

                # 转换Markdown到HTML
                success = markdown_to_html(md_file, html_file)
                if success:
                    result["html"] = html_file

            self.progress_updated.emit(90, "完成处理...")

            # 返回结果
            self.finished.emit(
                {"success": True, "message": "报告生成成功", "files": result}
            )

        except Exception as e:
            self.error_occurred.emit(
                f"生成报告失败: {str(e)}\n{traceback.format_exc()}"
            )


# 主窗口类
class CityVeinsGUI(QMainWindow):
    """CityVeins GUI主窗口"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.worker_thread = None

    def init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("CityVeins - 15分钟生活圈评估系统")
        self.setGeometry(100, 100, 1000, 700)
        self.setWindowIcon(QIcon())

        # 创建菜单栏
        self.create_menu_bar()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建选项卡部件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建各个选项卡
        self.create_poi_tab()
        self.create_score_tab()
        self.create_report_tab()

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 显示窗口
        self.show()

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def create_poi_tab(self):
        """创建POI获取选项卡"""
        # 创建选项卡部件
        poi_tab = QWidget()
        self.tab_widget.addTab(poi_tab, "获取POI数据")

        # 创建主布局
        layout = QVBoxLayout(poi_tab)

        # 创建输入区域
        input_group = QGroupBox("住宅区信息")
        input_layout = QFormLayout(input_group)

        # 住宅区ID输入
        self.residential_id_input = QLineEdit()
        input_layout.addRow("住宅区ID:", self.residential_id_input)

        # 住宅区名称输入
        self.name_input = QLineEdit()
        input_layout.addRow("住宅区名称(可选):", self.name_input)

        # 住宅区地址输入
        self.address_input = QLineEdit()
        input_layout.addRow("住宅区地址(可选):", self.address_input)

        layout.addWidget(input_group)

        # 创建参数设置区域
        param_group = QGroupBox("参数设置")
        param_layout = QFormLayout(param_group)

        # 搜索半径
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(100, 5000)
        self.radius_spin.setValue(1200)
        self.radius_spin.setSuffix(" 米")
        param_layout.addRow("搜索半径:", self.radius_spin)

        # POI过滤
        self.filter_poi_check = QCheckBox("启用POI过滤")
        self.filter_poi_check.setChecked(True)
        param_layout.addRow("", self.filter_poi_check)

        # 过滤级别
        self.filter_level_combo = QComboBox()
        self.filter_level_combo.addItems(["大类", "中类", "小类"])
        param_layout.addRow("过滤级别:", self.filter_level_combo)

        # 权重阈值
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setValue(0.4)
        self.threshold_spin.setSingleStep(0.1)
        self.threshold_spin.setDecimals(1)
        param_layout.addRow("权重阈值:", self.threshold_spin)

        layout.addWidget(param_group)

        # 创建按钮区域
        button_layout = QHBoxLayout()

        # 获取POI按钮
        self.fetch_poi_button = QPushButton("获取POI数据")
        self.fetch_poi_button.clicked.connect(self.fetch_poi_data)
        button_layout.addWidget(self.fetch_poi_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.poi_progress = QProgressBar()
        self.poi_progress.setVisible(False)
        layout.addWidget(self.poi_progress)

        # 创建输出区域
        output_group = QGroupBox("输出信息")
        output_layout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.poi_output = QTextEdit()
        self.poi_output.setReadOnly(True)
        output_layout.addWidget(self.poi_output)

        layout.addWidget(output_group)

    def create_score_tab(self):
        """创建得分计算选项卡"""
        # 创建选项卡部件
        score_tab = QWidget()
        self.tab_widget.addTab(score_tab, "计算得分")

        # 创建主布局
        layout = QVBoxLayout(score_tab)

        # 创建输入区域
        input_group = QGroupBox("输入设置")
        input_layout = QFormLayout(input_group)

        # POI文件选择
        poi_file_layout = QHBoxLayout()
        self.poi_file_input = QLineEdit()
        self.poi_file_input.setReadOnly(True)
        poi_file_layout.addWidget(self.poi_file_input)

        self.browse_poi_button = QPushButton("浏览...")
        self.browse_poi_button.clicked.connect(self.browse_poi_file)
        poi_file_layout.addWidget(self.browse_poi_button)

        input_layout.addRow("POI文件:", poi_file_layout)

        # 统计目录选择
        stats_dir_layout = QHBoxLayout()
        self.stats_dir_input = QLineEdit()
        self.stats_dir_input.setPlaceholderText("默认自动创建")
        stats_dir_layout.addWidget(self.stats_dir_input)

        self.browse_stats_button = QPushButton("浏览...")
        self.browse_stats_button.clicked.connect(self.browse_stats_dir)
        stats_dir_layout.addWidget(self.browse_stats_button)

        input_layout.addRow("统计目录:", stats_dir_layout)

        layout.addWidget(input_group)

        # 创建按钮区域
        button_layout = QHBoxLayout()

        # 计算得分按钮
        self.calc_score_button = QPushButton("计算得分")
        self.calc_score_button.clicked.connect(self.calculate_score)
        button_layout.addWidget(self.calc_score_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.score_progress = QProgressBar()
        self.score_progress.setVisible(False)
        layout.addWidget(self.score_progress)

        # 创建输出区域
        output_group = QGroupBox("输出信息")
        output_layout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.score_output = QTextEdit()
        self.score_output.setReadOnly(True)
        output_layout.addWidget(self.score_output)

        layout.addWidget(output_group)

    def create_report_tab(self):
        """创建报告生成选项卡"""
        # 创建选项卡部件
        report_tab = QWidget()
        self.tab_widget.addTab(report_tab, "生成报告")

        # 创建主布局
        layout = QVBoxLayout(report_tab)

        # 创建输入区域
        input_group = QGroupBox("输入设置")
        input_layout = QFormLayout(input_group)

        # 住宅区ID输入
        self.report_residential_id_input = QLineEdit()
        input_layout.addRow("住宅区ID:", self.report_residential_id_input)

        # 统计目录选择
        report_stats_dir_layout = QHBoxLayout()
        self.report_stats_dir_input = QLineEdit()
        report_stats_dir_layout.addWidget(self.report_stats_dir_input)

        self.browse_report_stats_button = QPushButton("浏览...")
        self.browse_report_stats_button.clicked.connect(self.browse_report_stats_dir)
        report_stats_dir_layout.addWidget(self.browse_report_stats_button)

        input_layout.addRow("统计目录:", report_stats_dir_layout)

        # 输出文件选择
        output_file_layout = QHBoxLayout()
        self.output_file_input = QLineEdit()
        self.output_file_input.setPlaceholderText("默认自动生成")
        output_file_layout.addWidget(self.output_file_input)

        self.browse_output_button = QPushButton("浏览...")
        self.browse_output_button.clicked.connect(self.browse_output_file)
        output_file_layout.addWidget(self.browse_output_button)

        input_layout.addRow("输出文件:", output_file_layout)

        layout.addWidget(input_group)

        # 创建选项区域
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout(options_group)

        # 生成HTML选项
        self.generate_html_check = QCheckBox("生成HTML格式报告")
        self.generate_html_check.setChecked(True)
        options_layout.addWidget(self.generate_html_check)

        layout.addWidget(options_group)

        # 创建按钮区域
        button_layout = QHBoxLayout()

        # 生成报告按钮
        self.generate_report_button = QPushButton("生成报告")
        self.generate_report_button.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_report_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.report_progress = QProgressBar()
        self.report_progress.setVisible(False)
        layout.addWidget(self.report_progress)

        # 创建输出区域
        output_group = QGroupBox("输出信息")
        output_layout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.report_output = QTextEdit()
        self.report_output.setReadOnly(True)
        output_layout.addWidget(self.report_output)

        layout.addWidget(output_group)

    def fetch_poi_data(self):
        """获取POI数据"""
        # 获取输入值
        residential_id = self.residential_id_input.text().strip()
        if not residential_id:
            QMessageBox.warning(self, "输入错误", "请输入住宅区ID")
            return

        name = self.name_input.text().strip() or None
        address = self.address_input.text().strip() or None
        radius = self.radius_spin.value()
        filter_poi = self.filter_poi_check.isChecked()
        filter_level = self.filter_level_combo.currentText()
        threshold = self.threshold_spin.value()

        # 转换过滤级别
        if filter_level == "大类":
            filter_level = "category"
        elif filter_level == "中类":
            filter_level = "subcategory"
        elif filter_level == "小类":
            filter_level = "smallcategory"

        # 清空输出区域
        self.poi_output.clear()

        # 显示进度条
        self.poi_progress.setVisible(True)
        self.poi_progress.setValue(0)

        # 禁用按钮
        self.fetch_poi_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread = POIFetchWorker(
            residential_id=residential_id,
            name=name,
            address=address,
            filter_poi=filter_poi,
            filter_level=filter_level,
            threshold=threshold,
            radius=radius,
        )

        # 连接信号
        self.worker_thread.progress_updated.connect(self.update_poi_progress)
        self.worker_thread.finished.connect(self.poi_fetch_finished)
        self.worker_thread.error_occurred.connect(self.poi_fetch_error)

        # 启动线程
        self.worker_thread.start()

    def calculate_score(self):
        """计算得分"""
        # 获取输入值
        poi_file = self.poi_file_input.text().strip()
        if not poi_file or not os.path.exists(poi_file):
            QMessageBox.warning(self, "输入错误", "请选择有效的POI文件")
            return

        stats_dir = self.stats_dir_input.text().strip() or None

        # 清空输出区域
        self.score_output.clear()

        # 显示进度条
        self.score_progress.setVisible(True)
        self.score_progress.setValue(0)

        # 禁用按钮
        self.calc_score_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread = ScoreCalcWorker(poi_file=poi_file, stats_dir=stats_dir)

        # 连接信号
        self.worker_thread.progress_updated.connect(self.update_score_progress)
        self.worker_thread.finished.connect(self.score_calc_finished)
        self.worker_thread.error_occurred.connect(self.score_calc_error)

        # 启动线程
        self.worker_thread.start()

    def generate_report(self):
        """生成报告"""
        # 获取输入值
        residential_id = self.report_residential_id_input.text().strip()
        if not residential_id:
            QMessageBox.warning(self, "输入错误", "请输入住宅区ID")
            return

        stats_dir = self.report_stats_dir_input.text().strip()
        if not stats_dir or not os.path.exists(stats_dir):
            QMessageBox.warning(self, "输入错误", "请选择有效的统计目录")
            return

        output_file = self.output_file_input.text().strip() or None
        generate_html = self.generate_html_check.isChecked()

        # 清空输出区域
        self.report_output.clear()

        # 显示进度条
        self.report_progress.setVisible(True)
        self.report_progress.setValue(0)

        # 禁用按钮
        self.generate_report_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread = ReportGenerateWorker(
            residential_id=residential_id,
            stats_dir=stats_dir,
            output_file=output_file,
            generate_html=generate_html,
        )

        # 连接信号
        self.worker_thread.progress_updated.connect(self.update_report_progress)
        self.worker_thread.finished.connect(self.report_generate_finished)
        self.worker_thread.error_occurred.connect(self.report_generate_error)

        # 启动线程
        self.worker_thread.start()

    def browse_poi_file(self):
        """浏览POI文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择POI文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if file_path:
            self.poi_file_input.setText(file_path)

    def browse_stats_dir(self):
        """浏览统计目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择统计目录", "")
        if dir_path:
            self.stats_dir_input.setText(dir_path)

    def browse_report_stats_dir(self):
        """浏览报告统计目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择统计目录", "")
        if dir_path:
            self.report_stats_dir_input.setText(dir_path)

    def browse_output_file(self):
        """浏览输出文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", "", "Markdown文件 (*.md);;所有文件 (*)"
        )
        if file_path:
            self.output_file_input.setText(file_path)

    def update_poi_progress(self, value, message):
        """更新POI获取进度"""
        self.poi_progress.setValue(value)
        self.poi_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor = self.poi_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.poi_output.setTextCursor(cursor)

    def update_score_progress(self, value, message):
        """更新得分计算进度"""
        self.score_progress.setValue(value)
        self.score_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor = self.score_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.score_output.setTextCursor(cursor)

    def update_report_progress(self, value, message):
        """更新报告生成进度"""
        self.report_progress.setValue(value)
        self.report_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor = self.report_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.report_output.setTextCursor(cursor)

    def poi_fetch_finished(self, result):
        """POI获取完成"""
        # 隐藏进度条
        self.poi_progress.setVisible(False)

        # 启用按钮
        self.fetch_poi_button.setEnabled(True)

        # 显示结果
        self.poi_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] 任务完成!")
        self.poi_output.append(f"POI文件: {result.get('poi_file', 'N/A')}")

        # 自动填充得分计算选项卡中的POI文件
        poi_file = result.get("poi_file")
        if poi_file and os.path.exists(poi_file):
            self.poi_file_input.setText(poi_file)

        # 自动填充报告生成选项卡中的住宅区ID和统计目录
        residential_id = self.residential_id_input.text().strip()
        if residential_id:
            self.report_residential_id_input.setText(residential_id)

            # 尝试确定统计目录
            stats_dir = os.path.join(
                os.path.dirname(poi_file), f"stats_poi_{residential_id}"
            )
            if os.path.exists(stats_dir):
                self.report_stats_dir_input.setText(stats_dir)

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "POI数据获取成功"))

    def poi_fetch_error(self, error_message):
        """POI获取错误"""
        # 隐藏进度条
        self.poi_progress.setVisible(False)

        # 启用按钮
        self.fetch_poi_button.setEnabled(True)

        # 显示错误
        self.poi_output.append(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 错误: {error_message}"
        )

        # 显示错误消息
        QMessageBox.critical(self, "错误", f"获取POI数据失败: {error_message}")

    def score_calc_finished(self, result):
        """得分计算完成"""
        # 隐藏进度条
        self.score_progress.setVisible(False)

        # 启用按钮
        self.calc_score_button.setEnabled(True)

        # 显示结果
        self.score_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] 任务完成!")
        self.score_output.append(f"统计目录: {result.get('stats_dir', 'N/A')}")

        # 显示汇总信息
        summary = result.get("summary", {})
        if summary:
            self.score_output.append("\n===== 汇总信息 =====")
            self.score_output.append(
                f"住宅区ID: {summary.get('residential_id', 'N/A')}"
            )
            self.score_output.append(f"加权总分: {summary.get('total_score', 0):.2f}")
            self.score_output.append(f"POI总数: {summary.get('poi_count', 0)}")
            self.score_output.append(
                f"大类数量: {summary.get('big_category_count', 0)}"
            )
            self.score_output.append(
                f"中类数量: {summary.get('mid_category_count', 0)}"
            )
            self.score_output.append(
                f"小类数量: {summary.get('small_category_count', 0)}"
            )

        # 自动填充报告生成选项卡中的统计目录
        stats_dir = result.get("stats_dir")
        if stats_dir and os.path.exists(stats_dir):
            self.report_stats_dir_input.setText(stats_dir)

            # 尝试从路径中提取住宅区ID
            path_parts = stats_dir.split(os.sep)
            for part in reversed(path_parts):
                if part.startswith("stats_poi_"):
                    residential_id = part[10:]  # 去掉"stats_poi_"前缀
                    self.report_residential_id_input.setText(residential_id)
                    break

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "得分计算成功"))

    def score_calc_error(self, error_message):
        """得分计算错误"""
        # 隐藏进度条
        self.score_progress.setVisible(False)

        # 启用按钮
        self.calc_score_button.setEnabled(True)

        # 显示错误
        self.score_output.append(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 错误: {error_message}"
        )

        # 显示错误消息
        QMessageBox.critical(self, "错误", f"计算得分失败: {error_message}")

    def report_generate_finished(self, result):
        """报告生成完成"""
        # 隐藏进度条
        self.report_progress.setVisible(False)

        # 启用按钮
        self.generate_report_button.setEnabled(True)

        # 显示结果
        self.report_output.append(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 任务完成!"
        )

        # 显示文件信息
        files = result.get("files", {})
        if files.get("markdown"):
            self.report_output.append(f"Markdown报告: {files['markdown']}")
        if files.get("html"):
            self.report_output.append(f"HTML报告: {files['html']}")

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "报告生成成功"))

    def report_generate_error(self, error_message):
        """报告生成错误"""
        # 隐藏进度条
        self.report_progress.setVisible(False)

        # 启用按钮
        self.generate_report_button.setEnabled(True)

        # 显示错误
        self.report_output.append(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 错误: {error_message}"
        )

        # 显示错误消息
        QMessageBox.critical(self, "错误", f"生成报告失败: {error_message}")

    def show_about_dialog(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于CityVeins",
            "CityVeins - 15分钟生活圈评估系统\n\n"
            "本系统用于评估住宅区周边15分钟生活圈的便利性，\n"
            "通过获取POI数据、计算得分和生成报告，\n"
            "为城市规划和居民生活提供参考。\n"
            "版本: 1.0\n"
            "作者: CityVeins Team",
        )


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("CityVeins")
    app.setApplicationVersion("1.0")

    # 设置应用程序样式
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window = CityVeinsGUI()

    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
