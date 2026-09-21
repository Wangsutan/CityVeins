"""高德 API Key 设置页与接口（懒猫部署补丁）。

背景：原项目前端完全没有填写高德 Key 的入口（index.html 只有住宅区搜索框与
单选按钮），sources/app.py 也没有任何写入密钥的接口——密钥只由
utils/file/key_loader.py 从 config.KEY_FILE（data/key/key.txt）读取。

本模块以 Blueprint 形式补上这一环，不改动 app.py：
    GET    /settings                 设置页
    GET    /api/settings/amap-key    查询状态（只回掩码，绝不回传明文）
    POST   /api/settings/amap-key    保存密钥
    DELETE /api/settings/amap-key    清除密钥

run.sh 已把 /app/data/key/key.txt 软链到 /lzcapp/var/config/amap_key.txt，
因此这里写入的密钥会被原来的 load_key() 直接读到，且容器重建不丢。
"""

import os
import re
import stat
import tempfile

from flask import Blueprint, abort, jsonify, request, send_from_directory

try:
    from config import KEY_FILE
except Exception:                                    # pragma: no cover
    KEY_FILE = "/app/data/key/key.txt"

# 持久化保障层（persist.py）。它不在时**不放行写入** —— 见 _write_key 的注释：
# 宁可当场报「无法持久化」，也不要让用户以为存住了、重启后才发现没了。
try:
    from persist import (
        AMAP_REL,
        DEEPSEEK_REL,
        PERSIST_ROOT,
        ensure_file_link,
        is_persistent,
        status as persist_status,
    )
    PERSIST_READY = True
except Exception as _exc:                            # pragma: no cover
    PERSIST_READY = False
    AMAP_REL = DEEPSEEK_REL = "config/keys.txt"
    PERSIST_ROOT = os.environ.get("CITYVEINS_PERSIST_ROOT", "/lzcapp/var")

    def ensure_file_link(_link, _rel, seed=True):     # type: ignore[misc]
        return False, os.path.realpath(_link)

    def is_persistent(path):                          # type: ignore[misc]
        root = PERSIST_ROOT.rstrip(os.sep)
        real = os.path.realpath(path)
        return real == root or real.startswith(root + os.sep)

    def persist_status(path):                         # type: ignore[misc]
        target = os.path.realpath(path)
        return {
            "path": path, "target": target, "symlinked": os.path.islink(path),
            "persistent": is_persistent(target), "exists": os.path.exists(path),
            "writable": os.access(os.path.dirname(target) or ".", os.W_OK),
            "persist_root": PERSIST_ROOT,
        }

    print(f"[cityveins] persist.py 不可用（{_exc!r}）：密钥写入将被拒绝")

HERE = os.path.dirname(os.path.abspath(__file__))

settings_bp = Blueprint("cityveins_settings", __name__)

# DeepSeek Key（AI 报告用）持久化路径：与高德 Key 同目录
DEEPSEEK_KEY_FILE = os.environ.get(
    "CITYVEINS_DEEPSEEK_KEY_FILE",
    os.path.join(PERSIST_ROOT, *DEEPSEEK_REL.split("/")),
)
# DeepSeek Key 以 sk- 开头（长度宽松校验，不校验具体字符）
DEEPSEEK_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{10,200}$")

# 高德 Key 文件里也只允许字母数字/下划线/连字符
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

def _target_path() -> str:
    """写入目标：解析符号链接后的真实路径（并要求它真的在持久化目录里）。

    run.sh 把 /app/data/key/key.txt 软链到持久化目录 /lzcapp/var/config/amap_key.txt。
    若直接对 KEY_FILE 做 os.replace()，替换掉的会是**软链本身**而不是持久化文件——
    写进去的密钥会落在容器可写层，容器重建即丢失。所以必须写到 realpath。

    但「软链没建起来」这件事是会发生的（run.sh 那几步都是 `|| true`；
    历史上 data/key/ 目录因为不进构建上下文而在镜像里根本不存在，软链必然失败）。
    那种情况下 realpath 就是 /app/data/key/key.txt —— 可写层。所以这里每次都先
    让 persist 层确认/修复软链，修不好就不会返回一个非持久路径让上层照写。
    """
    ensure_file_link(KEY_FILE, AMAP_REL)
    return os.path.realpath(KEY_FILE)


