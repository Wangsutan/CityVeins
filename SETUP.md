# CityVeins 项目配置指南

本文档提供了在Windows和DeepinOS平台上配置CityVeins项目的详细说明。

## 系统要求

- Windows 10/11 或 DeepinOS 20/23
- Python 3.8 或更高版本
- 至少 4GB RAM
- 至少 2GB 可用磁盘空间

## 通用配置步骤

### 1. 获取项目代码

从代码仓库获取项目代码：

```bash
git clone https://github.com/yourusername/CityVeins.git
cd CityVeins
```

### 2. 安装Python依赖

安装项目所需的所有Python依赖：

```bash
pip install -r requirements.txt
```

### 3. 配置数据文件

确保以下数据文件已正确配置：

1. **API密钥文件**：
   - 在 `data/key/` 目录下创建 `key.txt` 文件
   - 文件内容为高德地图API密钥

2. **权重配置文件**：
   - 确保 `data/poi_weights/高德POI_加权.csv` 文件存在
   - 此文件包含各类POI的权重配置

3. **POI分类编码文件**：
   - 确保 `data/poi_code/高德POI分类与编码（中英文）_V1.06_20230208.csv` 文件存在
   - 此文件包含高德POI分类与编码信息

## Windows平台配置

### 1. 安装Python

1. 访问 [Python官网](https://www.python.org/downloads/)
2. 下载Python 3.8或更高版本的安装程序
3. 运行安装程序，确保勾选"Add Python to PATH"选项
4. 完成安装

### 2. 验证Python安装

打开命令提示符，运行以下命令：

```cmd
python --version
pip --version
```

### 3. 安装pandoc

CityVeins需要pandoc来生成HTML报告：

1. 访问 [pandoc官网](https://pandoc.org/installing.html)
2. 下载Windows版本的pandoc安装程序
3. 运行安装程序，按照提示完成安装

### 4. 运行项目

在项目根目录下打开命令提示符，运行：

```cmd
python sources/run_gui.py
```

### 5. 创建桌面快捷方式（可选）

为了方便运行，可以创建一个桌面快捷方式：

1. 在桌面上右键，选择"新建" > "快捷方式"
2. 在位置字段中输入：`cmd /k "cd /d C:\path	o\CityVeins && python sources
un_gui.py"`（将路径替换为实际的项目路径）
3. 点击"下一步"，为快捷方式命名（如"CityVeins"）
4. 点击"完成"
5. 可选：右键点击新创建的快捷方式，选择"属性"，然后点击"更改图标"来设置一个自定义图标

## DeepinOS平台配置

### 1. 安装Python

DeepinOS通常已预装Python，但可能需要安装pip和开发工具：

```bash
sudo apt update
sudo apt install python3 python3-pip python3-dev
```

### 2. 验证Python安装

打开终端，运行以下命令：

```bash
python3 --version
pip3 --version
```

### 3. 安装系统依赖

安装CityVeins所需的系统依赖：

```bash
sudo apt install libxcb-xinerama0 libxcb-cursor0 pandoc
```

### 4. 安装Python依赖

安装项目所需的所有Python依赖：

```bash
pip3 install -r requirements.txt
```

### 5. 运行项目

在项目根目录下打开终端，运行：

```bash
python3 sources/run_gui.py
```

### 6. 创建桌面快捷方式（可选）

为了方便运行，可以创建一个桌面快捷方式：

1. 创建桌面快捷方式文件：

```bash
nano ~/Desktop/CityVeins.desktop
```

2. 在文件中添加以下内容（将路径替换为实际的项目路径）：

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=CityVeins
Comment=15分钟生活圈评估系统
Exec=python3 /path/to/CityVeins/sources/run_gui.py
Icon=/path/to/CityVeins/resources/icon.png
Path=/path/to/CityVeins
Terminal=false
Categories=Science;Education;
```

3. 保存文件（按Ctrl+O，然后按Enter，再按Ctrl+X退出）

4. 给文件添加执行权限：

```bash
chmod +x ~/Desktop/CityVeins.desktop
```

## 常见问题

### Q: 安装依赖时出现错误
A: 尝试升级pip：`pip install --upgrade pip`，然后重新安装依赖

### Q: 运行时出现"ModuleNotFoundError"错误
A: 确保所有依赖都已正确安装，可以尝试重新运行`pip install -r requirements.txt`

### Q: 在DeepinOS上无法显示界面
A: 确保已安装必要的Qt依赖：`sudo apt install libxcb-xinerama0 libxcb-cursor0`

### Q: 无法生成HTML报告
A: 确保已安装pandoc，并且pandoc在系统PATH中

### Q: API调用失败
A: 检查`data/key/key.txt`文件中的API密钥是否正确，以及网络连接是否正常

## 技术支持

如果您在配置过程中遇到问题，请检查：
1. Python版本是否符合要求
2. 所有依赖是否已正确安装
3. 数据文件是否已正确配置
4. 系统是否满足最低要求

如需更多帮助，请联系开发团队。
