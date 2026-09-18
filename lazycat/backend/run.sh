#!/bin/sh
# 注意：这里**刻意不用 set -e**。
# 容器刚启动时 /lzcapp/var / /lzcapp/var/config 可能尚未就绪，若持久化那几步
# 失败就让脚本退出，lzcinit 会把它记成「启动失败」并长期保持不健康状态
# （即便事后由请求触发的重启已经把应用跑起来）。因此每个持久化步骤都单独容错，
# 只有最后的 exec 是必须成功的。

# 平台内部 DNS 偶发解析失败会打断高德 / DeepSeek 请求，固定为国内公共 DNS
printf 'nameserver 223.5.5.5\nnameserver 119.29.29.29\n' > /etc/resolv.conf 2>/dev/null || true

mkdir -p /lzcapp/var/config 2>/dev/null || true

# --- 高德 API Key 持久化 -------------------------------------------------
# 把 data/key/key.txt 软链到 /lzcapp/var/config/amap_key.txt：
#   · 设置页写入的密钥落在持久化目录，容器重建不丢
#   · 原 utils/file/key_loader.py 无需任何改动即可读到
# 首次运行时用镜像内自带的 key.txt 做种子（若存在），否则建成空文件。
KEY_PERSIST=/lzcapp/var/config/amap_key.txt
KEY_SEED=/app/data/key/key.txt

# 必须先把目录建出来。踩过的坑（线上实测）：
#   data/key/ 里除 .gitkeep 外没有任何被 git 跟踪的文件，lzc 的构建通道又不保留
#   空目录，所以镜像里 **根本没有 /app/data/key/** —— 那样下面的 `ln -sfn` 会因为
#   父目录不存在而失败（还被 `|| true` 吞掉），结果 key.txt 始终不存在，
#   key_loader 读不到任何密钥；表现是「重新部署之后高德 Key 就丢了」。
#   持久化文件其实一直都在，只是应用看不见它。
mkdir -p /app/data/key 2>/dev/null || true

if [ ! -f "$KEY_PERSIST" ]; then
  if [ -s "$KEY_SEED" ] && [ ! -L "$KEY_SEED" ]; then
    cp "$KEY_SEED" "$KEY_PERSIST" 2>/dev/null || true
  fi
  # 用 touch 而不是 `: >` —— 万一上面某步失败，这里也不会把已经写好的密钥抹掉
  [ -f "$KEY_PERSIST" ] || touch "$KEY_PERSIST" 2>/dev/null || true
fi
chmod 600 "$KEY_PERSIST" 2>/dev/null || true
rm -f "$KEY_SEED" 2>/dev/null || true
ln -sfn "$KEY_PERSIST" "$KEY_SEED" 2>/dev/null || true

# 启动自检：这一步失败不会拦住应用（核心功能不该因为密钥读不到就起不来），
# 但会在容器日志里留下明确的线索，不至于又变成"Key 莫名消失"。
if [ -r "$KEY_SEED" ]; then
  echo "[cityveins] 高德 Key 已就绪：$KEY_SEED -> $KEY_PERSIST ($(wc -c < "$KEY_SEED" 2>/dev/null || echo 0) 字节)"
else
  echo "[cityveins] 警告：读不到 $KEY_SEED，高德相关接口会报未配置密钥；持久化文件 $KEY_PERSIST 是否非空：$([ -s "$KEY_PERSIST" ] && echo 是 || echo 否)"
fi

# --- DeepSeek API Key 持久化（AI 报告用）---------------------------------
# 注意：lzc 的构建通道会丢弃 .env 这类隐藏文件（实测镜像内 /app/.env 不存在），
# 所以种子文件在构建时被改名为非隐藏的 env.seed。
DS_PERSIST=/lzcapp/var/config/deepseek_key.txt
if [ ! -s "$DS_PERSIST" ] && [ -s /app/env.seed ]; then
  seed=$(grep -m1 '^DEEPSEEK_API_KEY=' /app/env.seed 2>/dev/null | sed 's/^DEEPSEEK_API_KEY=//' | tr -d '\r')
  seed=$(printf '%s' "$seed" | sed 's/^"//; s/"$//')
  if [ -n "$seed" ]; then
    printf '%s' "$seed" > "$DS_PERSIST"
  fi
fi
chmod 600 "$DS_PERSIST" 2>/dev/null || true
if [ -s "$DS_PERSIST" ]; then
  DEEPSEEK_API_KEY=$(cat "$DS_PERSIST")
  export DEEPSEEK_API_KEY
fi

# --- POI 权重表持久化 -----------------------------------------------
# data/poi_weights/高德POI_加权.csv → /lzcapp/var/config/poi_weights.csv
# 权重页写入的改动因此容器重建不丢；app 侧按原路径读取，无需改动。
WEIGHT_SRC=/app/data/poi_weights/高德POI_加权.csv
WEIGHT_PERSIST=/lzcapp/var/config/poi_weights.csv
if [ ! -f "$WEIGHT_PERSIST" ] && [ -s "$WEIGHT_SRC" ] && [ ! -L "$WEIGHT_SRC" ]; then
  cp "$WEIGHT_SRC" "$WEIGHT_PERSIST" 2>/dev/null || true
fi
if [ -s "$WEIGHT_PERSIST" ]; then
  rm -f "$WEIGHT_SRC" 2>/dev/null || true
  ln -sfn "$WEIGHT_PERSIST" "$WEIGHT_SRC" 2>/dev/null || true
fi

# --- 用户数据持久化 -----------------------------------------------------
# output/ → /lzcapp/var/output（POI 数据、得分、报告都在这里）
mkdir -p /lzcapp/var/output 2>/dev/null || true
rm -rf /app/output 2>/dev/null || true
ln -sfn /lzcapp/var/output /app/output 2>/dev/null || true

exec python3 -u /app/sources/run_lazycat.py
