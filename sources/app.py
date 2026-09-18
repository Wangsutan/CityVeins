from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import datetime
import json
import shutil
import logging
import requests
from urllib.parse import quote

# ---------- 环境 ----------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from ai_report_builder import build_ai_prompt, build_report_context
from config import OUTPUT_DIR, WEIGHT_FILE
from query_residential import query_by_id, query_by_name, query_by_coordinates
from get_single_residential_poi_fixed import main as get_poi
from generate_report_fixed import generate_markdown_report, markdown_to_html
from utils.file.weight_loader import load_weight_config
from utils.poi.poi_analysis import calculate_weighted_score

app = Flask(__name__)
CORS(app,
     resources={r"/*": {"origins": "*"}},  # 允许所有源（生产环境应收紧）
     supports_credentials=True)

# 配置日志
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)


# ---------- 工具：权重文件自动搜索 ----------
def find_weight_csv():
    custom = os.path.join(PROJECT_ROOT, "data", "poi_weights", "高德POI_加权.csv")
    if os.path.exists(custom):
        return custom
    default = os.path.join(
        PROJECT_ROOT, "data", "poi_weights", "poi_weight_default.csv"
    )
    if os.path.exists(default):
        return default
    raise FileNotFoundError(f"未找到任何权重文件，已搜索：{custom} 和 {default}")


