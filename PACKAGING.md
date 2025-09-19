# CityVeins 打包指南

本文档提供了将CityVeins项目打包成单个可执行文件的详细说明，以便在Windows和Linux平台上运行。

## 准备工作

在开始打包之前，请确保您的系统已安装以下软件：

1. Python 3.8或更高版本
2. pip (Python包管理器)

## 打包步骤

### 1. 安装依赖

首先，安装项目所需的所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 运行打包脚本

使用我们提供的打包脚本进行打包：

```bash
python build_exe.py [选项]
```

可用选项：
- `--onedir`：创建一个目录包含可执行文件和所有依赖（默认）
- `--onefile`：创建单个可执行文件
- `--noconsole`：不显示控制台窗口（仅Windows）
- `--clean`：在构建之前清理临时文件

#### 示例命令

**Windows平台（单个文件，无控制台窗口）：**
```bash
python build_exe.py --onefile --noconsole
```

**Linux平台（单个文件）：**
```bash
python build_exe.py --onefile
```

**Windows平台（目录形式，带控制台窗口）：**
```bash
python build_exe.py --onedir
```

### 3. 获取打包结果

打包完成后，可执行文件将位于`dist`目录下：

- 如果使用`--onefile`选项：`dist/CityVeins.exe`（Windows）或`dist/CityVeins`（Linux）
- 如果使用`--onedir`选项：`dist/CityVeins/CityVeins.exe`（Windows）或`dist/CityVeins/CityVeins`（Linux）

## 平台特定说明

### Windows平台

1. **单个文件模式（--onefile）**：
   - 优点：只有一个文件，便于分发
   - 缺点：启动时间较长，因为需要解压到临时目录

2. **目录模式（--onedir）**：
   - 优点：启动速度快
   - 缺点：多个文件，分发时需要打包整个目录

3. **无控制台窗口（--noconsole）**：
   - 适用于GUI应用，不会显示黑色控制台窗口
   - 注意：如果程序有错误，将无法看到错误信息

### Linux平台

1. 在Linux上，可能需要安装一些系统依赖：
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libxcb-xinerama0 libxcb-cursor0

   # CentOS/RHEL/Fedora
   sudo yum install libxcb-xinerama0 libxcb-cursor0
   ```

2. 给可执行文件添加执行权限：
   ```bash
   chmod +x dist/CityVeins
   ```

## 分发说明

### Windows平台

1. **单个文件模式**：
   - 只需分发`CityVeins.exe`文件
   - 用户可以直接双击运行

2. **目录模式**：
   - 需要分发整个`dist/CityVeins`目录
   - 用户可以运行目录中的`CityVeins.exe`文件

### Linux平台

1. **单个文件模式**：
   - 分发`CityVeins`文件
   - 用户需要添加执行权限：`chmod +x CityVeins`
   - 然后运行：`./CityVeins`

2. **目录模式**：
   - 分发整个`dist/CityVeins`目录
   - 用户需要添加执行权限：`chmod +x CityVeins/CityVeins`
   - 然后运行：`./CityVeins/CityVeins`

## 注意事项

1. **数据文件**：
   - 打包后的可执行文件会包含`data`和`output`目录
   - 确保这些目录中包含所有必要的数据文件，特别是API密钥文件

2. **性能考虑**：
   - 单个文件模式（--onefile）的启动时间较长，但分发更简单
   - 目录模式（--onedir）启动更快，但分发时需要处理多个文件

3. **调试**：
   - 如果遇到问题，可以尝试使用`--clean`选项重新打包
   - 保留控制台窗口（不使用`--noconsole`）有助于查看错误信息

4. **依赖库**：
   - 如果系统缺少某些必要的库，可能需要手动安装
   - 特别是图形界面相关的库，如Qt的运行时库

## 常见问题

### Q: 为什么打包后的可执行文件无法运行？
A: 可能是缺少必要的系统库或数据文件。请检查：
1. 所有必要的数据文件是否已包含在打包中
2. 系统是否安装了必要的运行时库
3. 尝试使用控制台模式运行，查看错误信息

### Q: 为什么在Linux上打包后无法显示界面？
A: 可能是缺少Qt的运行时库。请尝试安装：
```bash
sudo apt-get install libxcb-xinerama0 libxcb-cursor0  # Ubuntu/Debian
sudo yum install libxcb-xinerama0 libxcb-cursor0      # CentOS/RHEL/Fedora
```

### Q: 如何减小打包后的文件大小？
A: 可以尝试以下方法：
1. 使用UPX压缩：在打包脚本中添加`--upx-dir=path_to_upx`选项
2. 排除不必要的模块：在打包脚本中添加`--exclude-module`选项
3. 清理项目中的无用文件
