# CityVeins GUI应用使用说明

CityVeins GUI是一个基于PyQt开发的图形用户界面应用，用于调用CityVeins后端功能，包括获取POI数据、计算得分、生成报告等。

## 安装依赖

在运行GUI应用之前，需要安装以下依赖：

```bash
pip install pyqt5 pandas
```

## 运行GUI应用

在项目根目录下执行以下命令：

```bash
python sources/run_gui.py
```

## 功能说明

### 1. 获取POI数据

在"获取POI数据"选项卡中，您可以：

- 输入住宅区ID（必需）
- 输入住宅区名称和地址（可选）
- 设置搜索半径（默认1200米）
- 配置POI过滤参数：
  - 启用/禁用POI过滤
  - 选择过滤级别（大类、中类、小类）
  - 设置权重阈值（默认0.4）

点击"获取POI数据"按钮后，系统将调用高德地图API获取指定住宅区周边的POI数据，并保存为CSV和JSON格式。

### 2. 计算得分

在"计算得分"选项卡中，您可以：

- 选择POI数据文件（CSV格式）
- 指定统计结果输出目录（可选）

点击"计算得分"按钮后，系统将根据POI数据和权重配置计算加权得分，并生成以下文件：
- 分类统计结果（CSV和JSON格式）
- 得分文件（score_xxx.csv）
- 汇总文件（summary.json）

### 3. 生成报告

在"生成报告"选项卡中，您可以：

- 输入住宅区ID
- 选择统计数据目录（包含summary.json、stats_xxx.json和score_xxx.csv文件）
- 指定输出文件路径（可选）
- 选择是否生成HTML格式报告

点击"生成报告"按钮后，系统将生成Markdown格式的评估报告，并根据需要转换为HTML格式。

## 使用流程

1. **获取POI数据**：
   - 输入住宅区ID
   - 设置搜索半径和过滤参数
   - 点击"获取POI数据"按钮
   - 等待数据处理完成

2. **计算得分**：
   - 切换到"计算得分"选项卡
   - 选择上一步生成的POI数据文件
   - 点击"计算得分"按钮
   - 等待计算完成

3. **生成报告**：
   - 切换到"生成报告"选项卡
   - 输入住宅区ID
   - 选择上一步生成的统计数据目录
   - 点击"生成报告"按钮
   - 等待报告生成完成

## 注意事项

1. 确保高德地图API密钥已正确配置在`data/key/`目录下。

2. 确保权重配置文件`data/poi_weights/高德POI_加权.csv`存在且格式正确。

3. 生成HTML报告需要安装pandoc工具：
   - Ubuntu/Debian: `sudo apt-get install pandoc`
   - CentOS/RHEL: `sudo yum install pandoc`
   - macOS: `brew install pandoc`
   - Windows: 从 [pandoc官网](https://pandoc.org/installing.html) 下载安装

4. 在执行耗时操作时，GUI应用会显示进度条，请耐心等待操作完成。

5. 如果操作失败，请查看日志输出区域中的错误信息，以便排查问题。
