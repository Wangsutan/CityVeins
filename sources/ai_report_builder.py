"""AI 报告的数据上下文构建。

为什么需要这个模块（原 /ai-report 的硬伤）：

原实现在 sources/app.py 里只有一行喂数据：
    ai_prompt = f"{prompt}" + "\\n\\n" + str(poi_df)
它把 DataFrame 的**默认字符串表示**塞进 prompt。pandas 默认会截断大表
（display.max_rows=60、display.width=80）：实测 550 行的数据，模型只能看到约
8 行、且中间列被省略。模型拿不到任何分类计数，而 prompt 却要求填「生鲜菜市场
POI数量」这类精确数字，于是通篇写成「待统计」，用政策套话填充。

而本项目的 save 流程其实**早就把统计算好了**：stats_{id}.json（大/中/小三级
分类的 POI数量/加权得分/平均权重）、score_{id}.csv、summary.json（总分/总数），
只是从未喂给模型。

本模块把这些现成统计 + POI 名称清单 + 类型码字典 + **数据覆盖范围**整理成一段
紧凑文本，供 prompt 使用。
"""

import glob
import json
import os

# 单个小类最多列多少个 POI 名称
MAX_NAME_PER_CATEGORY = 40
# 与 utils/poi/poi_filter.filter_poi_types 的 category_threshold 默认值一致
CATEGORY_WEIGHT_THRESHOLD = 0.4

_TYPE_DICT_CACHE = None
_COVERAGE_CACHE = None


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_type_dict():
    """高德类型码 → 「大类 / 中类 / 小类」（读 data/poi_code 下的官方字典）。"""
    global _TYPE_DICT_CACHE
    if _TYPE_DICT_CACHE is not None:
        return _TYPE_DICT_CACHE

    mapping = {}
    pattern = os.path.join(_project_root(), "data", "poi_code", "*.csv")
    for path in sorted(glob.glob(pattern)):
        try:
            import pandas as pd

            dic = pd.read_csv(path)
            if "NEW_TYPE" not in dic.columns:
                continue
            cols = [c for c in ("大类", "中类", "小类") if c in dic.columns]
            for _, row in dic.iterrows():
                code = str(row["NEW_TYPE"]).split(".")[0]
                parts = [str(row[c]) for c in cols
                         if str(row[c]) not in ("nan", "None", "")]
                if parts:
                    mapping[code] = " / ".join(parts)
            if mapping:
                break
        except Exception:
            continue

    _TYPE_DICT_CACHE = mapping
    return mapping


def _load_coverage():
    """返回 (纳入抓取的大类, 被排除的大类)。

    filter_poi_types 是**按大类权重**过滤的：大类权重低于阈值时，其下所有中类/小类
    都不会进入抓取队列。后果是某些业态（如餐饮服务，大类权重 0.29）从未被抓取，
    因此数据里出现 0 **不能**判定为「实际缺失」。
    """
    global _COVERAGE_CACHE
    if _COVERAGE_CACHE is not None:
        return _COVERAGE_CACHE

    kept, dropped = [], []
    try:
        import pandas as pd

        try:
            from config import WEIGHT_FILE
            path = WEIGHT_FILE
        except Exception:
            path = os.path.join(_project_root(), "data", "poi_weights", "高德POI_加权.csv")

        df = pd.read_csv(path)
        best = {}
        for _, row in df.iterrows():
            name = str(row.get("大类", "")).strip()
            if not name or name == "nan":
                continue
            try:
                w = float(row.get("权重", 0) or 0)
            except (TypeError, ValueError):
                continue
            if name not in best or w > best[name]:
                best[name] = w
        for name, w in sorted(best.items(), key=lambda kv: -kv[1]):
            (kept if w >= CATEGORY_WEIGHT_THRESHOLD else dropped).append((name, w))
    except Exception:
        pass

    _COVERAGE_CACHE = (kept, dropped)
    return _COVERAGE_CACHE


def coverage_note() -> str:
    kept, dropped = _load_coverage()
    if not kept and not dropped:
        return ""

    L = ["", "【数据覆盖范围（务必先读，直接影响结论口径）】"]
    L.append("- 本次抓取**只覆盖**以下 %d 个大类（大类权重 >= %s）：%s"
             % (len(kept), CATEGORY_WEIGHT_THRESHOLD,
                "、".join("%s（%s）" % (n, w) for n, w in kept)))
    if dropped:
        L.append("- 以下 %d 个大类**未纳入抓取**（大类权重 < %s）：%s"
                 % (len(dropped), CATEGORY_WEIGHT_THRESHOLD,
                    "、".join("%s（%s）" % (n, w) for n, w in dropped)))
    L.append("- 由此产生两条硬性约束：")
    L.append("  1) 只有落在「已覆盖大类」里的业态，才能用数量为 0 推出「服务缺口」；")
    L.append("  2) 属于「未纳入抓取大类」的业态（例如餐饮服务下的早餐店），"
             "在数据中为 0 是抓取范围所致，**不代表现实中缺失**，"
             "只能表述为「本次数据未覆盖，无法判断」，"
             "严禁写成「0 处」「供给空白」「缺口显著」等结论。")
    return "\n".join(L)


def _numeric(df, col):
    import pandas as pd

    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    return s if s.notna().any() else None


