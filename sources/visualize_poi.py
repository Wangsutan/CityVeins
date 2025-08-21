from __future__ import annotations
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
import os
from pathlib import Path
from typing import Dict, Tuple, List, Any, Optional, Union
from matplotlib.patches import Circle
from matplotlib.ticker import ScalarFormatter


# ---------------- 配置加载 ----------------
def load_poi_config() -> Dict[str, Any]:
    """加载 poi_marker_config.json；文件缺失或键缺失时返回安全默认值。"""
    cfg_file = Path(__file__).with_name("poi_marker_config.json")
    if not cfg_file.exists() or cfg_file.stat().st_size == 0:
        raise FileNotFoundError(
            "配置文件 poi_marker_config.json 不存在或为空，请检查！"
        )
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 确保必要键存在
    cfg.setdefault("default_colors", ["#1f77b4", "#ff7f0e", "#2ca02c"])
    cfg.setdefault("types", {})
    return cfg


POI_CONFIG = load_poi_config()

# ---------------- 字体 ----------------
plt.rcParams["font.family"] = "SimHei"
plt.rcParams["axes.unicode_minus"] = False


# ---------------- 工具函数 ----------------
def get_poi_style(poi_type: str) -> Tuple[str, str]:
    """返回 (颜色, 文字标记)。"""
    if poi_type in POI_CONFIG["types"]:
        return (
            POI_CONFIG["types"][poi_type]["color"],
            POI_CONFIG["types"][poi_type]["marker"],
        )
    # 回退
    h = hash(poi_type)
    colors = POI_CONFIG["default_colors"]
    color = colors[h % len(colors)]
    marker = poi_type
    return color, marker


# ---------------- 可视化函数（略简，与原逻辑一致） ----------------
def visualize_poi_map(
    residential_id: str, output_dir: str, radius: int = 1200, show_plots: bool = False
) -> str:
    poi_csv_path: Path = Path(output_dir).parent / f"poi_{residential_id}.csv"
    summary_json_path: Path = Path(output_dir) / "summary.json"
    poi_data: pd.DataFrame = pd.read_csv(poi_csv_path)
    with open(summary_json_path, "r", encoding="utf-8") as f:
        summary: Dict[str, Any] = json.load(f)

    residential_name: str = poi_data["住宅区名称"].iloc[0]
    residential_lon: float = poi_data["经度"].mean()
    residential_lat: float = poi_data["纬度"].mean()
    total_score: float = summary["total_score"]
    poi_count: int = summary["poi_count"]

    plt.figure(figsize=(15, 12))
    plt.scatter(
        residential_lon,
        residential_lat,
        marker="*",
        s=500,
        c="red",
        edgecolors="black",
        linewidths=1.5,
        zorder=5,
        label=f"{residential_name} (评分: {total_score:.2f}, POI总数: {poi_count})",
    )
    circle: Circle = Circle(
        (residential_lon, residential_lat),
        radius / 111000,
        fill=False,
        color="blue",
        linestyle=":",
        linewidth=2,
        label="15分钟生活圈",
    )
    plt.gca().add_patch(circle)

    for poi_type in poi_data["POI大类"].unique():
        sub: pd.DataFrame = poi_data[poi_data["POI大类"] == poi_type]
        color: str
        marker: str
        color, marker = get_poi_style(poi_type)
        for _, row in sub.iterrows():
            plt.text(
                row["经度"],
                row["纬度"],
                marker,
                color=color,
                fontsize=7,
                ha="center",
                va="center",
                zorder=3,
            )
        plt.scatter([], [], color=color, label=f"{poi_type} ({len(sub)})")

    plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1))
    plt.title(f"{residential_name} 周边 POI 分布")
    plt.xlabel("经度")
    plt.ylabel("纬度")
    plt.grid(True, linestyle="--", alpha=0.5)
    save_path: Path = Path(output_dir) / "poi_visualization.png"
    ax: plt.Axes = plt.gca()
    ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.ticklabel_format(style="plain", axis="both")  # 取消科学计数法
    ax.set_aspect("equal", adjustable="box")  # 1:1 比例
    plt.savefig(save_path, dpi=300, bbox_inches="tight")
    if show_plots:
        plt.show()
    else:
        plt.close()
    print(f"POI分布地图已保存至 {save_path}")
    return str(save_path)


def visualize_poi_statistics(
    residential_id: str, output_dir: str, show_plots: bool = False
) -> str:
    summary_json_path: Path = Path(output_dir) / "summary.json"
    stats_json_path: Path = Path(output_dir) / f"stats_{residential_id}.json"
    with open(summary_json_path, "r", encoding="utf-8") as f:
        summary: Dict[str, Any] = json.load(f)
    with open(stats_json_path, "r", encoding="utf-8") as f:
        stats: List[Dict[str, Any]] = json.load(f)

    big_stats: List[Dict[str, Any]] = [s for s in stats if s["类型"] == "大类"]
    df: pd.DataFrame = pd.DataFrame(big_stats)

    x: np.ndarray = np.arange(len(df))
    width: float = 0.35
    fig: plt.Figure
    ax1: plt.Axes
    fig, ax1 = plt.subplots(figsize=(12, 8))
    ax2: plt.Axes = ax1.twinx()
    ax1.bar(x - width / 2, df["POI数量"], width, label="POI数量", color="skyblue")
    ax2.bar(x + width / 2, df["加权得分"], width, label="加权得分", color="lightgreen")
    ax1.set_xlabel("POI大类")
    ax1.set_ylabel("数量")
    ax2.set_ylabel("得分")
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["名称"], rotation=45, ha="right")
    ax1.legend(loc="upper right")
    save_path: Path = Path(output_dir) / "poi_statistics.png"
    plt.savefig(save_path, dpi=300, bbox_inches="tight")
    if show_plots:
        plt.show()
    else:
        plt.close()
    print(f"POI统计图表已保存至 {save_path}")
    return str(save_path)


# ---------------- 主入口 ----------------
def visualize_poi(
    residential_id: str, output_dir: str, radius: int = 1200, show_plots: bool = False
) -> Tuple[str, str]:
    v: str = visualize_poi_map(residential_id, output_dir, radius, show_plots)
    s: str = visualize_poi_statistics(residential_id, output_dir, show_plots)
    print(f"可视化图表已保存至 {output_dir}")
    return v, s


if __name__ == "__main__":
    import argparse

    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="POI数据可视化工具")
    parser.add_argument("residential_id", help="住宅区ID")
    parser.add_argument(
        "output_dir", nargs="?", help="输出目录路径，如果不提供则自动生成", default=None
    )
    parser.add_argument(
        "--radius", type=int, default=1200, help="搜索半径(米)，默认为1200"
    )
    parser.add_argument("--show-plots", action="store_true", help="显示图表而不保存")

    args = parser.parse_args()

    # 如果没有提供输出目录，则自动生成
    if args.output_dir is None:
        from config import OUTPUT_DIR

        args.output_dir = os.path.join(OUTPUT_DIR, f"stats_poi_{args.residential_id}")

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    # 调用可视化函数
    visualize_poi(args.residential_id, args.output_dir, args.radius, args.show_plots)
