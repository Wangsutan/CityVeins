#!/usr/bin/env python3
"""CityVeins 懒猫容器入口。

原 sources/app.py 只提供 /query /poi /score /report /ai-report /save /files 等接口，
没有 "/" 路由（前端 index.html 原本是本地打开、指向写死的远程 API），并且
__main__ 里绑定 127.0.0.1:8000。容器里需要同一个进程既提供接口、又托管前端，因此：

  1) 把项目根的 index.html 以同源方式挂在 "/"
  2) 注册高德 API Key 设置页（原项目前端完全没有填写密钥的入口）
  3) 绑定 0.0.0.0 与 PORT 环境变量

app.py 本身未作任何修改。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app import app                       # noqa: E402  Flask 实例
from weights_api import weights_bp        # noqa: E402  权重页/接口
from settings_api import (                # noqa: E402  密钥设置页/接口
    apply_deepseek_env,
    settings_bp,
)
from flask import send_from_directory     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))

# 高德 / DeepSeek Key 设置页：/settings 与 /api/settings/*-key
app.register_blueprint(settings_bp)

# 权重查看/编辑页：/weights 与 /api/weights
app.register_blueprint(weights_bp)

# 把持久化的 DeepSeek Key 注入环境变量，供 /ai-report 使用
apply_deepseek_env()



@app.route("/")
def _cityveins_index():
    """托管前端页面（与接口同源，前端 API 基址为空字符串即可）。"""
    return send_from_directory(ROOT, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
