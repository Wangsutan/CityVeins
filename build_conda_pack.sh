#!/usr/bin/env bash
set -e
ENV_NAME=cityveins
PKG_NAME=cityveins_env.tar.gz
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_NAME=cityveins.png
DESKTOP_NAME=CityVeins.desktop

step(){ echo -e "\n[$(date +%H:%M:%S)] $*"; }

# 1. 确保有 conda
if ! command -v conda &> /dev/null; then
    step "未找到 conda，正在安装 Miniconda..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-$(uname)-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p $HOME/miniconda3
    source $HOME/miniconda3/etc/profile.d/conda.sh
fi

# 2. 安装 conda-pack
step "安装 conda-pack"
conda install -c conda-forge conda-pack -y

# 3. 创建环境并安装依赖
step "创建 ${ENV_NAME} 环境"
conda remove -n $ENV_NAME --all -y || true
conda create -n $ENV_NAME -c conda-forge -y \
      python=3.11 pyqt>=5.15 pandas>=1.3 numpy>=1.20 matplotlib>=3.3 \
      seaborn>=0.11 openpyxl>=3.0 xlrd>=2.0 requests>=2.25 tqdm>=4.60 shapely

# 4. 生成并安装 pip 依赖
cat > "${PROJECT_DIR}/requirements.txt" <<'EOF'
pyqt5>=5.15.0
pandas>=1.3.0
requests>=2.25.0
tqdm>=4.60.0
numpy>=1.20.0
pypandoc>=1.8
matplotlib>=3.3.0
seaborn>=0.11.0
folium>=0.12.0
openpyxl>=3.0.0
xlrd>=2.0.0
EOF
step "安装 pip 依赖"
conda run -n $ENV_NAME pip install --progress-bar=on -r "${PROJECT_DIR}/requirements.txt"

# 5. 拷贝项目源码（排除 data/key 与 output）
step "拷贝项目源码到环境"
ENV_SOURCES=$(conda run -n $ENV_NAME python -c "import sys,os;print(os.path.join(sys.prefix,'sources'))")
conda run -n $ENV_NAME mkdir -p "$ENV_SOURCES"
rsync -av --progress \
      --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
      --exclude '.mypy_cache' --exclude '.ropeproject' \
      --exclude 'data/key' --exclude 'output' \
      --exclude "$PKG_NAME" --exclude 'build_conda_pack.sh' --exclude 'build_conda_pack.bat' \
      "${PROJECT_DIR}/" "$ENV_SOURCES/"

# 6. 清理 & 打包
conda clean -afy
step "conda-pack 打包"
rm -f "$PROJECT_DIR/$PKG_NAME"
conda-pack -n $ENV_NAME -o "$PROJECT_DIR/$PKG_NAME" --ignore-editable-packages

# 7. 生成启动器
step "生成启动器 run_cityveins.sh"
cat > "$PROJECT_DIR/run_cityveins.sh" <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/cityveins_env/bin/activate"
python "$DIR/cityveins_env/sources/sources/run_gui.py" "$@"
EOF
chmod +x "$PROJECT_DIR/run_cityveins.sh"

# 8. 生成 .desktop 文件
step "生成 $DESKTOP_NAME"
cat > "$PROJECT_DIR/$DESKTOP_NAME" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=CityVeins
Comment=City-wide residential POI analysis tool
Exec=${PROJECT_DIR}/run_cityveins.sh
Icon=${PROJECT_DIR}/$ICON_NAME
Terminal=false
Categories=Education;Science;
EOF
chmod +x "$PROJECT_DIR/$DESKTOP_NAME"

# 9. 生成图标安装/卸载小工具
step "生成 install_icon.sh"
cat > "$PROJECT_DIR/install_icon.sh" <<'EOF'
#!/usr/bin/env bash
set -e
ACTION=${1:-install}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_NAME=cityveins.png
DESKTOP_NAME=CityVeins.desktop
case $ACTION in
  install)
    echo "安装 CityVeins 图标（当前用户）"
    cp "$SCRIPT_DIR/$ICON_NAME"     "$HOME/.local/share/icons/"
    cp "$SCRIPT_DIR/$DESKTOP_NAME"  "$HOME/.local/share/applications/"
    update-desktop-database "$HOME/.local/share/applications/"
    echo "完成！可在“开始菜单”→ Education/Science 中找到 CityVeins。"
    ;;
  uninstall)
    echo "卸载 CityVeins 图标"
    rm -f "$HOME/.local/share/icons/$ICON_NAME"
    rm -f "$HOME/.local/share/applications/$DESKTOP_NAME"
    update-desktop-database "$HOME/.local/share/applications/"
    echo "已卸载。"
    ;;
  *) echo "用法: $0 {install|uninstall}"; exit 1 ;;
esac
EOF
chmod +x "$PROJECT_DIR/install_icon.sh"

step "全部完成！文件清单："
ls -lh "$PROJECT_DIR"/*.tar.gz "$PROJECT_DIR"/*.sh "$PROJECT_DIR"/*.desktop
