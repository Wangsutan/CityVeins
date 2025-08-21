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
from typing import Dict, List, Any, Optional, Union, Tuple

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
        QStackedWidget,
        QDialog,
        QListWidget,
        QDialogButtonBox,
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
from query_residential import (
    query_by_id,
    query_by_name,
    query_by_coordinates,
    get_residential_details,
)
from config import WEIGHT_FILE, OUTPUT_DIR, KEY_FILE, DATA_DIR
# 在文件顶部的导入部分，修改导入语句
try:
    from utils.api.api_buttons import APIButtonsWidget
except ImportError as e:
    print(f"无法导入API按钮组件: {str(e)}")
    # 添加一个空的占位类，防止程序崩溃
    class APIButtonsWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setVisible(False)  # 隐藏这个占位组件


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
        longitude=None,
        latitude=None,
    ):
        super().__init__()
        self.residential_id = residential_id
        self.name = name
        self.address = address
        self.filter_poi = filter_poi
        self.filter_level = filter_level
        self.threshold = threshold
        self.radius = radius
        self.longitude = longitude
        self.latitude = latitude

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

            # 如果提供了经纬度，设置经纬度参数
            if self.longitude is not None and self.latitude is not None:
                poi_module.LONGITUDE = self.longitude
                poi_module.LATITUDE = self.latitude

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

    def __init__(self, poi_file, stats_dir=None, weight_file=None):
        super().__init__()
        self.poi_file = poi_file
        self.stats_dir = stats_dir
        self.weight_file = weight_file

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
            # 优先使用用户选择的权重文件
            if self.weight_file and os.path.exists(self.weight_file):
                weight_file = self.weight_file
                self.progress_updated.emit(40, f"使用用户选择的权重配置: {os.path.basename(self.weight_file)}")
            else:
                # 如果用户没有选择权重文件，则优先使用自定义权重文件
                custom_weight_file = os.path.join(DATA_DIR, "poi_weights", "高德POI_加权_自定义.csv")
                if os.path.exists(custom_weight_file):
                    weight_file = custom_weight_file
                    self.progress_updated.emit(40, f"使用自定义权重配置: {os.path.basename(custom_weight_file)}")
                else:
                    weight_file = WEIGHT_FILE
                    self.progress_updated.emit(40, f"使用默认权重配置: {os.path.basename(WEIGHT_FILE)}")

            weight_map = load_weight_config(weight_file)

            self.progress_updated.emit(50, "计算加权得分...")

            # 检查是否存在去重后的POI文件
            dedup_file = self.poi_file.replace(".csv", "_unique.csv")
            if os.path.exists(dedup_file):
                # 使用去重后的POI文件进行计分
                poi_file_for_score = dedup_file
                self.progress_updated.emit(
                    45, f"使用去重后的POI数据: {os.path.basename(dedup_file)}"
                )
            else:
                # 使用原始POI文件进行计分
                poi_file_for_score = self.poi_file
                self.progress_updated.emit(45, "使用原始POI数据（未找到去重文件）")

            # 计算加权得分和分类统计
            total_score, poi_count, category_stats_df = calculate_weighted_score(
                poi_file_for_score, weight_map
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

            summary_file: str = os.path.join(stats_dir, "summary.json")
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
        # 尝试从去重后的POI数据文件中获取住宅区名称
        dedup_poi_file: str = os.path.join(
            os.path.dirname(stats_dir), f"poi_{residential_id}_unique.csv"
        )
        poi_file: str = os.path.join(
            os.path.dirname(stats_dir), f"poi_{residential_id}.csv"
        )

        # 优先使用去重后的POI文件
        file_to_use = dedup_poi_file if os.path.exists(dedup_poi_file) else poi_file

        if os.path.exists(file_to_use):
            poi_df: pd.DataFrame = pd.read_csv(file_to_use)
            if "住宅区名称" in poi_df.columns:
                community_name: str = poi_df["住宅区名称"].iloc[0]  # 取第一个住宅区名称
                print(f"已从CSV文件读取到社区名称: {community_name}")
                return community_name
            else:
                print("警告：CSV文件中未找到'住宅区名称'列")
        else:
            print(f"警告：未找到POI数据文件: {file_to_use}")
    except Exception as e:
        print(f"警告：无法从CSV文件读取住宅区名称: {str(e)}")

    return None


class ReportGenerateWorker(WorkerThread):
    """生成报告的工作线程"""

    def __init__(
        self,
        residential_id: str,
        stats_dir: str,
        output_file: Optional[str] = None,
        generate_html: bool = True,
    ) -> None:
        super().__init__()
        self.residential_id: str = residential_id
        self.stats_dir: str = stats_dir
        self.output_file: Optional[str] = output_file
        self.generate_html: bool = generate_html

    def run(self) -> None:
        """执行生成报告的任务"""
        try:
            self.progress_updated.emit(10, "初始化参数...")

            # 自动从CSV文件中读取社区名称
            community_name: Optional[str] = get_community_name(
                self.residential_id, self.stats_dir
            )

            self.progress_updated.emit(30, "生成Markdown报告...")

            # 生成Markdown报告
            report: str = generate_markdown_report(
                self.residential_id, self.stats_dir, community_name
            )

            # 确定Markdown输出文件路径
            if self.output_file:
                md_file: str = self.output_file
                if not md_file.endswith(".md"):
                    md_file = os.path.splitext(md_file)[0] + ".md"
            else:
                # 使用社区名称作为文件名，如果没有社区名称则使用ID
                if community_name:
                    md_file: str = os.path.join(
                        self.stats_dir, f"{community_name}_评估报告.md"
                    )
                else:
                    md_file: str = os.path.join(
                        self.stats_dir, f"{self.residential_id}_评估报告.md"
                    )

            # 写入Markdown报告文件
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(report)

            self.progress_updated.emit(60, "保存报告文件...")

            result: Dict[str, str] = {"markdown": md_file}

            # 如果需要生成HTML文件
            if self.generate_html:
                self.progress_updated.emit(80, "转换为HTML格式...")

                # 确定HTML输出文件路径
                html_file: str = os.path.splitext(md_file)[0] + ".html"

                # 转换Markdown到HTML
                success: bool = markdown_to_html(md_file, html_file)
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

    def __init__(self) -> None:
        super().__init__()
        self.weight_file = None  # 存储当前选择的权重文件路径
        self.init_ui()
        self.worker_thread: Optional[WorkerThread] = None

    def init_ui(self) -> None:
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("CityVeins - 15分钟生活圈评估系统")
        self.setGeometry(100, 100, 500, 700)
        self.setWindowIcon(QIcon())

        # 创建菜单栏
        self.create_menu_bar()

        # 创建中央部件
        central_widget: QWidget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout: QVBoxLayout = QVBoxLayout(central_widget)

        # 创建顶部布局（用于放置API按钮）
        top_layout: QHBoxLayout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 5)
        
        # 添加弹性空间，将按钮推到右侧
        top_layout.addStretch()
        
        # 导入并添加API按钮组件
        try:
            self.api_buttons_widget = APIButtonsWidget()
            top_layout.addWidget(self.api_buttons_widget)
        except Exception as e:
            # 如果导入失败，显示错误信息但不影响程序运行
            error_label = QLabel("API按钮组件加载失败")
            error_label.setStyleSheet("color: red;")
            top_layout.addWidget(error_label)
            print(f"API按钮组件加载失败: {str(e)}")
        
        # 将顶部布局添加到主布局
        main_layout.addLayout(top_layout)

        # 创建选项卡部件
        self.tab_widget: QTabWidget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建各个选项卡
        self.create_poi_tab()
        self.create_score_tab()
        self.create_report_tab()

        # 创建状态栏
        self.status_bar: QStatusBar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 显示窗口
        self.show()

    def create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar: QMenuBar = self.menuBar()

        # 文件菜单
        file_menu: QMenu = menubar.addMenu("文件")

        exit_action: QAction = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu: QMenu = menubar.addMenu("帮助")

        about_action: QAction = QAction("关于", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def create_poi_tab(self) -> None:
        """创建POI获取选项卡"""
        # 创建选项卡部件
        poi_tab: QWidget = QWidget()
        self.tab_widget.addTab(poi_tab, "获取POI数据")

        # 创建主布局
        layout: QVBoxLayout = QVBoxLayout(poi_tab)

        # 创建查询方式选择区域
        query_method_group: QGroupBox = QGroupBox("查询方式")
        query_method_layout: QVBoxLayout = QVBoxLayout(query_method_group)

        # 创建单选按钮组
        self.query_method_group: QButtonGroup = QButtonGroup()

        # ID查询选项
        self.id_radio: QRadioButton = QRadioButton("住宅区ID查询")
        self.id_radio.setChecked(True)  # 默认选中
        self.query_method_group.addButton(self.id_radio)
        query_method_layout.addWidget(self.id_radio)

        # 名称查询选项
        self.name_radio: QRadioButton = QRadioButton("住宅区名称查询")
        self.query_method_group.addButton(self.name_radio)
        query_method_layout.addWidget(self.name_radio)

        # 经纬度查询选项
        self.coord_radio: QRadioButton = QRadioButton("经纬度查询")
        self.query_method_group.addButton(self.coord_radio)
        query_method_layout.addWidget(self.coord_radio)

        # 连接信号
        self.id_radio.toggled.connect(lambda: self.toggle_query_method("id"))
        self.name_radio.toggled.connect(lambda: self.toggle_query_method("name"))
        self.coord_radio.toggled.connect(lambda: self.toggle_query_method("coord"))

        layout.addWidget(query_method_group)

        # 创建输入区域
        input_group: QGroupBox = QGroupBox("住宅区信息")
        input_layout: QFormLayout = QFormLayout(input_group)

        # 创建堆叠小部件，用于切换不同的输入界面
        self.input_stack: QStackedWidget = QStackedWidget()
        input_layout.addRow(self.input_stack)

        # 创建ID查询界面
        id_widget: QWidget = QWidget()
        id_layout: QFormLayout = QFormLayout(id_widget)
        self.residential_id_input: QLineEdit = QLineEdit()
        id_layout.addRow("住宅区ID:", self.residential_id_input)

        self.query_id_button: QPushButton = QPushButton("查询")
        self.query_id_button.clicked.connect(self.query_by_id)
        id_layout.addRow("", self.query_id_button)  # 使用id_layout而不是name_layout

        self.input_stack.addWidget(id_widget)

        # 创建名称查询界面
        name_widget: QWidget = QWidget()
        name_layout: QFormLayout = QFormLayout(name_widget)

        # 添加行政区划输入框
        self.province_input: QLineEdit = QLineEdit()
        self.province_input.setPlaceholderText("例如：安徽省")
        name_layout.addRow("省份:", self.province_input)

        self.city_input: QLineEdit = QLineEdit()
        self.city_input.setPlaceholderText("例如：淮南市")
        name_layout.addRow("城市:", self.city_input)

        self.district_input: QLineEdit = QLineEdit()
        self.district_input.setPlaceholderText("例如：田家庵区")
        name_layout.addRow("区县:", self.district_input)

        self.name_input: QLineEdit = QLineEdit()
        name_layout.addRow("住宅区名称:", self.name_input)

        self.query_name_button: QPushButton = QPushButton("查询")
        self.query_name_button.clicked.connect(self.query_by_name)
        name_layout.addRow("", self.query_name_button)
        self.input_stack.addWidget(name_widget)

        # 创建经纬度查询界面
        coord_widget: QWidget = QWidget()
        coord_layout: QFormLayout = QFormLayout(coord_widget)
        coord_input_layout: QHBoxLayout = QHBoxLayout()
        self.longitude_input: QLineEdit = QLineEdit()
        self.longitude_input.setPlaceholderText("经度")
        coord_input_layout.addWidget(self.longitude_input)
        self.latitude_input: QLineEdit = QLineEdit()
        self.latitude_input.setPlaceholderText("纬度")
        coord_input_layout.addWidget(self.latitude_input)
        self.query_coord_button: QPushButton = QPushButton("查询")
        self.query_coord_button.clicked.connect(self.query_by_coordinates)
        coord_input_layout.addWidget(self.query_coord_button)
        coord_layout.addRow("经纬度:", coord_input_layout)
        self.input_stack.addWidget(coord_widget)

        # 创建住宅区信息显示区域
        info_group: QGroupBox = QGroupBox("住宅区详细信息")
        info_layout: QFormLayout = QFormLayout(info_group)

        self.selected_id_label: QLabel = QLabel("未选择")
        info_layout.addRow("住宅区ID:", self.selected_id_label)

        self.selected_name_label: QLabel = QLabel("未选择")
        info_layout.addRow("住宅区名称:", self.selected_name_label)

        self.selected_address_label: QLabel = QLabel("未选择")
        info_layout.addRow("住宅区地址:", self.selected_address_label)

        self.selected_coord_label: QLabel = QLabel("未选择")
        info_layout.addRow("经纬度:", self.selected_coord_label)

        layout.addWidget(info_group)

        layout.addWidget(input_group)

        # 创建参数设置区域
        param_group: QGroupBox = QGroupBox("参数设置")
        param_layout: QFormLayout = QFormLayout(param_group)

        # 搜索半径
        self.radius_spin: QSpinBox = QSpinBox()
        self.radius_spin.setRange(100, 5000)
        self.radius_spin.setValue(1200)
        self.radius_spin.setSuffix(" 米")
        param_layout.addRow("搜索半径:", self.radius_spin)

        # POI过滤
        self.filter_poi_check: QCheckBox = QCheckBox("启用POI过滤")
        self.filter_poi_check.setChecked(True)
        param_layout.addRow("", self.filter_poi_check)

        # 过滤级别
        self.filter_level_combo: QComboBox = QComboBox()
        self.filter_level_combo.addItems(["大类", "中类", "小类"])
        param_layout.addRow("过滤级别:", self.filter_level_combo)

        # 权重阈值
        self.threshold_spin: QDoubleSpinBox = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setValue(0.4)
        self.threshold_spin.setSingleStep(0.1)
        self.threshold_spin.setDecimals(1)
        param_layout.addRow("权重阈值:", self.threshold_spin)

        layout.addWidget(param_group)

        # 创建按钮区域
        button_layout: QHBoxLayout = QHBoxLayout()

        # 获取POI按钮
        self.fetch_poi_button: QPushButton = QPushButton("获取POI数据")
        self.fetch_poi_button.clicked.connect(self.fetch_poi_data)
        button_layout.addWidget(self.fetch_poi_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.poi_progress: QProgressBar = QProgressBar()
        self.poi_progress.setVisible(False)
        layout.addWidget(self.poi_progress)

        # 创建输出区域
        output_group: QGroupBox = QGroupBox("输出信息")
        output_layout: QVBoxLayout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.poi_output: QTextEdit = QTextEdit()
        self.poi_output.setReadOnly(True)
        output_layout.addWidget(self.poi_output)

        layout.addWidget(output_group)

    def create_score_tab(self) -> None:
        """创建得分计算选项卡"""
        # 创建选项卡部件
        score_tab: QWidget = QWidget()
        self.tab_widget.addTab(score_tab, "计算得分")

        # 创建主布局
        layout: QVBoxLayout = QVBoxLayout(score_tab)

        # 创建输入区域
        input_group: QGroupBox = QGroupBox("输入设置")
        input_layout: QFormLayout = QFormLayout(input_group)

        # POI文件选择
        poi_file_layout: QHBoxLayout = QHBoxLayout()
        self.poi_file_input: QLineEdit = QLineEdit()
        self.poi_file_input.setReadOnly(True)
        poi_file_layout.addWidget(self.poi_file_input)

        self.browse_poi_button: QPushButton = QPushButton("浏览...")
        self.browse_poi_button.clicked.connect(self.browse_poi_file)
        poi_file_layout.addWidget(self.browse_poi_button)

        input_layout.addRow("POI文件:", poi_file_layout)

        # 统计目录选择
        stats_dir_layout: QHBoxLayout = QHBoxLayout()
        self.stats_dir_input: QLineEdit = QLineEdit()
        self.stats_dir_input.setPlaceholderText("默认自动创建")
        stats_dir_layout.addWidget(self.stats_dir_input)

        self.browse_stats_button: QPushButton = QPushButton("浏览...")
        self.browse_stats_button.clicked.connect(self.browse_stats_dir)
        stats_dir_layout.addWidget(self.browse_stats_button)

        input_layout.addRow("统计目录:", stats_dir_layout)

        # 创建权重配置选择组
        weight_group = QGroupBox("权重配置")
        weight_layout = QHBoxLayout(weight_group)

        # 创建权重配置选择按钮
        self.weight_button = QPushButton("选择权重配置文件")
        self.weight_button.clicked.connect(self.select_weight_file)
        weight_layout.addWidget(self.weight_button)

        # 创建权重配置文件显示标签
        self.weight_label = QLabel("当前权重配置: 默认")
        weight_layout.addWidget(self.weight_label)

        # 添加权重配置组到评分布局
        layout.addWidget(weight_group)

        layout.addWidget(input_group)

        # 创建按钮区域
        button_layout: QHBoxLayout = QHBoxLayout()

        # 计算得分按钮
        self.calc_score_button: QPushButton = QPushButton("计算得分")
        self.calc_score_button.clicked.connect(self.calculate_score)
        button_layout.addWidget(self.calc_score_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.score_progress: QProgressBar = QProgressBar()
        self.score_progress.setVisible(False)
        layout.addWidget(self.score_progress)

        # 创建输出区域
        output_group: QGroupBox = QGroupBox("输出信息")
        output_layout: QVBoxLayout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.score_output: QTextEdit = QTextEdit()
        self.score_output.setReadOnly(True)
        output_layout.addWidget(self.score_output)

        layout.addWidget(output_group)

    def create_report_tab(self) -> None:
        """创建报告生成选项卡"""
        # 创建选项卡部件
        report_tab: QWidget = QWidget()
        self.tab_widget.addTab(report_tab, "生成报告")

        # 创建主布局
        layout: QVBoxLayout = QVBoxLayout(report_tab)

        # 创建输入区域
        input_group: QGroupBox = QGroupBox("输入设置")
        input_layout: QFormLayout = QFormLayout(input_group)

        # 住宅区ID输入
        self.report_residential_id_input: QLineEdit = QLineEdit()
        input_layout.addRow("住宅区ID:", self.report_residential_id_input)

        # 统计目录选择
        report_stats_dir_layout: QHBoxLayout = QHBoxLayout()
        self.report_stats_dir_input: QLineEdit = QLineEdit()
        report_stats_dir_layout.addWidget(self.report_stats_dir_input)

        self.browse_report_stats_button: QPushButton = QPushButton("浏览...")
        self.browse_report_stats_button.clicked.connect(self.browse_report_stats_dir)
        report_stats_dir_layout.addWidget(self.browse_report_stats_button)

        input_layout.addRow("统计目录:", report_stats_dir_layout)

        # 输出文件选择
        output_file_layout: QHBoxLayout = QHBoxLayout()
        self.output_file_input: QLineEdit = QLineEdit()
        self.output_file_input.setPlaceholderText("默认自动生成")
        output_file_layout.addWidget(self.output_file_input)

        self.browse_output_button: QPushButton = QPushButton("浏览...")
        self.browse_output_button.clicked.connect(self.browse_output_file)
        output_file_layout.addWidget(self.browse_output_button)

        input_layout.addRow("输出文件:", output_file_layout)

        layout.addWidget(input_group)

        # 创建选项区域
        options_group: QGroupBox = QGroupBox("选项")
        options_layout: QVBoxLayout = QVBoxLayout(options_group)

        # 生成HTML选项
        self.generate_html_check: QCheckBox = QCheckBox("生成HTML格式报告")
        self.generate_html_check.setChecked(True)
        options_layout.addWidget(self.generate_html_check)

        layout.addWidget(options_group)

        # 创建按钮区域
        button_layout: QHBoxLayout = QHBoxLayout()

        # 生成报告按钮
        self.generate_report_button: QPushButton = QPushButton("生成报告")
        self.generate_report_button.clicked.connect(self.generate_report)
        button_layout.addWidget(self.generate_report_button)

        # 打开Markdown报告按钮
        self.open_md_button: QPushButton = QPushButton("打开Markdown")
        self.open_md_button.clicked.connect(self.open_markdown_report)
        self.open_md_button.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.open_md_button)

        # 打开HTML报告按钮
        self.open_html_button: QPushButton = QPushButton("打开HTML")
        self.open_html_button.clicked.connect(self.open_html_report)
        self.open_html_button.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.open_html_button)

        # 添加弹性空间
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 创建进度条
        self.report_progress: QProgressBar = QProgressBar()
        self.report_progress.setVisible(False)
        layout.addWidget(self.report_progress)

        # 创建输出区域
        output_group: QGroupBox = QGroupBox("输出信息")
        output_layout: QVBoxLayout = QVBoxLayout(output_group)

        # 创建文本编辑器
        self.report_output: QTextEdit = QTextEdit()
        self.report_output.setReadOnly(True)
        output_layout.addWidget(self.report_output)

        layout.addWidget(output_group)

    def select_weight_file(self):
        """选择权重配置文件"""
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择权重配置文件",
            os.path.join(DATA_DIR, "poi_weights"),
            "CSV文件 (*.csv);;所有文件 (*)"
        )
        
        # 如果用户选择了文件
        if file_path:
            # 更新权重配置文件路径
            self.weight_file = file_path
            
            # 更新权重配置文件显示标签
            self.weight_label.setText(f"当前权重配置: {os.path.basename(file_path)}")
            
            # 更新状态栏
            self.status_bar.showMessage(f"已选择权重配置文件: {os.path.basename(file_path)}", 3000)

    def fetch_poi_data(self) -> None:
        """获取POI数据"""
        # 获取输入值
        residential_id: str = self.residential_id_input.text().strip()
        if not residential_id:
            QMessageBox.warning(self, "输入错误", "请先查询并选择住宅区")
            return

        name: Optional[str] = self.selected_name_label.text().strip() or None
        address: Optional[str] = self.selected_address_label.text().strip() or None

        # 获取经纬度信息
        longitude: Optional[float] = getattr(self, "selected_longitude", None)
        latitude: Optional[float] = getattr(self, "selected_latitude", None)

        radius: int = self.radius_spin.value()
        filter_poi: bool = self.filter_poi_check.isChecked()
        filter_level: str = self.filter_level_combo.currentText()
        threshold: float = self.threshold_spin.value()

        # 转换过滤级别
        if filter_level == "大类":
            filter_level: str = "category"
        elif filter_level == "中类":
            filter_level: str = "subcategory"
        elif filter_level == "小类":
            filter_level: str = "smallcategory"

        # 清空输出区域
        self.poi_output.clear()

        # 显示进度条
        self.poi_progress.setVisible(True)
        self.poi_progress.setValue(0)

        # 禁用按钮
        self.fetch_poi_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread: POIFetchWorker = POIFetchWorker(
            residential_id=residential_id,
            name=name,
            address=address,
            filter_poi=filter_poi,
            filter_level=filter_level,
            threshold=threshold,
            radius=radius,
            longitude=longitude,
            latitude=latitude,
        )

        # 连接信号
        self.worker_thread.progress_updated.connect(self.update_poi_progress)
        self.worker_thread.finished.connect(self.poi_fetch_finished)
        self.worker_thread.error_occurred.connect(self.poi_fetch_error)

        # 启动线程
        self.worker_thread.start()

    def calculate_score(self) -> None:
        """计算得分"""
        # 获取输入值
        poi_file: str = self.poi_file_input.text().strip()
        if not poi_file or not os.path.exists(poi_file):
            QMessageBox.warning(self, "输入错误", "请选择有效的POI文件")
            return

        stats_dir: Optional[str] = self.stats_dir_input.text().strip() or None

        # 清空输出区域
        self.score_output.clear()

        # 显示进度条
        self.score_progress.setVisible(True)
        self.score_progress.setValue(0)

        # 禁用按钮
        self.calc_score_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread: ScoreCalcWorker = ScoreCalcWorker(
            poi_file=poi_file, 
            stats_dir=stats_dir,
            weight_file=self.weight_file  # 添加权重配置文件参数
        )

        # 连接信号
        self.worker_thread.progress_updated.connect(self.update_score_progress)
        self.worker_thread.finished.connect(self.score_calc_finished)
        self.worker_thread.error_occurred.connect(self.score_calc_error)

        # 启动线程
        self.worker_thread.start()

    def generate_report(self) -> None:
        """生成报告"""
        # 获取输入值
        residential_id: str = self.report_residential_id_input.text().strip()
        if not residential_id:
            QMessageBox.warning(self, "输入错误", "请输入住宅区ID")
            return

        stats_dir: str = self.report_stats_dir_input.text().strip()
        if not stats_dir or not os.path.exists(stats_dir):
            QMessageBox.warning(self, "输入错误", "请选择有效的统计目录")
            return

        output_file: Optional[str] = self.output_file_input.text().strip() or None
        generate_html: bool = self.generate_html_check.isChecked()

        # 清空输出区域
        self.report_output.clear()

        # 显示进度条
        self.report_progress.setVisible(True)
        self.report_progress.setValue(0)

        # 禁用按钮
        self.generate_report_button.setEnabled(False)

        # 创建工作线程
        self.worker_thread: ReportGenerateWorker = ReportGenerateWorker(
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

    def browse_poi_file(self) -> None:
        """浏览POI文件"""
        file_path: str
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择POI文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if file_path:
            self.poi_file_input.setText(file_path)

    def browse_stats_dir(self) -> None:
        """浏览统计目录"""
        dir_path: str = QFileDialog.getExistingDirectory(self, "选择统计目录", "")
        if dir_path:
            self.stats_dir_input.setText(dir_path)

    def browse_report_stats_dir(self) -> None:
        """浏览报告统计目录"""
        dir_path: str = QFileDialog.getExistingDirectory(self, "选择统计目录", "")
        if dir_path:
            self.report_stats_dir_input.setText(dir_path)

    def browse_output_file(self) -> None:
        """浏览输出文件"""
        file_path: str
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", "", "Markdown文件 (*.md);;所有文件 (*)"
        )
        if file_path:
            self.output_file_input.setText(file_path)

    def toggle_query_method(self, method: str) -> None:
        """切换查询方式

        Args:
            method (str): 查询方式，id/name/coord
        """
        if method == "id":
            self.input_stack.setCurrentIndex(0)
        elif method == "name":
            self.input_stack.setCurrentIndex(1)
        elif method == "coord":
            self.input_stack.setCurrentIndex(2)

    def query_by_id(self) -> None:
        """根据ID查询住宅区"""
        residential_id = self.residential_id_input.text().strip()
        if not residential_id:
            QMessageBox.warning(self, "输入错误", "请输入住宅区ID")
            return

        # 显示进度提示
        self.poi_output.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 正在查询住宅区ID: {residential_id}..."
        )

        try:
            # 查询住宅区
            result = query_by_id(residential_id)

            if not result:
                self.poi_output.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 未找到ID为 {residential_id} 的住宅区"
                )
                QMessageBox.information(self, "查询结果", f"未找到ID为 {residential_id} 的住宅区")
                return

            # 选择住宅区
            self.select_residential(result)
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 已选择住宅区: {result['name']}"
            )

        except Exception as e:
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 查询失败: {str(e)}"
            )
            QMessageBox.critical(self, "查询错误", f"查询失败: {str(e)}")

    def query_by_name(self) -> None:
        """根据名称查询住宅区"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "输入错误", "请输入住宅区名称")
            return

        # 获取行政区划信息
        province = self.province_input.text().strip()
        city = self.city_input.text().strip()
        district = self.district_input.text().strip()

        # 构建完整地址
        full_address = name
        if district:
            full_address = f"{district}{full_address}"
        if city:
            full_address = f"{city}{full_address}"
        if province:
            full_address = f"{province}{full_address}"

        # 显示进度提示
        self.poi_output.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 正在查询住宅区: {full_address}..."
        )

        try:
            # 查询住宅区
            results = query_by_name(full_address)

            if not results:
                self.poi_output.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 未找到匹配的住宅区"
                )
                QMessageBox.information(self, "查询结果", "未找到匹配的住宅区")
                return

            # 如果只有一个结果，直接使用
            if len(results) == 1:
                self.select_residential(results[0])
                self.poi_output.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 已选择住宅区: {results[0]['name']}"
                )
            else:
                # 如果有多个结果，显示选择对话框
                self.show_residential_selection_dialog(results)

        except Exception as e:
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 查询失败: {str(e)}"
            )
            QMessageBox.critical(self, "查询错误", f"查询失败: {str(e)}")

    def query_by_coordinates(self) -> None:
        """根据经纬度查询住宅区"""
        longitude_text = self.longitude_input.text().strip()
        latitude_text = self.latitude_input.text().strip()

        if not longitude_text or not latitude_text:
            QMessageBox.warning(self, "输入错误", "请输入经度和纬度")
            return

        try:
            longitude = float(longitude_text)
            latitude = float(latitude_text)
        except ValueError:
            QMessageBox.warning(self, "输入错误", "经纬度格式不正确")
            return

        # 显示进度提示
        self.poi_output.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 正在查询经纬度: {longitude}, {latitude}..."
        )

        try:
            # 查询住宅区
            results = query_by_coordinates(longitude, latitude)

            if not results:
                # 如果没有找到住宅区，直接使用经纬度
                self.poi_output.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 未找到住宅区，将使用经纬度直接查询POI"
                )

                # 创建虚拟住宅区信息
                virtual_residential = {
                    "id": f"COORD_{longitude}_{latitude}",
                    "name": f"位置({longitude}, {latitude})",
                    "address": f"经度: {longitude}, 纬度: {latitude}",
                    "longitude": longitude,
                    "latitude": latitude,
                }

                self.select_residential(virtual_residential)
                return

            # 如果只有一个结果，直接使用
            if len(results) == 1:
                self.select_residential(results[0])
                self.poi_output.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 已选择住宅区: {results[0]['name']}"
                )
            else:
                # 如果有多个结果，显示选择对话框
                self.show_residential_selection_dialog(results)

        except Exception as e:
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 查询失败: {str(e)}"
            )
            QMessageBox.critical(self, "查询错误", f"查询失败: {str(e)}")

    def select_residential(self, residential: Dict[str, Any]) -> None:
        """选择住宅区并更新界面

        Args:
            residential (Dict[str, Any]): 住宅区信息
        """
        # 获取住宅区ID，如果是临时ID（以L开头），尝试从高德地图获取真实ID
        residential_id = residential.get("id", "未知")
        if residential_id.startswith("L"):
            # 尝试获取更详细的住宅区信息
            try:
                # 使用同步方式获取真实POI ID
                from query_residential import query_by_name

                name = (
                    residential.get("name", "")
                    .replace("住宅区", "")
                    .replace("小区", "")
                )
                if name:
                    # 不再打印查询信息
                    results = query_by_name(name)
                    if results and len(results) > 0:
                        # 找到最匹配的结果
                        real_id = results[0]["id"]
                        if not real_id.startswith("L"):  # 确保是真实ID
                            residential_id = real_id
                            # 更新住宅区信息
                            residential["id"] = residential_id
                            residential["name"] = results[0]["name"]
                            residential["address"] = results[0]["address"]
                            # 更新经纬度信息
                            residential["longitude"] = results[0]["longitude"]
                            residential["latitude"] = results[0]["latitude"]
                            self.selected_longitude = results[0]["longitude"]
                            self.selected_latitude = results[0]["latitude"]
                            # 不再打印获取信息
            except Exception as e:
                print(f"获取住宅区详细信息失败: {str(e)}")

        # 更新显示信息
        self.selected_id_label.setText(residential_id)
        self.selected_name_label.setText(residential.get("name", "未知"))
        self.selected_address_label.setText(residential.get("address", "未知"))

        longitude = residential.get("longitude")
        latitude = residential.get("latitude")
        if longitude is not None and latitude is not None:
            self.selected_coord_label.setText(f"{longitude}, {latitude}")
        else:
            self.selected_coord_label.setText("未知")

        # 更新输入字段
        self.residential_id_input.setText(residential_id)
        self.name_input.setText(residential.get("name", ""))

        # 如果获取到了真实的POI ID，显示提示信息
        if residential_id != residential.get("id", ""):
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 已更新为真实POI ID: {residential_id}"
            )
            # 强制刷新整个界面
            self.update()
            # 使用Qt的事件处理机制确保界面立即更新
            from PyQt5.QtWidgets import QApplication

            QApplication.processEvents()

        # 保存经纬度信息，用于后续POI查询
        self.selected_longitude = longitude
        self.selected_latitude = latitude

    def show_residential_selection_dialog(self, results: List[Dict[str, Any]]) -> None:
        """显示住宅区选择对话框

        Args:
            results (List[Dict[str, Any]]): 查询结果列表
        """
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("选择住宅区")
        dialog.setMinimumWidth(500)

        # 创建布局
        layout = QVBoxLayout(dialog)

        # 创建说明标签
        label = QLabel("找到多个住宅区，请选择一个：")
        layout.addWidget(label)

        # 创建列表
        list_widget = QListWidget()
        for result in results:
            name = result.get("name", "未知")
            address = result.get("address", "未知地址")
            item_text = f"{name} - {address}"
            list_widget.addItem(item_text)
        layout.addWidget(list_widget)

        # 创建按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # 显示对话框
        if dialog.exec_() == QDialog.Accepted and list_widget.currentRow() >= 0:
            selected = results[list_widget.currentRow()]
            self.select_residential(selected)
            self.poi_output.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 已选择住宅区: {selected['name']}"
            )

    def update_poi_progress(self, value: int, message: str) -> None:
        """更新POI获取进度"""
        self.poi_progress.setValue(value)
        self.poi_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor: QTextCursor = self.poi_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.poi_output.setTextCursor(cursor)

    def update_score_progress(self, value: int, message: str) -> None:
        """更新得分计算进度"""
        self.score_progress.setValue(value)
        self.score_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor: QTextCursor = self.score_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.score_output.setTextCursor(cursor)

    def update_report_progress(self, value: int, message: str) -> None:
        """更新报告生成进度"""
        self.report_progress.setValue(value)
        self.report_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 滚动到底部
        cursor: QTextCursor = self.report_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.report_output.setTextCursor(cursor)

    def poi_fetch_finished(self, result: Dict[str, Any]) -> None:
        """POI获取完成"""
        # 隐藏进度条
        self.poi_progress.setVisible(False)

        # 启用按钮
        self.fetch_poi_button.setEnabled(True)

        # 显示结果
        self.poi_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] 任务完成!")
        self.poi_output.append(f"POI文件: {result.get('poi_file', 'N/A')}")

        # 自动填充得分计算选项卡中的POI文件
        poi_file: Optional[str] = result.get("poi_file")
        if poi_file and os.path.exists(poi_file):
            self.poi_file_input.setText(poi_file)
        else:
            self.poi_output.append(
                "\n警告: 未生成有效的POI文件，可能是因为没有找到相关的POI数据"
            )

        # 自动填充报告生成选项卡中的住宅区ID和统计目录
        residential_id: str = self.residential_id_input.text().strip()
        if residential_id:
            self.report_residential_id_input.setText(residential_id)

            # 尝试确定统计目录
            stats_dir: str = os.path.join(
                os.path.dirname(poi_file), f"stats_poi_{residential_id}"
            )
            if os.path.exists(stats_dir):
                self.report_stats_dir_input.setText(stats_dir)

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "POI数据获取成功"))

    def poi_fetch_error(self, error_message: str) -> None:
        """POI获取错误"""
        # 隐藏进度条
        self.poi_progress.setVisible(False)

        # 启用按钮
        self.fetch_poi_button.setEnabled(True)

        # 显示错误
        self.poi_output.append(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 错误: {error_message}"
        )

        # 检查是否是住宅区信息相关的错误，并提供解决方案
        if "未找到住宅区ID" in error_message or "无法获取住宅区" in error_message:
            self.poi_output.append("\n可能的解决方案:")
            self.poi_output.append("1. 确认住宅区ID是否正确")
            self.poi_output.append("2. 尝试提供住宅区名称和地址信息")
            self.poi_output.append("3. 检查网络连接和API密钥是否有效")

        # 显示错误消息
        QMessageBox.critical(self, "错误", f"获取POI数据失败: {error_message}")

    def score_calc_finished(self, result: Dict[str, Any]) -> None:
        """得分计算完成"""
        # 隐藏进度条
        self.score_progress.setVisible(False)

        # 启用按钮
        self.calc_score_button.setEnabled(True)

        # 显示结果
        self.score_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] 任务完成!")
        self.score_output.append(f"统计目录: {result.get('stats_dir', 'N/A')}")

        # 显示汇总信息
        summary: Dict[str, Any] = result.get("summary", {})
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
        stats_dir: Optional[str] = result.get("stats_dir")
        if stats_dir and os.path.exists(stats_dir):
            self.report_stats_dir_input.setText(stats_dir)

            # 尝试从路径中提取住宅区ID
            path_parts: List[str] = stats_dir.split(os.sep)
            for part in reversed(path_parts):
                if part.startswith("stats_poi_"):
                    residential_id: str = part[10:]  # 去掉"stats_poi_"前缀
                    self.report_residential_id_input.setText(residential_id)
                    break

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "得分计算成功"))

    def score_calc_error(self, error_message: str) -> None:
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

    def report_generate_finished(self, result: Dict[str, Any]) -> None:
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
        files: Dict[str, str] = result.get("files", {})
        if files.get("markdown"):
            self.report_output.append(f"Markdown报告: {files['markdown']}")
        if files.get("html"):
            self.report_output.append(f"HTML报告: {files['html']}")

        # 保存文件路径，以便后续打开
        self.markdown_file_path = files.get("markdown", "")
        self.html_file_path = files.get("html", "")

        # 启用打开文件按钮
        if self.markdown_file_path:
            self.open_md_button.setEnabled(True)
        if self.html_file_path:
            self.open_html_button.setEnabled(True)

        # 显示成功消息
        QMessageBox.information(self, "成功", result.get("message", "报告生成成功"))

    def report_generate_error(self, error_message: str) -> None:
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

    def open_markdown_report(self) -> None:
        """打开Markdown报告文件"""
        if (
            hasattr(self, "markdown_file_path")
            and self.markdown_file_path
            and os.path.exists(self.markdown_file_path)
        ):
            import subprocess
            import platform

            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(self.markdown_file_path)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", self.markdown_file_path])
                else:  # Linux
                    subprocess.run(["xdg-open", self.markdown_file_path])
            except Exception as e:
                QMessageBox.warning(
                    self, "打开文件失败", f"无法打开Markdown报告: {str(e)}"
                )
        else:
            QMessageBox.warning(self, "文件不存在", "Markdown报告文件不存在或尚未生成")

    def open_html_report(self) -> None:
        """打开HTML报告文件"""
        if (
            hasattr(self, "html_file_path")
            and self.html_file_path
            and os.path.exists(self.html_file_path)
        ):
            import subprocess
            import platform

            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(self.html_file_path)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", self.html_file_path])
                else:  # Linux
                    subprocess.run(["xdg-open", self.html_file_path])
            except Exception as e:
                QMessageBox.warning(self, "打开文件失败", f"无法打开HTML报告: {str(e)}")
        else:
            QMessageBox.warning(self, "文件不存在", "HTML报告文件不存在或尚未生成")

    def show_about_dialog(self) -> None:
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


def main() -> None:
    """主函数"""
    app: QApplication = QApplication(sys.argv)
    app.setApplicationName("CityVeins")
    app.setApplicationVersion("1.0")

    # 设置应用程序样式
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window: CityVeinsGUI = CityVeinsGUI()

    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