def _read_key() -> str:
    try:
        # 读取走 KEY_FILE 即可，open() 会自动跟随软链
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _write_key(key: str) -> None:
    """原子写入，权限 0600（密钥文件不应被同容器其它进程读到）。

    写入前先确认落点在持久化目录里：落点不持久的话，密钥重启即丢，
    与其让用户过一天才发现，不如当场把错误抛回去（接口会显示「无法持久化」）。
    """
    target = _target_path()
    if not is_persistent(target):
        raise RuntimeError(
            f"密钥落点 {target} 不在持久化目录 {PERSIST_ROOT} 内，拒绝写入"
            "（否则重启应用后密钥会丢）"
        )
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".amap-key-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _key_meta(key: str) -> dict:
    """只回传「是否已配置 + 长度」，绝不回传密钥的任何字符。

    此前这里会返回首 4 位 + 末 4 位的掩码，等于把真实密钥的片段暴露在
    接口与页面上；现改为仅回长度。
    """
    return {"configured": bool(key), "length": len(key) if key else 0}


@settings_bp.route("/settings")
def settings_page():
    """设置列表页：每个设置项各占一格，点进去才是那个项目自己的页面。"""
    return send_from_directory(HERE, "settings.html")


@settings_bp.route("/settings/amap")
def amap_settings_page():
    """高德 API Key 独立设置页（原来和 DeepSeek、权重挤在同一页）。"""
    return send_from_directory(HERE, "amap.html")


@settings_bp.route("/settings/deepseek")
def deepseek_settings_page():
    """DeepSeek API Key 独立设置页。"""
    return send_from_directory(HERE, "deepseek.html")


@settings_bp.route("/settings/zip")
def zip_help_page():
    """ZIP 使用说明（各系统怎么解压）。

    原先这段说明挂在首页「打包下载 ZIP」按钮上的一个小问号气泡里，
    挤在按钮角上、又容易被忽略；现在收进设置里做成独立一项，
    要看详情点进来即可，主页面上不再出现。
    """
    return send_from_directory(HERE, "ziphelp.html")


@settings_bp.route("/api/settings/amap-key", methods=["GET"])
def get_amap_key():
    # 查状态时顺手自愈一次：软链要是丢了（历史上就丢过），密钥明明在持久化目录里
    # 也会被报成「未配置」。修好之后再读，报出来的才是真实情况。
    ensure_file_link(KEY_FILE, AMAP_REL)
    key = _read_key()
    info = persist_status(KEY_FILE)
    return jsonify({
        **_key_meta(key),
        "source": info["target"],
        "symlinked": info["symlinked"],
        # 直观暴露"文件到底在不在"：曾经因为 /app/data/key/ 目录在镜像里不存在，
        # 软链一直建不起来，持久化里明明有密钥、应用却报未配置。
        "source_exists": info["exists"],
        "readable": os.access(KEY_FILE, os.R_OK),
        # writable 之前查的是"软链所在目录"，真正要写的是 realpath 所在目录
        # （/lzcapp/var/config），两者在容器里不是一个地方，会给出误导性的 false。
        "writable": info["writable"],
        # 写入是否落在持久化目录 —— false 就意味着「重启应用后要重新填」。
        "persistent": info["persistent"],
        "persist_root": info["persist_root"],
    })


@settings_bp.route("/api/settings/amap-key", methods=["POST"])
def set_amap_key():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "密钥不能为空"}), 400
    if not KEY_PATTERN.match(key):
        return jsonify({
            "error": "密钥格式不正确：应为 16–64 位字母、数字、下划线或连字符"
        }), 400
    try:
        _write_key(key)
    except Exception as exc:
        return jsonify({"error": f"写入失败：{exc}"}), 500
    return jsonify({"ok": True, **_key_meta(key)})


@settings_bp.route("/api/settings/amap-key", methods=["DELETE"])
def clear_amap_key():
    try:
        _write_key("")
    except Exception as exc:
        return jsonify({"error": f"清除失败：{exc}"}), 500
    return jsonify({"ok": True, "configured": False})


