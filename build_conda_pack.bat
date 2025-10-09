@echo off
setlocal enabledelayedexpansion
title CityVeins conda-pack 全自动构建脚本
set "ENV_NAME=cityveins"
set "PKG_NAME=cityveins_env.tar.gz"
set "PROJECT_DIR=%~dp0"
set "ICON_NAME=cityveins.png"
set "DESKTOP_NAME=CityVeins.lnk"

:: [1] 检查 conda ...
where conda >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=1" %%i in ('where conda') do set "CONDA_EXE=%%i"
    echo [1] 发现 conda: %CONDA_EXE%
) else (
    echo [1] 未找到 conda，正在自动安装 Miniconda...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -OutFile %TEMP%\miniconda.exe}"
    %TEMP%\miniconda.exe /InstallationType=JustMe /AddToPath=1 /RegisterPython=0 /S /D=%USERPROFILE%\miniconda3
    set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
    set "PATH=%USERPROFILE%\miniconda3\Scripts;%PATH%"
)

:: [2] 安装 conda-pack
echo [2] 安装 conda-pack ...
call "%CONDA_EXE%" install -c conda-forge conda-pack -y

:: [3] 创建环境并安装依赖
echo [3] 创建环境 %ENV_NAME% ...
call "%CONDA_EXE%" remove -n %ENV_NAME% --all -y 2>nul
call "%CONDA_EXE%" create -n %ENV_NAME% -c conda-forge -y python=3.11 ^
      pyqt>=5.15 pandas>=1.3 numpy>=1.20 matplotlib>=3.3 ^
      seaborn>=0.11 openpyxl>=3.0 xlrd>=2.0 requests>=2.25 tqdm>=4.60 shapely

:: [4] 生成并安装 pip 依赖
(
echo pyqt5>=5.15.0
echo pandas>=1.3.0
echo requests>=2.25.0
echo tqdm>=4.60.0
echo numpy>=1.20.0
echo pypandoc>=1.8
echo matplotlib>=3.3.0
echo seaborn>=0.11.0
echo folium>=0.12.0
echo openpyxl>=3.0.0
echo xlrd>=2.0.0
) > "%PROJECT_DIR%requirements.txt"
echo [4] 安装 pip 依赖 ...
call "%CONDA_EXE%" run -n %ENV_NAME% python -m pip install --progress-bar=on -r "%PROJECT_DIR%requirements.txt"

:: [5] 拷贝项目源码（排除 data\key 与 output）
echo [5] 拷贝项目源码 ...
for /f "delims=" %%F in ('call "%CONDA_EXE%" run -n %ENV_NAME% python -c "import sys,os;print(os.path.join(sys.prefix,'sources'))"') do set "ENV_SOURCES=%%F"
call "%CONDA_EXE%" run -n %ENV_NAME% mkdir "%ENV_SOURCES%"
robocopy "%PROJECT_DIR%" "%ENV_SOURCES%" /E /XD .git __pycache__ .mypy_cache .ropeproject "data\key" output /XF "%PKG_NAME%" "build_conda_pack.bat"
if %errorlevel% gtr 7 exit /b 1

:: [6] 清理缓存
echo [6] 清理缓存 ...
call "%CONDA_EXE%" clean -afy

:: [7] conda-pack 打包
echo [7] conda-pack 打包 ...
if exist %PKG_NAME% del %PKG_NAME%
call "%CONDA_EXE%" run -n %ENV_NAME% conda-pack -n %ENV_NAME% -o "%PROJECT_DIR%%PKG_NAME%" --ignore-editable-packages
if %errorlevel% neq 0 (echo 错误: conda-pack 失败 & pause & exit /b 1)

:: [8] 生成启动器
echo [8] 生成启动器 run_cityveins.bat ...
>run_cityveins.bat (
echo @echo off
echo set CONDA_PREFIX=%%~dp0cityveins_env
echo call %%CONDA_PREFIX%%\Scripts\activate.bat
echo python %%CONDA_PREFIX%%\sources\sources\run_gui.py %%*
)

:: [9] 生成图标安装脚本
echo [9] 生成图标安装脚本 install_icon.bat ...
>install_icon.bat (
echo @echo off
echo :: 一键把 CityVeins 加到开始菜单/桌面（当前用户）
echo set SCRIPT_DIR=%%~dp0
echo set ICON=%%SCRIPT_DIR%%cityveins.png
echo set BAT=%%SCRIPT_DIR%%run_cityveins.bat
echo mkdir "%%APPDATA%%\Microsoft\Windows\Start Menu\Programs\CityVeins" 2^>nul
echo mshta vbscript:Execute("CreateObject(\"WScript.Shell\").CreateShortcut(\"%%APPDATA%%\Microsoft\Windows\Start Menu\Programs\CityVeins\CityVeins.lnk\").TargetPath=\"%%BAT%%\"" ^& "shortcut.IconLocation=\"%%ICON%%\"" ^& "shortcut.Save\":Close")
echo mshta vbscript:Execute("CreateObject(\"WScript.Shell\").CreateShortcut(\"%%USERPROFILE%%\Desktop\CityVeins.lnk\").TargetPath=\"%%BAT%%\"" ^& "shortcut.IconLocation=\"%%ICON%%\"" ^& "shortcut.Save\":Close")
echo echo 快捷方式已创建，可在“开始菜单”或桌面找到 CityVeins。
)

echo.
echo [10] 构建完成！
echo    绿色包 : %PKG_NAME%
echo    启动器 : run_cityveins.bat
echo    图标脚本: install_icon.bat
pause
