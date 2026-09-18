"""权重查看/编辑页与接口（/weights 与 /api/weights）。

页面已从「统一设置页」拆出来：/settings 现在只是设置项列表，权重有自己的独立页面。

要点（两列权重的区别，决定了本页面的设计）：

1) `权重`（基础权重）
   - 参与评分（score / save 时的加权计算）
   - **同时决定抓取范围**：utils/poi/poi_filter.filter_poi_types 按**大类权重 ≥ 阈值(0.4)**
     决定该大类下的所有中类/小类是否进入抓取队列。改它 = 改抓哪些 POI。
2) `客制化权重`
   - utils/file/weight_loader.load_weight_config 优先读这一列，为空才回落到 `权重`
   - **只影响评分，不影响抓取范围**

原 CSV 没有 `客制化权重` 列（虽然加载器支持），本模块读取时会自动补上，并把它作为
默认的编辑入口 —— 改评分不会意外改变抓取范围。基础权重也允许编辑，但会在前端
对大类行明确标注「会影响抓取范围」。

持久化：run.sh 把 /app/data/poi_weights/高德POI_加权.csv 软链到
/lzcapp/var/config/poi_weights.csv，因此这里写入的改动容器重建后仍在。
"""

import os
import tempfile

from flask import Blueprint, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))

weights_bp = Blueprint("cityveins_weights", __name__)


@weights_bp.route("/weights")
def weights_page():
    """权重页（原先嵌在 /settings 里，现已独立）。"""
    return send_from_directory(HERE, "weights.html")


# 与 utils/poi/poi_filter.filter_poi_types 的默认值保持一致
CATEGORY_THRESHOLD = 0.4
CUSTOM_COL = "客制化权重"
BASE_COL = "权重"


def _weight_path():
    try:
        from config import WEIGHT_FILE
        return WEIGHT_FILE
    except Exception:
        return "/app/data/poi_weights/高德POI_加权.csv"


def _load_df():
    import pandas as pd

    path = _weight_path()
    if not os.path.exists(path):
        return None, path, "权重文件不存在"
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        return None, path, f"读取失败：{exc}"
    if CUSTOM_COL not in df.columns:
        df[CUSTOM_COL] = ""
    return df, path, None