# ---------------------------------------------------------------------------
# DeepSeek API Key（AI 报告）
# ---------------------------------------------------------------------------
def _read_deepseek() -> str:
    """优先读持久化文件，其次进程环境变量。"""
    try:
        with open(DEEPSEEK_KEY_FILE, "r", encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return value
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()


def _write_deepseek(key: str) -> None:
    # 默认落点是持久化目录里的绝对路径，但仍确认一次：只有显式用
    # CITYVEINS_DEEPSEEK_KEY_FILE 指到别处时才放过（那是调用方自己的选择）。
    if not os.environ.get("CITYVEINS_DEEPSEEK_KEY_FILE") and not is_persistent(
        DEEPSEEK_KEY_FILE
    ):
        raise RuntimeError(
            f"密钥落点 {DEEPSEEK_KEY_FILE} 不在持久化目录 {PERSIST_ROOT} 内，拒绝写入"
            "（否则重启应用后密钥会丢）"
        )
    directory = os.path.dirname(DEEPSEEK_KEY_FILE) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".ds-key-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, DEEPSEEK_KEY_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def apply_deepseek_env() -> None:
    """把持久化的 DeepSeek Key 注入进程环境变量。

    sources/app.py 是在 /ai-report 处理函数**内部**用
    os.environ.get("DEEPSEEK_API_KEY") 取值的，因此运行期改 os.environ
    即可立即生效——既不用改 app.py，也不用重启容器。
    """
    key = _read_deepseek()
    if key:
        os.environ["DEEPSEEK_API_KEY"] = key


@settings_bp.route("/api/settings/deepseek-key", methods=["GET"])
def get_deepseek_key():
    key = _read_deepseek()
    info = persist_status(DEEPSEEK_KEY_FILE)
    return jsonify({
        **_key_meta(key),
        "source": DEEPSEEK_KEY_FILE,
        "env_active": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "writable": info["writable"],
        "persistent": info["persistent"],
        "persist_root": info["persist_root"],
    })


@settings_bp.route("/api/settings/deepseek-key", methods=["POST"])
def set_deepseek_key():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "密钥不能为空"}), 400
    if not DEEPSEEK_PATTERN.match(key):
        return jsonify({"error": "密钥格式不正确：DeepSeek Key 应以 sk- 开头"}), 400
    try:
        _write_deepseek(key)
        os.environ["DEEPSEEK_API_KEY"] = key      # 立即对 /ai-report 生效
    except Exception as exc:
        return jsonify({"error": f"写入失败：{exc}"}), 500
    return jsonify({"ok": True, **_key_meta(key)})


@settings_bp.route("/api/settings/deepseek-key", methods=["DELETE"])
def clear_deepseek_key():
    try:
        _write_deepseek("")
        os.environ.pop("DEEPSEEK_API_KEY", None)
    except Exception as exc:
        return jsonify({"error": f"清除失败：{exc}"}), 500
    return jsonify({"ok": True, "configured": False})


# ---------------------------------------------------------------------------
# 报告预览（内联返回，不强制下载）
# ---------------------------------------------------------------------------
def _save_root() -> str:
    """报告目录：与 sources/app.py 的 SAVE_ROOT 保持一致（PROJECT_ROOT/output/web_save）。"""
    try:
        from config import OUTPUT_DIR          # /app/output
        return os.path.join(OUTPUT_DIR, "web_save")
    except Exception:
        return "/app/output/web_save"


@settings_bp.route("/preview/<path:subpath>/<filename>")
def preview_saved_file(subpath, filename):
    """在浏览器里直接打开报告，而不是弹下载框。

    原 sources/app.py 的 /download/<subpath>/<filename> 用 as_attachment=True 发送，
    浏览器一律当作下载处理，所以「预览报告」只会弹出下载对话框、页面打不开。
    这里以 inline 方式提供同一目录下的文件，仅用于预览；下载仍走原路由。
    """
    root = os.path.abspath(_save_root())
    dir_path = os.path.abspath(os.path.join(root, subpath))

    # 防目录穿越：解析后必须仍在 SAVE_ROOT 之内
    if dir_path != root and not dir_path.startswith(root + os.sep):
        abort(403)

    target = os.path.join(dir_path, filename)
    if not os.path.isfile(target):
        abort(404)

    # 一律以纯文本呈现，浏览器才会**直接显示**而不是弹下载框。
    #
    # 这里必须显式覆盖，不能只靠 send_from_directory 猜 mimetype：
    #   · .csv → text/csv，浏览器对它有「下载」的默认处置，preview 会变成下载
    #   · .json → application/json，Chrome 会下载，Firefox 才内联（行为不一致）
    #   · .md  → 本来就有映射到 text/markdown，同样不保证内联
    # 所以除 HTML 保持 text/html 外，其余可预览类型统一按 text/plain 发。
    # 只给基础类型，charset 交给 Flask 追加（否则会出现重复的 charset 参数）。
    lower = filename.lower()
    if lower.endswith(".html") or lower.endswith(".htm"):
        mimetype = None            # 保持 text/html，iframe 里正常渲染
    else:
        mimetype = "text/plain"
    return send_from_directory(dir_path, filename,
                               as_attachment=False, mimetype=mimetype)
