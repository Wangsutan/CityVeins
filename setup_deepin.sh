#!/bin/bash

echo "========================================"
echo "CityVeins DeepinOS 环境配置脚本"
echo "========================================"
echo

# 检查是否以root用户运行
if [ "$EUID" -eq 0 ]; then
    echo "请不要以root用户运行此脚本"
    exit 1
fi

# 检查Python3是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，正在安装..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-dev
    if [ $? -ne 0 ]; then
        echo "错误: Python3安装失败"
        exit 1
    fi
else
    echo "检测到Python3版本:"
    python3 --version
    echo
fi

# 检查pip3是否安装
if ! command -v pip3 &> /dev/null; then
    echo "错误: 未找到pip3，正在安装..."
    sudo apt install -y python3-pip
    if [ $? -ne 0 ]; then
        echo "错误: pip3安装失败"
        exit 1
    fi
else
    echo "检测到pip3版本:"
    pip3 --version
    echo
fi

# 升级pip3
echo "正在升级pip3..."
pip3 install --upgrade pip
if [ $? -ne 0 ]; then
    echo "警告: pip3升级失败，但将继续尝试安装依赖"
fi
echo

# 安装系统依赖
echo "正在安装系统依赖..."
sudo apt install -y libxcb-xinerama0 libxcb-cursor0 pandoc
if [ $? -ne 0 ]; then
    echo "警告: 系统依赖安装失败，但将继续尝试安装Python依赖"
fi
echo

# 安装Python依赖
echo "正在安装Python依赖..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "错误: Python依赖安装失败"
    exit 1
fi
echo

# 检查pandoc是否安装
if ! command -v pandoc &> /dev/null; then
    echo "警告: 未检测到pandoc，HTML报告生成功能可能无法正常工作"
    echo "您可以使用以下命令安装pandoc: sudo apt install pandoc"
    echo
else
    echo "检测到pandoc:"
    pandoc --version | head -n 1
    echo
fi

# 检查数据文件
echo "正在检查数据文件..."

if [ ! -f "data/key/key.txt" ]; then
    echo "警告: 未找到API密钥文件 data/key/key.txt"
    echo "请在该文件中添加您的高德地图API密钥"
    echo
fi

if [ ! -f "data/poi_weights/高德POI_加权.csv" ]; then
    echo "警告: 未找到权重配置文件 data/poi_weights/高德POI_加权.csv"
    echo
fi

if [ ! -f "data/poi_code/高德POI分类与编码（中英文）_V1.06_20230208.csv" ]; then
    echo "警告: 未找到POI分类编码文件 data/poi_code/高德POI分类与编码（中英文）_V1.06_20230208.csv"
    echo
fi

echo "========================================"
echo "环境配置完成!"
echo "========================================"
echo
echo "您现在可以运行以下命令启动CityVeins:"
echo "python3 sources/run_gui.py"
echo

# 询问是否立即运行
read -p "是否立即运行CityVeins? (y/n): " run_now
if [ "$run_now" = "y" ] || [ "$run_now" = "Y" ]; then
    echo "正在启动CityVeins..."
    python3 sources/run_gui.py
else
    echo "您可以稍后手动运行CityVeins"
fi