def build_report_context(save_dir: str, rid: str, df) -> str:
    """把数据聚合成模型可直接引用的统计文本。"""
    L = []
    name = str(df["住宅区名称"].iloc[0]) if ("住宅区名称" in df.columns and len(df)) else rid

    # ---------- 总体概况 ----------
    L.append("【总体概况】")
    L.append("- 住宅区：%s（ID：%s）" % (name, rid))
    L.append("- 生活圈内 POI 总数：%d 处" % len(df))
    for col, label in (("POI大类", "大类"), ("POI中类", "中类"), ("POI小类", "小类")):
        if col in df.columns:
            L.append("- 覆盖%s数量：%d 个" % (label, df[col].nunique()))

    summary_path = os.path.join(save_dir, "summary.json")
    if os.path.exists(summary_path):
        try:
            sm = json.load(open(summary_path, encoding="utf-8"))
            if sm.get("total_score") is not None:
                L.append("- 生活圈加权总分：%.2f" % float(sm["total_score"]))
        except Exception:
            pass

    dist = _numeric(df, "距离(米)")
    if dist is not None:
        L.append("- POI 距离分布：最近 %.0f 米 / 中位 %.0f 米 / 最远 %.0f 米"
                 % (dist.min(), dist.median(), dist.max()))

    weight = _numeric(df, "默认权重")
    if weight is not None:
        L.append("- 平均权重：%.2f" % weight.mean())

    # ---------- 三级分类统计（这才是"每类有多少个"的权威来源）----------
    for col, label in (("POI大类", "大类"), ("POI中类", "中类"), ("POI小类", "小类")):
        if col not in df.columns:
            continue
        L.append("")
        L.append("【%s统计（按 POI 数量降序，共 %d 类）】" % (label, df[col].nunique()))
        for cat, sub in sorted(df.groupby(col), key=lambda kv: -len(kv[1])):
            extra = []
            w = _numeric(sub, "默认权重")
            if w is not None:
                extra.append("平均权重 %.2f" % w.mean())
            d = _numeric(sub, "距离(米)")
            if d is not None:
                extra.append("最近 %.0f 米" % d.min())
            tail = "（%s）" % "，".join(extra) if extra else ""
            L.append("  %s：%d 处%s" % (cat, len(sub), tail))

    # ---------- 各小类的 POI 名称清单（判断具体业态是否存在）----------
    if "POI小类" in df.columns and "POI名称" in df.columns:
        L.append("")
        L.append("【各小类的 POI 名称清单（用于判断早餐店/便利店/托育中心等具体业态是否存在）】")
        for cat, sub in sorted(df.groupby("POI小类"), key=lambda kv: -len(kv[1])):
            names = [str(n).strip() for n in sub["POI名称"].tolist() if str(n).strip()]
            shown = names[:MAX_NAME_PER_CATEGORY]
            more = (" …（共 %d 条，此处列前 %d 条）" % (len(names), MAX_NAME_PER_CATEGORY)
                    if len(names) > MAX_NAME_PER_CATEGORY else "")
            L.append("  · %s（%d 处）：%s%s" % (cat, len(names), "、".join(shown), more))

    # ---------- 类型码对照 ----------
    if "POI类型" in df.columns:
        codes = sorted({str(c).split(".")[0] for c in df["POI类型"].dropna()})
        if codes:
            dic = _load_type_dict()
            col = df["POI类型"].astype(str).str.split(".").str[0]
            L.append("")
            L.append("【本数据涉及的高德类型码对照（类型码 → 大类 / 中类 / 小类）】")
            for c in codes:
                L.append("  %s → %s（%d 处）"
                         % (c, dic.get(c, "（官方字典中未收录）"), int((col == c).sum())))

    note = coverage_note()
    if note:
        L.append(note)

    return "\n".join(L)


def build_ai_prompt(user_prompt: str, context: str) -> str:
    return (
        "%s\n\n"
        "===== 以下是系统对该住宅区生活圈内**全部** POI 聚合得到的统计数据"
        "（非抽样，已覆盖全部记录）=====\n"
        "%s\n"
        "===== 统计数据结束 =====\n\n"
        "写作要求：\n"
        "1. 报告中的每一个数量都必须取自上面的统计数据，不得编造；\n"
        "2. 严禁使用「待统计」「待核实」这类占位表述；但**必须区分两种 0**：\n"
        "   · 属于「已覆盖大类」的业态若为 0，直接写「0 处」并据此分析缺口；\n"
        "   · 属于「未纳入抓取大类」的业态（如餐饮服务下的早餐店），"
        "只能写「本次数据未覆盖，无法判断」，不得写成「0 处」或「供给空白」；\n"
        "3. 引用数量时请一并给出小类名称，便于核对；\n"
        "4. 直接输出 Markdown 报告正文，不要复述本说明。"
        % (user_prompt, context)
    )


if __name__ == "__main__":     # 便于人工检查上下文长什么样
    import sys
    import pandas as pd

    save_dir = sys.argv[1]
    rid = os.path.basename(save_dir).split("_")[0]
    df = pd.read_csv(os.path.join(save_dir, "poi_%s_unique.csv" % rid))
    ctx = build_report_context(save_dir, rid, df)
    print("上下文长度:", len(ctx))
    print(ctx)
