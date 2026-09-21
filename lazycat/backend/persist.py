"""持久化保障层（懒猫微服部署补丁）。

为什么需要这一层
================
懒猫容器里只有 `/lzcapp/var` 是持久的（在盒子上落在
`/lzcsys/data/appvar/<pkgid>/`，容器重建后原样还在，`/proc/mounts` 里是一个
btrfs 子卷）；容器内的其它路径都在「可写层」，容器一重建就回滚成镜像里的样子。

城脉有三样东西必须落在 `/lzcapp/var`：

    /app/data/key/key.txt                    → config/amap_key.txt
    /app/data/poi_weights/高德POI_加权.csv    → config/poi_weights.csv
    /app/output/                             → output/

`run.sh` 启动时会把它们软链过去。但那几步全是 `|| true` 的容错写法（容器刚起来时
`/lzcapp/var` 未必就绪，不能让脚本因此退出），于是「软链没建起来」这种故障会
**静默**发生 —— 接口层随后把该写进持久化目录的东西写进了可写层：

  · 用户填的高德 Key 当场可用，**重启应用后就没了**，得重新填；
  · 权重改动、评估记录同理，重启即回滚。

这正是商店审核反馈的「API 未持久化，一重启就丢失」：密钥文件本身没丢，
是**写入落点**不在持久化目录里。历史上 `data/key/` 目录因为没进构建上下文
（lzc 的构建通道会丢掉空目录与点文件）而在镜像里根本不存在，`ln` 因此失败，
于是每次保存都写进可写层 —— 症状与这条反馈完全一致。

本层做的事
==========
1. `ensure_*`：写入前先确认软链存在且指向持久化目录，坏了就**当场修好**；
2. 修不好就报错，**绝不假装保存成功**（宁可让用户看见「无法持久化」，
   也不要他以为存住了、重启后才发现没了）；
3. 把「这条路是不是持久化的」暴露给接口与设置页，随时可自查。

`CITYVEINS_PERSIST_ROOT` 可覆盖持久化根目录，便于本地测试。
"""

import logging
import os
import shutil

log = logging.getLogger("cityveins.persist")

# 容器里的持久化根目录。懒猫平台把它挂到盒子的 appvar 子卷上。
PERSIST_ROOT = os.path.realpath(
    os.environ.get("CITYVEINS_PERSIST_ROOT", "/lzcapp/var")
)

# 三样东西的「容器内可见路径 → 持久化目录内的相对路径」
AMAP_LINK, AMAP_REL = "/app/data/key/key.txt", "config/amap_key.txt"
WEIGHTS_LINK, WEIGHTS_REL = (
    "/app/data/poi_weights/高德POI_加权.csv",
    "config/poi_weights.csv",
)
OUTPUT_LINK, OUTPUT_REL = "/app/output", "output"
DEEPSEEK_REL = "config/deepseek_key.txt"


def _root() -> str:
    return PERSIST_ROOT.rstrip(os.sep) or os.sep


def is_persistent(path: str) -> bool:
    """path 解析后是否落在持久化目录里（软链会先解析）。"""
    if not path:
        return False
    real = os.path.realpath(path)
    root = _root()
    return real == root or real.startswith(root + os.sep)


def persist_path(rel: str) -> str:
    return os.path.join(_root(), *rel.split("/"))


def _link_ok(link: str, target: str) -> bool:
    """软链已存在且正指向 target。"""
    return os.path.islink(link) and os.path.realpath(link) == os.path.realpath(target)


def _touch(path: str) -> None:
    if os.path.exists(path):
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8"):
            pass
    except OSError as exc:                                # pragma: no cover
        log.warning("[persist] 无法创建 %s：%r", path, exc)