# ---------- 查询 ----------
@app.route("/query", methods=["POST"])
def query():
    data = request.get_json() or {}
    method = data.get("method")
    try:
        if method == "id":
            result = query_by_id(data["id"])
        elif method == "name":
            result = query_by_name(data["name"])
        elif method == "coord":
            result = query_by_coordinates(data["lng"], data["lat"])
        else:
            return jsonify({"error": "无效查询方式"}), 400
        return jsonify({"result": result})
    except Exception as e:
        app.logger.error(f"查询错误: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------- POI ----------
@app.route("/poi", methods=["POST"])
def poi():
    data = request.get_json() or {}
    rid = data["residential_id"]
    radius = data.get("radius", 1200)
    filter_poi = data.get("filter_poi", True)
    threshold = data.get("threshold", 0.4)
    try:
        import get_single_residential_poi_fixed as poi_mod

        poi_mod.RADIUS = radius
        poi_mod.FILTER_LOW_WEIGHT_POI = filter_poi
        poi_mod.POI_WEIGHT_THRESHOLD = threshold
        get_poi(residential_id=rid, name=data.get("name"), address=data.get("address"))

        poi_unique = os.path.join(OUTPUT_DIR, "poi", f"poi_{rid}_unique.csv")
        poi_raw = os.path.join(OUTPUT_DIR, "poi", f"poi_{rid}.csv")
        poi_file = poi_unique if os.path.exists(poi_unique) else poi_raw
        if not os.path.exists(poi_file):
            return jsonify({"error": f"POI 文件不存在: {poi_file}"}), 404
        return jsonify({"poi_file": poi_file})
    except Exception as e:
        app.logger.error(f"POI处理错误: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------- 评分 ----------
@app.route("/score", methods=["POST"])
def score():
    data = request.get_json() or {}
    poi_file = data.get("poi_file")
    if not poi_file or not os.path.exists(poi_file):
        return jsonify({"error": f"缺少 POI 文件: {poi_file}"}), 404
    try:
        weight_csv = find_weight_csv()
        weight_map = load_weight_config(weight_csv)
        total, cnt, df = calculate_weighted_score(poi_file, weight_map)

        # 添加大、中、小类数量统计
        big_category_count = len(df[df["类型"] == "大类"])
        mid_category_count = len(df[df["类型"] == "中类"])
        small_category_count = len(df[df["类型"] == "小类"])

        return jsonify(
            {
                "total_score": total,
                "poi_count": cnt,
                "big_category_count": big_category_count,
                "mid_category_count": mid_category_count,
                "small_category_count": small_category_count,
                "categories": df.to_dict("records"),
            }
        )
    except Exception as e:
        app.logger.error(f"评分错误: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------- 报告 ----------
@app.route("/report", methods=["POST"])
def report():
    data = request.get_json() or {}
    rid = data.get("residential_id")
    stats_dir = data.get("stats_dir")
    if not rid or not stats_dir:
        return jsonify({"error": "缺少 residential_id 或 stats_dir"}), 400
    try:
        md_path = os.path.join(stats_dir, f"{rid}_评估报告.md")
        html_path = md_path.replace(".md", ".html")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(generate_markdown_report(rid, stats_dir))
        markdown_to_html(md_path, html_path)
        return jsonify({"markdown": md_path, "html": html_path})
    except Exception as e:
        app.logger.error(f"报告生成错误: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------- AI生成报告 ----------
@app.route("/ai-report", methods=["POST"])
def ai_report():
    try:
        data = request.get_json() or {}
        rid = data.get("residential_id")
        save_dir = data.get("save_dir")
        prompt = data.get("prompt", "根据POI数据生成自动报告")

        if not rid or not save_dir:
            return jsonify({"error": "缺少 residential_id 或 save_dir"}), 400

        # 读取POI文件
        poi_file = os.path.join(save_dir, f"poi_{rid}_unique.csv")
        if not os.path.exists(poi_file):
            return jsonify({"error": f"POI文件不存在: {poi_file}"}), 404

        # 读取POI数据
        import pandas as pd

        poi_df = pd.read_csv(poi_file)

        # 构建「聚合统计」上下文后再交给模型。
        # 原实现是 f"{prompt}\n\n{poi_df}" —— 把 DataFrame 的默认 repr 直接塞进
        # prompt，而 pandas 默认会截断大表（display.max_rows=60、display.width=80）：
        # 实测 550 行数据模型只能看到约 8 行、中间列还被省略，于是拿不到任何分类
        # 计数，只能把每个表格写成「待统计」。本项目的 save 流程其实早已算好
        # stats_{rid}.json（大/中/小类计数、加权得分、平均权重）与 summary.json，
        # 现在把这些现成统计 + POI 名称清单 + 类型码字典 + 数据覆盖范围一并喂给模型。
        # 详见 sources/ai_report_builder.py
        context = build_report_context(save_dir, rid, poi_df)
        ai_prompt = build_ai_prompt(prompt, context)

        # 调用DeepSeek API
        DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
        if not DEEPSEEK_API_KEY:
            return jsonify({"error": "未配置DeepSeek API密钥"}), 500

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": ai_prompt}],
            # 数据型报告不需要发挥：温度调低可显著减少编造与套话
            "temperature": 0.3,
            # 原来是 2000，报告会在结尾被硬截断（实测断在半句话上）
            "max_tokens": 8000,
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=180,
        )

        if response.status_code != 200:
            return jsonify({"error": f"AI API调用失败: {response.text}"}), 500

        result = response.json()
        ai_content = result["choices"][0]["message"]["content"]

        # 保存AI生成的报告
        ai_md_filename = f"ai_report_{rid}.md"
        ai_html_filename = f"ai_report_{rid}.html"
        ai_md_path = os.path.join(save_dir, ai_md_filename)
        ai_html_path = os.path.join(save_dir, ai_html_filename)

        with open(ai_md_path, "w", encoding="utf-8") as f:
            f.write(ai_content)

        # 转换为HTML（依赖 pandoc；失败时仍保留 Markdown，并如实告知）
        html_ok = False
        try:
            html_ok = bool(markdown_to_html(ai_md_path, ai_html_path))
        except Exception as html_err:
            app.logger.warning(f"Markdown 转 HTML 失败（pandoc 是否可用？）: {html_err}")

        return jsonify(
            {
                "success": True,
                "html_ok": html_ok,
                "context_chars": len(context),
                "prompt_chars": len(ai_prompt),
                "markdown_path": ai_md_path,
                "html_path": ai_html_path,
                "markdown_url": f"/download/{os.path.basename(save_dir)}/{ai_md_filename}",
                "html_url": f"/download/{os.path.basename(save_dir)}/{ai_html_filename}",
            }
        )

    except Exception as e:
        app.logger.error(f"AI报告生成错误: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------- 一键落盘 + 下载 ----------
SAVE_ROOT = os.path.join(PROJECT_ROOT, "output", "web_save")


@app.route("/save", methods=["POST"])
def save_all():
    try:
        # 1. 多重 JSON 解析保护
        app.logger.debug("开始处理保存请求")

        data = request.get_json()
        app.logger.debug(f"初始数据: {data}, 类型: {type(data)}")

        # 如果 data 是字符串，尝试解析多次
        parse_count = 0
        while isinstance(data, str) and parse_count < 3:
            try:
                data = json.loads(data)
                parse_count += 1
                app.logger.debug(f"第{parse_count}次解析后: {data}, 类型: {type(data)}")
            except json.JSONDecodeError:
                app.logger.warning("无法进一步解析JSON字符串")
                break

        # 2. 如果最终还不是字典，返回错误
        if not isinstance(data, dict):
            app.logger.error(f"无效的数据类型: {type(data)}, 数据: {data}")
            return jsonify(
                {"error": f"无效的请求数据格式，期望 JSON 对象，得到 {type(data)}"}
            ), 400

        # 3. 强制类型转换
        app.logger.debug("开始类型转换")
        try:
            rid = str(data["residential_id"])
            name = str(data.get("name", rid))
            radius = int(data.get("radius", 1200))
            threshold = float(data.get("threshold", 0.4))
            filter_poi = bool(data.get("filter_poi", True))

            # 处理可能的空值
            lng = None
            lat = None
            if data.get("lng") is not None:
                lng = float(data["lng"])
            if data.get("lat") is not None:
                lat = float(data["lat"])

        except (ValueError, TypeError, KeyError) as e:
            app.logger.error(f"参数解析错误: {e}, 数据: {data}")
            return jsonify({"error": f"参数类型错误: {e}"}), 400

        app.logger.debug(
            f"转换后参数: rid={rid}, name={name}, radius={radius}, threshold={threshold}"
        )

        # 4. 目录 & 时间戳
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = os.path.join(SAVE_ROOT, f"{rid}_{ts}")
        os.makedirs(save_dir, exist_ok=True)
        app.logger.debug(f"创建保存目录: {save_dir}")

        # 5. 拉 POI（去重）
        app.logger.debug("开始获取POI数据")
        import get_single_residential_poi_fixed as poi_mod

        poi_mod.RADIUS = radius
        poi_mod.POI_WEIGHT_THRESHOLD = threshold
        poi_mod.FILTER_LOW_WEIGHT_POI = filter_poi

        get_poi(residential_id=rid, name=name, address=data.get("address"))

        poi_unique = os.path.join(OUTPUT_DIR, "poi", f"poi_{rid}_unique.csv")
        poi_raw = os.path.join(OUTPUT_DIR, "poi", f"poi_{rid}.csv")
        poi_file = poi_unique if os.path.exists(poi_unique) else poi_raw

        if not os.path.exists(poi_file):
            app.logger.error(f"POI文件不存在: {poi_file}")
            return jsonify({"error": f"POI 文件不存在: {poi_file}"}), 404

        # 复制POI文件到保存目录
        shutil.copy(poi_file, os.path.join(save_dir, os.path.basename(poi_file)))
        app.logger.debug("POI文件复制完成")

        # 6. 评分（强制用去重）
        app.logger.debug("开始计算评分")
        weight_csv = find_weight_csv()
        weight_map = load_weight_config(weight_csv)
        total_score, poi_cnt, cate_df = calculate_weighted_score(poi_file, weight_map)

        # 保存score文件
        score_csv = os.path.join(save_dir, f"score_{rid}.csv")
        cate_df.to_csv(score_csv, index=False, encoding="utf-8-sig")
        app.logger.debug("评分计算完成")

        # 7. 生成各种JSON文件（报告模板需要）
        summary = {
            "residential_id": rid,
            "total_score": float(total_score),
            "poi_count": int(poi_cnt),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # 统计大、中、小类数量
        big_category_count = len(cate_df[cate_df["类型"] == "大类"])
        mid_category_count = len(cate_df[cate_df["类型"] == "中类"])
        small_category_count = len(cate_df[cate_df["类型"] == "小类"])

        # 更新summary数据
        summary.update(
            {
                "big_category_count": big_category_count,
                "mid_category_count": mid_category_count,
                "small_category_count": small_category_count,
            }
        )

        with open(os.path.join(save_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 生成与 generate_report_fixed.py 兼容的 stats 格式
        # 将大、中、小类数据合并为一个列表，每个项目包含"类型"字段
        stats_list = []

        # 添加大类数据
        big_data = cate_df[cate_df["类型"] == "大类"].to_dict("records")
        for item in big_data:
            item_with_type = item.copy()
            item_with_type["类型"] = "大类"  # 确保有类型字段
            stats_list.append(item_with_type)

        # 添加中类数据
        mid_data = cate_df[cate_df["类型"] == "中类"].to_dict("records")
        for item in mid_data:
            item_with_type = item.copy()
            item_with_type["类型"] = "中类"  # 确保有类型字段
            stats_list.append(item_with_type)

        # 添加小类数据
        small_data = cate_df[cate_df["类型"] == "小类"].to_dict("records")
        for item in small_data:
            item_with_type = item.copy()
            item_with_type["类型"] = "小类"  # 确保有类型字段
            stats_list.append(item_with_type)

        # 保存为列表格式（generate_report_fixed.py 期望的格式）
        with open(
            os.path.join(save_dir, f"stats_{rid}.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(stats_list, f, ensure_ascii=False, indent=2)

        app.logger.debug("JSON文件生成完成")

        # 8. 生成报告 - 使用英文文件名避免乱码
        app.logger.debug("开始生成报告")
        # 使用英文文件名
        md_filename = f"report_{rid}.md"
        html_filename = f"report_{rid}.html"
        md_path = os.path.join(save_dir, md_filename)
        html_path = os.path.join(save_dir, html_filename)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(generate_markdown_report(rid, save_dir, name))
        markdown_to_html(md_path, html_path)
        app.logger.debug("报告生成完成")

        return jsonify(
            {
                "save_dir": save_dir,
                "markdown_url": f"/download/{rid}_{ts}/{md_filename}?name={quote(name)}",
                "html_url": f"/download/{rid}_{ts}/{html_filename}?name={quote(name)}",
                "files": {
                    "poi": f"/download/{rid}_{ts}/poi_{rid}_unique.csv",
                    "score": f"/download/{rid}_{ts}/score_{rid}.csv",
                    "summary": f"/download/{rid}_{ts}/summary.json",
                    "stats": f"/download/{rid}_{ts}/stats_{rid}.json",
                    "report_md": f"/download/{rid}_{ts}/{md_filename}?name={quote(name)}",
                    "report_html": f"/download/{rid}_{ts}/{html_filename}?name={quote(name)}",
                },
            }
        )

    except Exception as e:
        app.logger.error(f"保存过程中出错: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/download/<path:subpath>/<filename>")
def download(subpath, filename):
    dir_path = os.path.join(SAVE_ROOT, subpath)

    # 获取自定义文件名参数
    custom_name = request.args.get("name", "")

    # 确保文件名使用UTF-8编码
    try:
        filename = filename.encode("utf-8").decode("utf-8")
    except:
        pass

    response = send_from_directory(dir_path, filename, as_attachment=True)

    # 设置下载文件的编码头
    try:
        # 如果有自定义文件名，使用自定义文件名
        if custom_name:
            # 根据文件类型设置下载文件名
            if filename.endswith(".md"):
                download_filename = f"{custom_name}_评估报告.md"
            elif filename.endswith(".html"):
                download_filename = f"{custom_name}_评估报告.html"
            elif filename.startswith("ai_report_"):
                if filename.endswith(".md"):
                    download_filename = f"{custom_name}_AI分析报告.md"
                elif filename.endswith(".html"):
                    download_filename = f"{custom_name}_AI分析报告.html"
                else:
                    download_filename = filename
            else:
                # 其他文件保持原名
                download_filename = filename
        else:
            download_filename = filename

        # 对中文文件名进行URL编码
        encoded_filename = quote(download_filename.encode("utf-8"))

        # 设置Content-Disposition头，使用RFC 5987编码
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )

    except Exception as e:
        app.logger.warning(f"设置文件名编码失败: {e}")
        # 如果编码失败，使用原始文件名
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@app.route("/files/<path:subpath>")
def list_files(subpath):
    """获取文件列表的API"""
    dir_path = os.path.join(SAVE_ROOT, subpath)

    if not os.path.exists(dir_path):
        return jsonify({"error": "目录不存在"}), 404

    files = []
    for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)
        if os.path.isfile(file_path):
            stat = os.stat(file_path)

            # 根据文件名生成显示名称
            display_name = filename
            if filename.startswith("report_") and filename.endswith(".md"):
                display_name = "评估报告 (Markdown)"
            elif filename.startswith("report_") and filename.endswith(".html"):
                display_name = "评估报告 (HTML)"
            elif filename.startswith("ai_report_") and filename.endswith(".md"):
                display_name = "AI分析报告 (Markdown)"
            elif filename.startswith("ai_report_") and filename.endswith(".html"):
                display_name = "AI分析报告 (HTML)"
            elif filename.startswith("poi_") and filename.endswith(".csv"):
                display_name = "POI数据"
            elif filename.startswith("score_") and filename.endswith(".csv"):
                display_name = "评分数据"
            elif filename == "summary.json":
                display_name = "汇总信息"
            elif filename.startswith("stats_") and filename.endswith(".json"):
                display_name = "统计信息"

            files.append(
                {
                    "name": filename,
                    "display_name": display_name,
                    "size": stat.st_size,
                    "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "url": f"/download/{subpath}/{quote(filename)}",
                }
            )

    return jsonify({"files": files})


@app.route("/download-zip/<path:subpath>")
def download_zip(subpath):
    """打包下载整个目录"""
    import zipfile

    dir_path = os.path.join(SAVE_ROOT, subpath)

    if not os.path.exists(dir_path):
        return jsonify({"error": "目录不存在"}), 404

    # 创建ZIP文件
    zip_filename = f"{subpath}.zip"
    zip_path = os.path.join(SAVE_ROOT, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 在ZIP文件中保持相对路径
                    arcname = os.path.relpath(file_path, dir_path)
                    zipf.write(file_path, arcname)

        # 发送ZIP文件
        response = send_from_directory(SAVE_ROOT, zip_filename, as_attachment=True)

        # 设置下载文件名
        encoded_filename = quote(f"{subpath}.zip".encode("utf-8"))
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )

        return response

    except Exception as e:
        app.logger.error(f"创建ZIP文件失败: {e}")
        return jsonify({"error": f"创建ZIP文件失败: {str(e)}"}), 500
    finally:
        # 清理临时ZIP文件
        if os.path.exists(zip_path):
            os.remove(zip_path)


@app.after_request
def after_request(response):
    """确保所有响应都使用UTF-8编码"""
    if response.content_type.startswith("application/json"):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)