def _atomic_write(df) -> None:
    """原子写入；注意必须写 realpath，否则会把软链替换成普通文件（持久化失效）。"""
    import pandas as pd

    target = os.path.realpath(_weight_path())
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".weights-", suffix=".csv")
    os.close(fd)
    try:
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _to_float(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return "INVALID"


def _fmt_weight(v) -> str:
    """把权重格式化成 CSV 里的字符串形式。

    本模块用 dtype=str 读取，而 pandas 3.x 对 .at 赋值做了严格类型校验：
    往 str 列写 float 会直接抛
    TypeError: Invalid value ... for dtype 'str'。
    因此写入前统一转成字符串（并用 %g 去掉多余小数位：0.66 / 0 / 0.95）。
    """
    if v is None:
        return ""
    return "%g" % float(v)


def _bigcat_rows(df):
    """按大类聚合：基础权重（取该大类自身那一行的权重）、是否纳入抓取、条目数。"""
    import pandas as pd

    wanted = ["NEW_TYPE", "大类", "中类", "小类", BASE_COL]
    cols = [c for c in wanted if c in df.columns]
    sub = df[cols].copy()
    sub["_d"] = sub[BASE_COL].map(lambda v: _to_float(v))
    sub["_d"] = pd.to_numeric(sub["_d"], errors="coerce")

    out = []
    for big, grp in sub.groupby("大类"):
        # 大类自身的行：中类与小类名称都与大类同名（数据里就是这么组织的）
        own = grp[grp["中类"] == big] if "中类" in grp.columns else grp.iloc[0:0]
        base = None
        if len(own) and own["_d"].notna().any():
            base = float(own["_d"].max())
        if base is None and grp["_d"].notna().any():
            base = float(grp["_d"].max())
        out.append({
            "big": str(big),
            "base": base,
            "in_scope": (base is not None and base >= CATEGORY_THRESHOLD),
            "rows": int(len(grp)),
        })
    out.sort(key=lambda r: (-(r["base"] if r["base"] is not None else -99), r["big"]))
    return out


@weights_bp.route("/api/weights", methods=["GET"])
def get_weights():
    df, path, err = _load_df()
    if err:
        return jsonify({"error": err}), 500

    rows = []
    custom_count = 0
    for _, r in df.iterrows():
        base = _to_float(r.get(BASE_COL))
        custom = _to_float(r.get(CUSTOM_COL))
        if isinstance(base, str):
            base = None
        if isinstance(custom, str):
            custom = None
        if custom is not None:
            custom_count += 1
        rows.append({
            "code": str(r.get("NEW_TYPE", "")).strip(),
            "big": str(r.get("大类", "")).strip(),
            "mid": str(r.get("中类", "")).strip(),
            "small": str(r.get("小类", "")).strip(),
            "base": base,
            "custom": custom,
            "effective": custom if custom is not None else base,
            "rule": str(r.get("评价规则", "")).strip(),
        })

    return jsonify({
        "rows": rows,
        "stats": {
            "total": len(rows),
            "customized": custom_count,
            "bigcats": len({r["big"] for r in rows}),
        },
        "bigcats": _bigcat_rows(df),
        "threshold": CATEGORY_THRESHOLD,
        "path": os.path.realpath(path),
        "is_symlink": os.path.islink(path),
    })


@weights_bp.route("/api/weights", methods=["POST"])
def update_weights():
    payload = request.get_json(silent=True) or {}
    updates = payload.get("updates") or []
    if not isinstance(updates, list) or not updates:
        return jsonify({"error": "没有需要保存的改动"}), 400

    df, path, err = _load_df()
    if err:
        return jsonify({"error": err}), 500

    index = {str(r.get("NEW_TYPE", "")).strip(): i for i, r in df.iterrows()}

    applied, rejected = 0, []
    for item in updates:
        code = str(item.get("code", "")).strip()
        if code not in index:
            rejected.append({"code": code, "reason": "类型码不存在"})
            continue

        i = index[code]
        if "custom" in item:
            val = item.get("custom")
            f = _to_float(val)
            if f == "INVALID":
                rejected.append({"code": code, "reason": "客制化权重不是数字"})
                continue
            if f is not None and not (-2.0 <= f <= 2.0):
                rejected.append({"code": code, "reason": "客制化权重超出 -2 ~ 2 范围"})
                continue
            df.at[i, CUSTOM_COL] = _fmt_weight(f)   # pandas 3.x 要求 str 列写 str
            applied += 1

        if "base" in item:
            val = item.get("base")
            f = _to_float(val)
            if f == "INVALID" or f is None:
                rejected.append({"code": code, "reason": "基础权重必须为数字"})
                continue
            if not (-2.0 <= f <= 2.0):
                rejected.append({"code": code, "reason": "基础权重超出 -2 ~ 2 范围"})
                continue
            df.at[i, BASE_COL] = _fmt_weight(f)     # 同上
            applied += 1

    if applied == 0:
        return jsonify({"error": "没有有效改动", "rejected": rejected}), 400

    try:
        _atomic_write(df)
    except Exception as exc:
        return jsonify({"error": f"写入失败：{exc}"}), 500

    return jsonify({"ok": True, "applied": applied, "rejected": rejected,
                    "path": os.path.realpath(path)})


@weights_bp.route("/api/weights/reset", methods=["POST"])
def reset_weights():
    """清空所有「客制化权重」，恢复为基础权重（不动基础权重本身）。"""
    df, path, err = _load_df()
    if err:
        return jsonify({"error": err}), 500
    df[CUSTOM_COL] = ""
    try:
        _atomic_write(df)
    except Exception as exc:
        return jsonify({"error": f"写入失败：{exc}"}), 500
    return jsonify({"ok": True, "cleared": int(len(df))})
