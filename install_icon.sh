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
