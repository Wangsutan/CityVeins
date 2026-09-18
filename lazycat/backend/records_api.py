"""已形成数据的列表页与接口（懒猫部署补丁）。

背景：
    /save 会把一次完整的评估落成 `output/web_save/<住宅区ID>_<YYYYmmdd_HHMMSS>/`
    目录（POI 去重表、评分表、summary/stats JSON、报告 MD/HTML，可选 AI 报告）。
    run.sh 又把 `output/` 软链到持久化目录 /lzcapp/var/output，所以这些数据
    **一直都在云上**，容器重建也不丢。

    但前端只有一个「下载到本地」按钮，而且只认本次会话的 currentSaveDir：
    一旦页面刷新、换设备或在安卓上从预览返回，`currentSaveDir` 就没了，
    云端那些已经存好的报告在界面上再也点不到，只能靠别的手段取回。

本模块补上这一环，不改动 sources/app.py：
    GET    /records                       列表页（记录袋）
    GET    /api/records                   全部记录（倒序）
    GET    /api/records/<rid>/<ts>        单条记录的文件清单
    GET    /records/<rid>/<ts>/zip        打包下载该记录
    POST   /api/records/<rid>/<ts>/delete 删除该记录（需 ?confirm=1）

为什么在 records_api 里重新实现一遍 zip：
    sources/app.py 的 /download-zip/<subpath> 把临时 zip 写进 SAVE_ROOT（数据目录）
    再删除，既会短暂污染数据目录，也不适合作为「按记录下载」的稳定入口。
    这里改成 0600 的临时文件 + 流式回传 + finally 清理，并且返回 404/403 而不是
    把异常信息塞进 HTTP 200 的 JSON 里。
"""

import datetime
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    request,
    send_file,
    send_from_directory,
)

HERE = os.path.dirname(os.path.abspath(__file__))

records_bp = Blueprint("cityveins_records", __name__)

# 记录目录名固定为 `<住宅区ID>_<YYYYmmdd_HHMMSS>`，由 /save 生成。
# 只接受这个形状，路径穿越因此不可能发生（名字里不允许 / 与 .）。
RECORD_NAME = re.compile(r"^([A-Za-z0-9]+)_(\d{8}_\d{6})$")

# 单个 zip 的上限，避免一个超大目录把内存/磁盘打满
ZIP_MAX_BYTES = 512 * 1024 * 1024

NO_FILES = {"name": "（空记录）", "mtime": "", "size_bytes": 0}


def _save_root() -> str:
    """报告目录：与 sources/app.py 的 SAVE_ROOT 保持一致。

    app.py 用 `PROJECT_ROOT/output/web_save`，容器里 PROJECT_ROOT=/app 且
    run.sh 已把 /app/output 软链到 /lzcapp/var/output，因此这里两种写法等价。
    """
    try:
        from config import OUTPUT_DIR          # /app/output
        return os.path.join(OUTPUT_DIR, "web_save")
    except Exception:
        return "/app/output/web_save"


def _parse_dir_name(dirname: str):
    """`L430722_20260918_195210` → (rid, ts, '2026-09-18 19:52:10')，不匹配则 None。"""
    m = RECORD_NAME.match(dirname)
    if not m:
        return None
    rid, ts = m.group(1), m.group(2)
    try:
        dt = datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return rid, ts, dt.strftime("%Y-%m-%d %H:%M:%S")


def _resolve_record(rid: str, ts: str) -> str:
    """把 (rid, ts) 解析成绝对目录，并强制它必须落在 SAVE_ROOT 之内。"""
    dirname = f"{rid}_{ts}"
    if not RECORD_NAME.match(dirname):
        abort(404)

    root = os.path.abspath(_save_root())
    path = os.path.abspath(os.path.join(root, dirname))

    if path != root and not path.startswith(root + os.sep):
        abort(403)
    if not os.path.isdir(path):
        abort(404)
    return path