def ensure_file_link(link: str, rel: str, seed: bool = True) -> tuple:
    """确保 link 是指向持久化目录的软链。

    返回 ``(ok, target)``：target 永远是想写到的持久化路径；ok=False 表示
    没能建立这条软链，此时调用方**必须拒绝写入**，而不是退回到 link 本身。

    seed=True 时，若 link 已经是个普通文件（软链没建起来时写进可写层的内容），
    会先把它搬到持久化位置，避免用户已经填好的密钥被这次修复动作弄丢。
    """
    target = persist_path(rel)
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    except OSError as exc:
        log.error("[persist] 持久化目录不可用：%s（%r）", os.path.dirname(target), exc)
        return False, target

    if not _link_ok(link, target):
        # 1) 先抢救：把可写层里的旧内容搬到持久化目录（持久化文件已有内容时不覆盖）
        if (
            seed
            and os.path.isfile(link)
            and not os.path.islink(link)
            and not os.path.exists(target)
        ):
            try:
                shutil.copy2(link, target)
                log.warning("[persist] 已把 %s 的内容迁移到 %s", link, target)
            except OSError as exc:
                log.warning("[persist] 迁移 %s 失败：%r", link, exc)

        # 2) 清掉挡路的旧文件/旧软链
        try:
            os.makedirs(os.path.dirname(link) or ".", exist_ok=True)
        except OSError as exc:
            log.error("[persist] 目录不可用：%s（%r）", os.path.dirname(link), exc)
            return False, target
        if os.path.islink(link) or os.path.isfile(link):
            try:
                os.unlink(link)
            except OSError as exc:
                log.error("[persist] 无法替换 %s：%r", link, exc)
                return False, target
        elif os.path.isdir(link):
            # 文件该在的位置被目录占了，不擅自删目录
            log.error("[persist] %s 是目录，无法改成软链", link)
            return False, target

        # 3) 建软链
        try:
            os.symlink(target, link)
        except OSError as exc:
            log.error("[persist] 无法建立软链 %s -> %s：%r", link, target, exc)
            return False, target

    _touch(target)
    if not is_persistent(link):
        log.error("[persist] %s 解析后仍不在 %s 内，持久化未生效", link, _root())
        return False, target
    return True, target


def _merge_into(src: str, dst: str) -> None:
    """把 src 目录里的内容搬进 dst（已在 dst 里的文件不覆盖）。"""
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        try:
            os.makedirs(out, exist_ok=True)
        except OSError:
            continue
        for name in files:
            s, d = os.path.join(root, name), os.path.join(out, name)
            if os.path.exists(d):
                continue
            try:
                shutil.move(s, d)
            except (OSError, shutil.Error) as exc:
                log.warning("[persist] 迁移 %s 失败：%r", s, exc)


def ensure_dir_link(link: str, rel: str) -> tuple:
    """确保 link 是指向持久化目录的软链（目录版）；返回 (ok, target)。"""
    target = persist_path(rel)
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as exc:
        log.error("[persist] 持久化目录不可用：%s（%r）", target, exc)
        return False, target

    if not _link_ok(link, target):
        if os.path.isdir(link) and not os.path.islink(link):
            # 先把可写层里的产物搬到持久化目录，再换软链 —— 不删数据
            _merge_into(link, target)
            try:
                os.rmdir(link)
            except OSError as exc:
                log.error("[persist] %s 目录未清空，暂不改软链：%r", link, exc)
                return False, target
        elif os.path.lexists(link):
            try:
                os.unlink(link)
            except OSError as exc:
                log.error("[persist] 无法替换 %s：%r", link, exc)
                return False, target
        try:
            os.symlink(target, link)
        except OSError as exc:
            log.error("[persist] 无法建立软链 %s -> %s：%r", link, target, exc)
            return False, target

    if not is_persistent(link):
        return False, target
    return True, target


def status(path: str) -> dict:
    """给接口/页面用的持久化状态（不包含任何密钥内容）。"""
    target = os.path.realpath(path)
    return {
        "path": path,
        "target": target,
        "symlinked": os.path.islink(path),
        "persistent": is_persistent(target),
        "exists": os.path.exists(path),
        "writable": os.access(os.path.dirname(target) or ".", os.W_OK),
        "persist_root": _root(),
    }


def setup_all() -> list:
    """启动时把三条持久化通道各自检查/修复一遍，返回逐项状态。

    只返回状态、不抛异常 —— 容器入口调用它，不能因为持久化有问题就起不来；
    有问题会写进日志（以及接口的 `persistent` 字段），不至于又变成「莫名丢数据」。
    """
    report = []
    for link, rel, kind in (
        (AMAP_LINK, AMAP_REL, "file"),
        (WEIGHTS_LINK, WEIGHTS_REL, "file"),
        (OUTPUT_LINK, OUTPUT_REL, "dir"),
    ):
        try:
            ok, target = (
                ensure_file_link(link, rel) if kind == "file" else ensure_dir_link(link, rel)
            )
        except Exception as exc:                          # noqa: BLE001 兜住一切
            ok, target = False, persist_path(rel)
            log.error("[persist] 检查 %s 时异常：%r", link, exc)
        item = status(link) if ok else {**status(link), "persistent": False, "target": target}
        item["rel"] = rel
        report.append(item)
        log.info(
            "[cityveins] 持久化 %s：%s -> %s（%s）",
            "就绪" if item.get("persistent") else "**未生效**",
            link,
            item.get("target"),
            "在 /lzcapp/var 内，容器重建不丢" if item.get("persistent") else "落在可写层，重建即丢",
        )
    return report
