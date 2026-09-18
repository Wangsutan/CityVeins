# CityVeins — 懒猫微服发布镜像
#
# 基础镜像 = 懒猫官方运行时（Alpine 3.20 + Python 3.12）→ 盒子侧按 upstream 匹配，
# 只内嵌差异层，避免把整个基础镜像打进包里。
FROM registry.lazycat.cloud/lzc/lzcapp:3.20.3

# 构建期 DNS 固定为国内公共 DNS：平台的解析偶发失败，会让 apk/pip 取不到索引
RUN printf 'nameserver 223.5.5.5\nnameserver 119.29.29.29\n' > /etc/resolv.conf 2>/dev/null || true

# pandoc 是必需的：sources/generate_report_fixed.py 通过 subprocess 调用它做
# Markdown → HTML 转换（项目里并没有用 pypandoc 库）。
RUN apk add --no-cache python3 py3-pip pandoc

WORKDIR /app

# 依赖层单独放前面，改源码时不必重装依赖（构建缓存友好）。
# 镜像源按实测可达性排序：盒子侧 mirrors.aliyun.com=200、mirrors.ustc.edu.cn=200、
# pypi.org=200，而 pypi.tuna.tsinghua.edu.cn 返回 403（会导致 "from versions: none"）。
COPY requirements-lzc.txt /app/requirements-lzc.txt
RUN pip3 install --no-cache-dir --break-system-packages \
        -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
        -r /app/requirements-lzc.txt \
 || pip3 install --no-cache-dir --break-system-packages \
        -i https://mirrors.ustc.edu.cn/pypi/simple/ --trusted-host mirrors.ustc.edu.cn \
        -r /app/requirements-lzc.txt \
 || pip3 install --no-cache-dir --break-system-packages \
        -r /app/requirements-lzc.txt

# 项目本体（由 lzc-build.yml 的 buildscript 拷入 backend/app/）
COPY app /app

# 懒猫部署补丁层
COPY run_lazycat.py /app/sources/run_lazycat.py
COPY settings_api.py /app/sources/settings_api.py
COPY weights_api.py /app/sources/weights_api.py
COPY settings.html /app/sources/settings.html
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

ENV PORT=8000
EXPOSE 8000
CMD ["/app/run.sh"]
