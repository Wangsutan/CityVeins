@echo off
echo ========================================
echo CityVeins Windows 环境配置脚本
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8或更高版本
    echo 您可以从 https://www.python.org/downloads/ 下载Python
    pause
    exit /b 1
)

echo 检测到Python版本:
python --version
echo.

REM 检查pip是否安装
pip --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到pip，请确保Python安装时勾选了"Add Python to PATH"选项
    pause
    exit /b 1
)

echo 检测到pip版本:
pip --version
echo.

REM 升级pip
echo 正在升级pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo 警告: pip升级失败，但将继续尝试安装依赖
)
echo.

REM 安装Python依赖
echo 正在安装Python依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)
echo.

REM 检查pandoc是否安装
pandoc --version >nul 2>&1
if errorlevel 1 (
    echo 警告: 未检测到pandoc，HTML报告生成功能可能无法正常工作
    echo 您可以从 https://pandoc.org/installing.html 下载安装pandoc
    echo.
) else (
    echo 检测到pandoc:
    pandoc --version | findstr pandoc
    echo.
)

REM 检查数据文件
echo 正在检查数据文件...

if not exist "data\key\key.txt" (
    echo 警告: 未找到API密钥文件 data\key\key.txt
    echo 请在该文件中添加您的高德地图API密钥
    echo.
)

if not exist "data\poi_weights\高德POI_加权.csv" (
    echo 警告: 未找到权重配置文件 data\poi_weights\高德POI_加权.csv
    echo.
)

if not exist "data\poi_code\高德POI分类与编码（中英文）_V1.06_20230208.csv" (
    echo 警告: 未找到POI分类编码文件 data\poi_code\高德POI分类与编码（中英文）_V1.06_20230208.csv
    echo.
)

echo ========================================
echo 环境配置完成!
echo ========================================
echo.
echo 您现在可以运行以下命令启动CityVeins:
echo python sourcesun_gui.py
echo.

REM 询问是否立即运行
set /p run_now=是否立即运行CityVeins? (y/n): 
if /i "%run_now%"=="y" (
    echo 正在启动CityVeins...
    python sourcesun_gui.py
) else (
    echo 您可以稍后手动运行CityVeins
)

pause
