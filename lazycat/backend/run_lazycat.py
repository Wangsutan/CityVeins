#!/usr/bin/env python3
"""CityVeins 懒猫容器入口。

原 sources/app.py 只提供 /query /poi /score /report /ai-report /save /files 等接口，
没有 "/" 路由（前端 index.html 原本是本地打开、指向写死的远程 API），并且
__main__ 里绑定 127.0.0.1:8000。容器里需要同一个进程既提供接口、又托管前端，因此：

  1) 把项目根的 index.html 以同源方式挂在 "/"
  2) 注册高德 API Key 设置页（原项目前端完全没有填写密钥的入口）
  3) 注册「记录袋」列表页（云端已形成数据的清单 + 按条预览/下载）
  4) 绑定 0.0.0.0 与 PORT 环境变量

app.py 本身未作任何修改。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# --- 持久化自检：必须赶在 `import app` 之前 -------------------------------
# sources/app.py 在导入阶段就可能把 output/ 建出来；那一刻 /app/output 若不是
# 指向 /lzcapp/var/output 的软链，后面所有产物都落在容器可写层，重建即丢。
# persist.setup_all() 把「密钥 / 权重 / output」三条通道各自检查并尽量修好，
# 并把结论打到容器日志里 —— 再出问题也不必靠猜。
try:
    import persist                          # noqa: E402
    _PERSIST_REPORT = persist.setup_all()
except Exception as exc:                    # noqa: BLE001 兜住一切
    _PERSIST_REPORT = []
    print(f"[cityveins] 持久化自检失败（不影响启动）：{exc!r}", flush=True)

for _item in _PERSIST_REPORT:
    print(
        "[cityveins] 持久化{state}：{path} -> {target}".format(
            state="就绪" if _item.get("persistent") else "**未生效（重建即丢）**",
            path=_item.get("path"),
            target=_item.get("target"),
        ),
        flush=True,
    )

from app import app                       # noqa: E402  Flask 实例
from flask import send_from_directory     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))

for _item in _PERSIST_REPORT:
    if not _item.get("persistent"):
        app.logger.error(
            "[cityveins] %s 不在持久化目录内（%s），写入会在容器重建后丢失",
            _item.get("path"), _item.get("target"),
        )


def _register(module_name, attr, label):
    """注册一个补丁层蓝图，**失败不致命**。

    踩过的坑：records_api.py 加进来时，Dockerfile 忘了 COPY 它，
    于是这里的 `from records_api import records_bp` 直接 ImportError，
    整个进程起不来 —— 表现是「所有路由都 Connection refused」，
    比缺一个页面严重得多。所以补丁层一律各自容错：
    导入或注册失败只打日志（前端也看不到那个入口），核心功能照常。
    """
    try:
        mod = __import__(module_name, fromlist=[attr])
        app.register_blueprint(getattr(mod, attr))
        return True
    except Exception as exc:                  # noqa: BLE001 故意兜住所有异常
        app.logger.error(
            "[cityveins] 补丁层 %s(%s) 加载失败，已跳过：%r", module_name, label, exc
        )
        return False


# 高德 / DeepSeek Key 设置页：/settings 与 /api/settings/*-key
_register("settings_api", "settings_bp", "设置页")

# 权重查看/编辑页：/weights 与 /api/weights
_register("weights_api", "weights_bp", "权重页")

# 已形成的数据列表页：/records 与 /api/records*
_register("records_api", "records_bp", "记录袋")

# 把持久化的 DeepSeek Key 注入环境变量，供 /ai-report 使用
try:
    from settings_api import apply_deepseek_env   # noqa: E402
    apply_deepseek_env()
except Exception as exc:                          # noqa: BLE001
    app.logger.error("[cityveins] DeepSeek Key 注入失败：%r", exc)



@app.route("/")
def _cityveins_index():
    """托管前端页面（与接口同源，前端 API 基址为空字符串即可）。"""
    return send_from_directory(ROOT, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