def _read_summary(path: str):
    try:
        with open(os.path.join(path, "summary.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _name_from_report(path: str, rid: str, files):
    """报告标题形如 `# 湖南省常德市汉寿县恒大御府 15 分钟生活圈评估报告`。

    记录目录名里只有住宅区 ID（`/save` 用 `{rid}_{ts}` 建目录），中文名没有落进
    summary.json。为了列表能显示人看得懂的名字，这里从报告 MD 的首行标题里取——
    历史记录与新记录都适用，不用改 app.py 的 /save。
    """
    md = next(
        (f for f in files if f["kind"] == "report" and f["ext"] == ".md"),
        None,
    )
    if not md:
        return rid
    try:
        with open(os.path.join(path, md["name"]), "r", encoding="utf-8") as fh:
            for _ in range(20):                     # 标题总在第一行，兜底读 20 行
                line = fh.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    title = re.sub(r"\s*15\s*分钟生活圈评估报告\s*$", "", title).strip()
                    return title or rid
    except Exception:
        pass
    return rid


def _poi_fallback_exists(rid: str) -> bool:
    """output/poi/ 里是否还留着这个住宅区的原始 POI 产物。

    与 sources/app.py 的 _find_poi_csv() 的兜底顺序保持一致：记录目录里那份
    POI 副本被清理掉时，AI 报告仍能从 output/poi/ 取到数据。
    """
    poi_dir = os.path.join(os.path.dirname(os.path.abspath(_save_root())), "poi")
    for name in (f"poi_{rid}_unique.csv", f"poi_{rid}.csv"):
        if os.path.exists(os.path.join(poi_dir, name)):
            return True
    return False


def _classify(filename: str) -> str:
    """给文件分个类，前端据此显示中文名与图标用的小标记。"""
    lower = filename.lower()
    if lower.startswith("ai_report_"):
        return "ai_report"
    if lower.startswith("report_"):
        return "report"
    if lower.startswith("poi_"):
        return "poi"
    if lower.startswith("score_"):
        return "score"
    if lower == "summary.json":
        return "summary"
    if lower.startswith("stats_"):
        return "stats"
    return "other"


DISPLAY_NAMES = {
    "report": "评估报告",
    "ai_report": "AI 分析报告",
    "poi": "POI 数据",
    "score": "评分数据",
    "summary": "汇总信息",
    "stats": "统计信息",
    "other": "其他文件",
}

# AI 报告的默认提示词。
# 注意：首页 index.html 里有个一模一样的副本（更早就有，供「AI生成报告」用），
# 两边必须保持一致；记录袋从这里取，避免再抄第三份。
DEFAULT_AI_PROMPT = """作为商务局工作人员，根据上级关于推进社区一刻钟生活圈建设的工作部署，现提供某社区15分钟生活圈范围内的POI数据清单（附后）。

请基于这些数据，对以下关键业态进行专项分析：

分析维度

1. 基础生活服务

    一菜一早：生鲜菜市场、早餐店等

    便民商业：便利店、小型超市等

2. 重点民生服务

    一老一小：养老机构、托育中心、老年活动场所

    医疗保障：药店、诊所、社区卫生站

3. 生活配套服务

    一洗一修：洗衣店、洗车店、维修点、缝补店

    个人服务：理发店、美容店等

4. 文体教育服务

    教育培训：少儿培训机构、课外辅导机构

    健身休闲：健身房、体育场馆、活动中心

分析要求

    数量统计：各业态POI总数统计

    覆盖评估：分析是否满足社区居民基本需求

    质量分析：重点列举知名品牌或规模较大的POI

    缺口识别：指出存在的不足和服务盲区

    改进建议：提出具体可行的优化建议

报告格式

请用中文生成规范的Markdown格式报告，结构清晰，数据准确，建议具有可操作性。不要在正文前后加上“```markdown”“```”等额外标记。“-”列举的各项的前面要有空行，不然无法正常分段。"""


def _list_files(path: str, dirname: str):
    """返回 (文件信息列表, 目录总字节数)。按「报告 → AI 报告 → 数据」排序。"""
    order = {"report": 0, "ai_report": 1, "summary": 2, "score": 3, "stats": 4, "poi": 5, "other": 6}
    files = []
    total = 0
    try:
        names = os.listdir(path)
    except OSError:
        return [], 0

    for name in names:
        full = os.path.join(path, name)
        if not os.path.isfile(full):
            continue
        try:
            st = os.stat(full)
        except OSError:
            continue

        kind = _classify(name)
        ext = os.path.splitext(name)[1].lower()
        files.append(
            {
                "name": name,
                "kind": kind,
                "ext": ext,
                "display_name": f"{DISPLAY_NAMES[kind]}（{ext.lstrip('.').upper() or '文件'}）",
                "size_bytes": st.st_size,
                "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                # 下载走 app.py 原有路由（as_attachment=True）
                "download_url": f"/download/{dirname}/{name}",
                # 预览走 settings_api 的 inline 路由
                "preview_url": f"/preview/{dirname}/{name}",
            }
        )
        total += st.st_size

    files.sort(key=lambda f: (order.get(f["kind"], 9), f["name"]))
    return files, total


def _build_record(dirname: str):
    """把一个记录目录拼成前端要的结构；名字不合法直接返回 None。"""
    parsed = _parse_dir_name(dirname)
    if not parsed:
        return None
    rid, ts, created = parsed

    path = os.path.join(_save_root(), dirname)
    if not os.path.isdir(path):
        return None

    summary = _read_summary(path)
    files, total_bytes = _list_files(path, dirname)

    report = next((f for f in files if f["kind"] == "report" and f["ext"] == ".html"), None)
    ai_report = next((f for f in files if f["kind"] == "ai_report" and f["ext"] == ".html"), None)

    # 名字优先取 summary.json 里的 residential_name（新版 /save 会写），
    # 否则从报告标题里解析，最后退回 ID。
    name = str(summary.get("residential_name") or "").strip()
    if not name:
        name = _name_from_report(path, rid, files)

    # 「不能生成」时要说清缺什么，否则按钮灰着用户不知道为什么
    missing = []
    need = {
        "summary.json": "汇总信息 summary.json",
        f"stats_{rid}.json": "统计信息 stats_*.json",
        f"score_{rid}.csv": "评分数据 score_*.csv",
    }
    present = {f["name"] for f in files}
    for fname, label in need.items():
        if fname not in present:
            missing.append(label)

    # AI 报告要 POI 表。记录目录里没有时 /ai-report 会回退去 output/poi/ 找原始产物，
    # 所以这里也要照着判 —— 否则按钮灰着、实际却生成得出来。
    poi_in_record = f"poi_{rid}_unique.csv" in present or f"poi_{rid}.csv" in present
    has_poi = poi_in_record or _poi_fallback_exists(rid)
    if not has_poi:
        missing.append("POI 数据 poi_*_unique.csv（AI 报告需要）")

    has_all_for_report = all(f in present for f in need)

    return {
        "dir": dirname,
        "rid": rid,
        "ts": ts,
        "created": created,
        "name": name,
        "address": str(summary.get("address") or "").strip(),
        "residential_id": rid,
        "total_score": summary.get("total_score"),
        "poi_count": summary.get("poi_count"),
        "big_category_count": summary.get("big_category_count"),
        "mid_category_count": summary.get("mid_category_count"),
        "small_category_count": summary.get("small_category_count"),
        "saved_at": summary.get("timestamp"),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "has_report": report is not None,
        "has_ai_report": ai_report is not None,
        "report_preview_url": report["preview_url"] if report else None,
        "ai_report_preview_url": ai_report["preview_url"] if ai_report else None,
        "zip_url": f"/records/{rid}/{ts}/zip",
        # 生成能力的判据：数据够不够重建报告。前端据此决定按钮是
        # 「预览…」还是「生成…」，以及能不能点。
        "can_generate_report": has_all_for_report,
        "can_generate_ai_report": has_all_for_report and has_poi,
        "missing_for_generate": missing,
        # 目录建了但没写成（例如保存中途失败）：没报告、或没有 summary.json
        "incomplete": (not summary) or (report is None),
    }


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
@records_bp.route("/records")
def records_page():
    return send_from_directory(HERE, "records.html")


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@records_bp.route("/api/records")
def list_records():
    root = _save_root()
    records = []
    try:
        entries = os.listdir(root)
    except OSError:
        entries = []

    for dirname in entries:
        if not os.path.isdir(os.path.join(root, dirname)):
            continue
        rec = _build_record(dirname)
        if rec:
            # 最早 → 最新，前端再倒过来；这里直接给倒序（新记录在前）
            records.append(rec)

    records.sort(key=lambda r: (r["ts"], r["rid"]), reverse=True)
    return jsonify({"records": records, "count": len(records)})


@records_bp.route("/api/records/<rid>/<ts>")
def record_detail(rid, ts):
    path = _resolve_record(rid, ts)
    dirname = f"{rid}_{ts}"
    files, total_bytes = _list_files(path, dirname)
    rec = _build_record(dirname) or {}
    rec["files"] = files
    rec["total_bytes"] = total_bytes
    rec["file_count"] = len(files)
    return jsonify(rec)


@records_bp.route("/records/<rid>/<ts>/zip")
def record_zip(rid, ts):
    """把一条记录打成 zip 回传（临时文件，回传后清理）。"""
    path = _resolve_record(rid, ts)
    dirname = f"{rid}_{ts}"

    files, total_bytes = _list_files(path, dirname)
    if not files:
        return jsonify({"error": "该记录没有任何文件"}), 404
    if total_bytes > ZIP_MAX_BYTES:
        return jsonify({
            "error": f"记录过大（{total_bytes // 1048576} MB），超过打包上限 "
                     f"{ZIP_MAX_BYTES // 1048576} MB，请逐个下载文件"
        }), 413

    fd, tmp = tempfile.mkstemp(prefix="cityveins-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                src = os.path.join(path, f["name"])
                if os.path.isfile(src):
                    zf.write(src, f["name"])
        with open(tmp, "rb") as fh:
            payload = fh.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    return send_file(
        io.BytesIO(payload),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{dirname}.zip",
    )


@records_bp.route("/api/records/default-ai-prompt")
def get_default_ai_prompt():
    """AI 报告的默认提示词，供记录袋的生成弹窗预填。

    提示词全文只在后端存一份（DEFAULT_AI_PROMPT），首页 index.html 里那份是更早就
    有的副本；记录袋从这里取，避免同一个长文案出现第三份。
    """
    return jsonify({"prompt": DEFAULT_AI_PROMPT})


@records_bp.route("/api/records/<rid>/<ts>/generate-report", methods=["POST"])
def generate_report(rid, ts):
    """重新生成评估报告（Markdown + HTML）。

    记录袋里有些记录只留下了数据、报告文件缺失或被清理掉了，这个接口让它们能就地
    重建，不必回首页重跑一遍查询+拉 POI（那要重新消耗高德配额）。

    走的是 `/save` 里同一个 generate_markdown_report()，输入全部来自该记录目录内的
    summary.json / stats_*.json / score_*.csv，因此不联网、不用重拉 POI。
    输出文件名与 `/save` 保持一致（report_{rid}.md/.html），
    不用 app.py `/report` 那套 `{rid}_评估报告.md` —— 否则同一个目录里会同时出现
    两种命名的报告，列表是按 report_ / ai_report_ 前缀识别的，另一种会漏掉。
    """
    path = _resolve_record(rid, ts)
    dirname = f"{rid}_{ts}"

    # 派生模块在 /app/sources，容器启动时已在 sys.path 上；本地测试时手动补
    for candidate in (os.path.dirname(HERE), HERE):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    try:
        from generate_report_fixed import generate_markdown_report, markdown_to_html
    except Exception as exc:                      # noqa: BLE001
        return jsonify({"error": f"报告生成模块不可用：{exc}"}), 500

    # 先确认输入齐不齐，缺什么直接点名回报，别等里面抛 KeyError
    present = {f["name"] for f in _list_files(path, dirname)[0]}
    required = ["summary.json", f"stats_{rid}.json", f"score_{rid}.csv"]
    missing = [n for n in required if n not in present]
    if missing:
        return jsonify({
            "error": "缺少生成报告所需的数据：" + "、".join(missing),
            "missing": missing,
        }), 409

    summary = _read_summary(path)
    all_files, _ = _list_files(path, dirname)

    # 名字的解析顺序：
    #   1) summary.json 的 residential_name（生成过一次报告后会被写回，见下）
    #   2) 已有报告首行标题（删掉报告但留下数据的记录，靠这一步仍能拿到中文名）
    #   3) 退回 ID
    name = str(summary.get("residential_name") or "").strip()
    if not name:
        name = _name_from_report(path, rid, all_files)

    md_path = os.path.join(path, f"report_{rid}.md")
    html_path = os.path.join(path, f"report_{rid}.html")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(generate_markdown_report(rid, path, name))
        html_ok = bool(markdown_to_html(md_path, html_path))
    except Exception as exc:                      # noqa: BLE001
        return jsonify({"error": f"生成报告失败：{exc}"}), 500

    # 把名字回写进 summary.json：以后即便报告又被删掉，列表也还知道这是哪个小区，
    # 而且再次生成时标题不会再退化成 ID。只加一个键，不动 summary 里原有字段。
    if name and name != rid:
        try:
            new_summary = dict(summary)
            new_summary["residential_name"] = name
            tmp = md_path + ".summary.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(new_summary, f, ensure_ascii=False, indent=2)
            os.replace(tmp, os.path.join(path, "summary.json"))
        except Exception as exc:                  # noqa: BLE001
            current_app.logger.warning(
                "[records] 回写 residential_name 失败（不影响已生成的报告）：%r", exc
            )

    rec = _build_record(dirname) or {}
    return jsonify({
        "ok": True,
        "html_ok": html_ok,
        "name": name,
        "markdown_url": f"/download/{dirname}/report_{rid}.md",
        "html_url": f"/download/{dirname}/report_{rid}.html",
        "record": rec,
    })


@records_bp.route("/api/records/<rid>/<ts>/delete", methods=["POST"])
def delete_record(rid, ts):
    """删除一条记录。必须显式带 ?confirm=1，避免误删。"""
    if request.args.get("confirm") != "1":
        return jsonify({"error": "缺少确认参数 confirm=1"}), 400

    path = _resolve_record(rid, ts)
    try:
        shutil.rmtree(path)
    except Exception as exc:
        return jsonify({"error": f"删除失败：{exc}"}), 500
    return jsonify({"ok": True, "deleted": f"{rid}_{ts}"})
