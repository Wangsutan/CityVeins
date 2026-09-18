# 记录袋（云端已形成数据）与安卓预览修复

记录时间：2026-09-18

## 一、这次改了什么

用户反馈两件事：

1. **安卓端打开报告预览、关掉预览之后，已经查出来的结果就没了。** 桌面端正常。
2. **既然数据都存在云端，就再加一个「已形成数据」的列表页，专门从那上面下载。**

对应两处改动：

| # | 改动 | 文件 |
|---|---|---|
| 1 | 报告预览从 `window.open` 改成**站内 iframe 弹层**；状态加 `sessionStorage` 兜底 | `index.html`（项目根，buildscript 拷进 `backend/app/`） |
| 2 | 新增「记录袋」：`/records` 页面 + `/api/records*` 接口 | `lazycat/backend/records_api.py`、`lazycat/backend/records.html` |
| — | 注册新蓝图 | `lazycat/backend/run_lazycat.py` |

## 二、安卓为什么丢结果

### 根因

原来的预览是这么写的：

```js
window.open(reportUrl, '_blank');
```

页面上所有「结果」都只活在内存里的四个变量里：

```js
let lastResult = null;        // 查到的住宅区
let candidates = [];
let currentSaveDir = '';      // 云端保存目录，下载/AI报告都靠它
let currentResidentialName = '';
```

于是：

- **桌面端**：新标签页打开报告，主页面没被卸载，变量都还在 → 关掉新标签后一切正常。
- **安卓端**（懒猫 webapk / WebView）：`window.open` 会走系统外部浏览器或新 Activity，
  当前 WebView 被切走 / 重建，**页面被重新加载** → 四个变量回到初始值 →
  「保存到云端 / AI生成报告 / 下载到本地」全部变灰，看起来就是"结果丢了"。

### 为什么不是拦截器干的

懒猫的文件/下载拦截脚本 `lzc-file-chooser-inject.js` 只钩这一处：

```js
HTMLAnchorElement.prototype.click = hookedClick;   // 且要求 anchor.download 存在、href 是 blob:
```

它**完全不碰 `window.open`**。所以下载这条路一直没问题，出问题的只有预览。

> 顺带确认了一件事：那个注入脚本自己就是用 `iframe` 装文件选择器的
> （`lzc-file-picker` custom element），说明**站内 iframe 在这个平台上是可行的**，
> 拿 iframe 做预览不会踩到平台的坑。

### 修法

1. **不再开新窗口**：`previewReport()` / `previewAIReport()` 改调 `openPreviewModal()`，
   在同一页面的整屏弹层里用 `<iframe src="/preview/...">` 打开报告。
   主页面全程不卸载，变量自然还在。关掉弹层时清空按钮，但**不动任何业务状态**。
2. **兜底持久化**：`saveSession()` 把 `lastResult / candidates / currentSaveDir /
   currentResidentialName / radius / 日志` 写进 `sessionStorage`，
   在 `pagehide`、`visibilitychange`（切后台）时各存一次；
   页面加载时 `restoreSession()` 恢复，并追加一行「已恢复上次的结果与云端目录」。
   用 `sessionStorage` 而不是 `localStorage`：关掉标签页就失效，
   不会把上一次的结果跨会话一直摆在那里造成误解。

即使以后平台又在别的地方把页面重载了，第 2 条也能把结果捞回来。

后端 `/preview/<subpath>/<filename>` 本来就是 `as_attachment=False`（inline）、
且没有 `X-Frame-Options`，所以 iframe 能直接嵌 —— 这点已实测确认。

## 三、记录袋（/records）

### 数据从哪来

`/save` 每存一次就在 `output/web_save/<住宅区ID>_<YYYYmmdd_HHMMSS>/` 落一个目录：

```
L430722_20260918_195210/
├── report_L430722.md / .html        评估报告
├── ai_report_L430722.md / .html     AI 分析报告（点了「AI生成报告」才有）
├── poi_L430722_unique.csv           去重后的 POI
├── score_L430722.csv                评分明细
├── summary.json                     总分 / POI 数 / 类目数 / 时间戳
└── stats_L430722.json               大中小类统计
```

`run.sh` 把 `/app/output` 软链到持久化目录 `/lzcapp/var/output`，
所以这些目录**一直在云上**，容器重建也不丢。以前只是界面上够不着。

### 页面能做什么

- 入口：首页「下载到本地」→ 展开区底部的「📦 打开记录袋」（页脚另有一个低调链接）
- 全部记录按时间**倒序**列出；显示住宅区名、ID、保存时间、加权总分、POI 数、
  覆盖大类/中类、文件数、占用空间
- **按钮文案随实际状态切换**：已有报告 → 「预览评估报告 / 预览 AI 报告」；
  没有报告 → 「生成评估报告 / 生成 AI 报告」，点了**真去生成**，成功后自动预览。
  数据不足以生成时按钮置灰，并说明缺什么（`missing_for_generate`）。
  预览走站内弹层，和首页同一套逻辑（不开新窗口）
- **文件清单**：展开后逐个文件预览 / 下载
- **下载全部（ZIP）**：把整条记录打成 `<记录目录>.zip`
- **删除**：需要二次确认（`confirm()` + 后端强制 `?confirm=1`）
- 支持按名称/ID 搜索、只看含 AI 报告的记录、刷新
- 徽章标出「含 AI 报告」「报告缺失」「可能未写完」

### 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/records` | 列表页 |
| GET | `/api/records` | 全部记录（倒序） |
| GET | `/api/records/<rid>/<ts>` | 单条记录 + 文件清单 |
| GET | `/records/<rid>/<ts>/zip` | 打包下载（流式，临时文件用完即删） |
| GET | `/api/records/default-ai-prompt` | AI 报告默认提示词（供生成弹窗预填） |
| POST | `/api/records/<rid>/<ts>/generate-report` | 重建评估报告（不联网、不重拉 POI） |
| POST | `/api/records/<rid>/<ts>/delete?confirm=1` | 删除整条记录 |

### 几个刻意的设计

- **目录名当唯一键**：只接受 `<字母数字ID>_<8位日期>_<6位时间>` 这种形状，
  不匹配的目录（例如手工建的空壳）一律不进列表，因此**路径穿越不可能发生**。
  名字里只有字母数字和下划线，天然没有 `/` 和 `.`。
- **住宅区名从报告标题里取**：目录名里只有 ID，`summary.json` 里也没存中文名。
  报告 MD 首行是 `# 湖南省常德市汉寿县恒大御府 15 分钟生活圈评估报告`，
  把尾部固定串去掉就是名字 —— 历史记录与新记录都适用，
  **不用改 `app.py` 的 `/save` 也不用迁移数据**。取不到就退回显示 ID。
- **ZIP 不写在数据目录里**：原 `app.py` 的 `/download-zip` 把临时 zip 写进
  `SAVE_ROOT` 再删掉，会短暂污染数据目录，也不适合做「按记录下载」的稳定入口。
  记录袋的 zip 用 `tempfile` 建在系统临时目录、0600、回传后 `finally` 清理。
- **空记录不打空包**：目录里没有文件时返回 404 并说明原因，而不是给一个空 zip。
- **超大记录拦下来**：单条超过 512 MB 时返回 413，提示改用逐个下载，
  避免一个请求把内存和磁盘打满。
- **重建报告不给 `/report` 接口用**：`app.py` 的 `/report` 写的是
  `{rid}_评估报告.md`，而 `/save` 写的是 `report_{rid}.md`，两种命名会共存且
  记录袋只认后者。所以生成接口自己调 `generate_markdown_report()`，
  文件名与 `/save` 对齐。
- **重建报告不消耗高德配额**：输入全部来自记录目录里的
  summary.json / stats_*.json / score_*.csv，不重新查询、不重新拉 POI。
  只有 AI 报告要联网（走 DeepSeek）。

## 四、验证

本地建了三套测试（都在 `~/Desktop/lan-browser/cityveins-work/`，不进本仓库）：

| 测试 | 覆盖 |
|---|---|
| `test_records_api.py` | 造 5 种记录（正常/带AI/空目录/缺summary/非法目录名），跑列表、详情、zip、删除、路径穿越拒绝 |
| `test_state_restore.js` | 在 Node `vm` + 手写 DOM 打桩里跑真实前端脚本：查询→选点→保存→**模拟页面重载**→断言结果与按钮都恢复；并断言脚本里不再有 `window.open` |
| `verify_http.py` | 对着**真实云端数据副本**跑 HTTP：13 条记录、11 条 zip 全部 200、预览是 inline 且无 `X-Frame-Options`、下载是 attachment + RFC5987 中文名 |

线上部署后复核：

```bash
# 盒子：192.168.110.148
lzc-docker exec cloudlazycatappcityveins-app-1 sh -c '
  wget -qO- http://127.0.0.1:8000/records | grep -c 记录袋
  wget -qO- http://127.0.0.1:8000/api/records | head -c 300'
```

## 五、重新部署会不会丢东西（2026-09-18 追加）

用户问：「重新部署之后，以前的 API 会丢吗」。查实结果如下。

### 1. 接口本身：不会丢

`project deploy` 是**装新包覆盖旧包**（journal 里可见 `PkgUninstalled` →
`PkgInstalled` 成对出现），路由都写在代码里，跟镜像一起更新，只增不减。

### 2. 数据与密钥：不会丢（但当时确实出问题了）

持久化落在盒子的 `/lzcsys/data/appvar/cloud.lazycat.app.cityveins/`，
容器里是 `/lzcapp/var`，跟镜像完全分离。**装了三次新包之后**，下面这些都还在，
时间戳还是最初的：

```
config/amap_key.txt        32 字节   09-18 11:59    ← 用户填的高德 Key
config/deepseek_key.txt    35 字节   09-18 12:11    ← 用户填的 DeepSeek Key
config/poi_weights.csv    117642 字节 09-18 16:49   ← 权重页的改动
output/web_save/…          最早一条 09-18 12:03     ← 最早那批评估记录
```

`lzc-cli` 里只有 `lpk uninstall --delete-data` 会删数据
（`lib/lpk/index.js` 的 `uninstallHandler({pkgId, deleteData})`），
`project deploy` 从不传这个参数，所以**正常部署不会清数据**。

### 3. 但当时高德 Key 确实读不到了（已修，见 acde440）

`/api/settings/amap-key` 报 `configured: false`，而持久化文件里明明有密钥。
根因不在部署，是一条潜伏的构建问题：

1. 项目 `.gitignore` 第 135 行忽略了 `data/key/` → 该目录里除 `.gitkeep`
   外没有任何被 git 跟踪的文件；
2. **lzc 的构建通道打出的构建上下文 tar 会丢弃点文件** ——
   实测 `tar tf lzc-build-image-context.tar | grep -c data/key` = **0**，
   `.gitkeep` 一起没了，于是镜像里 `/app/data/key/` 这个目录根本不存在；
3. `run.sh` 的 `ln -sfn "$KEY_PERSIST" /app/data/key/key.txt` 因父目录不存在
   而失败，还被 `|| true` 吞掉 → `key.txt` 永远不出现 →
   `load_key()` 读成空字符串。

**密钥没丢，是应用看不见它。** 修法：`run.sh` 显式 `mkdir -p /app/data/key`，
并把 `: > "$KEY_PERSIST"` 换成 `[ -f … ] || touch …`（前者在特定状态下
会把已写好的密钥清空），再加一行启动自检。

修完后线上实测：`configured:true, length:32, source_exists:true, symlinked:true`，
并在容器里直连高德 REST API 拿到 `status=1 info=OK`，样例返回「恒大御府 | 道里区」，
确认是真能用，而不只是"读到了 32 字节"。

### 4. 部署后必须做的两件事

```bash
# ① project deploy 之后应用会停在 Status_Paused，必须再 start
lzc-cli project deploy && lzc-cli project start

# ② 确认 Key 活着（别只看页面能不能打开）
lzc-docker exec cloudlazycatappcityveins-app-1 \
  wget -qO- http://127.0.0.1:8000/api/settings/amap-key
```

`~/deploy_cityveins.sh` 已经把这两步串起来了。

## 六、设置页拆分：列表页 + 各自独立的设置页

用户要求：「点开设置按钮之后应该展示设置列表，高德 api 和 deepseek api 也要分成
独立的设置项，点击设置项再专门设置」「跟权重设置页面不要混在一起」。

原来的 `/settings` 是一张长表单：两个 Key 卡片 + 整张权重表全挤在一页，
顶部只有两个锚点 tab。现在拆成：

| 路径 | 内容 |
|---|---|
| `/settings` | **设置列表页**：三项各一格，点进去才是设置。只读状态摘要，不含任何输入框 |
| `/settings/amap` | 高德 API Key（必填）—— 只有它自己的输入框与帮助 |
| `/settings/deepseek` | DeepSeek API Key（可选·强烈推荐）—— 只有它自己 |
| `/weights` | POI 权重（原来嵌在 `/settings` 里，之前 **404**，这次一并补齐） |

拆法（可复现，不是手抄）：`settings.html` 原文件按行切成
CSS / header / keys-UI / weights-UI / tail / 各段 JS，
`weights.html` = 原权重 UI + 原权重 JS，`amap.html` / `deepseek.html` =
原对应 Key 卡片 + 原 Key JS（`KINDS` 只保留自己那一项，启动只 load 自己），
`settings.html` 重写为列表页。这样权重那套已经验证过的交互一行代码都没变。

路由：`settings_api` 增加 `/settings/amap`、`/settings/deepseek`；
`weights_api` 增加 `/weights`（它之前只有 `/api/weights`，没有页面 ——
首页页脚曾经挂过一个指向 `/weights` 的链接就是 404，已修正）。

`Dockerfile` 必须为每个新页面补 `COPY`（`amap.html` / `deepseek.html` /
`weights.html`）—— 上一轮就因为漏 COPY `records_api.py` 导致整个进程起不来。

## 七、记录袋里「生成 AI 报告」报「POI文件不存在」（已修）

现象：在记录袋里点「生成 AI 报告」，报 `生成失败：POI文件不存在`。
而那条记录的目录里，`poi_<rid>_unique.csv` 明明躺着。

根因：`save_dir` 的两种写法没对齐。

- `/save` 返回的 `save_dir` 是**绝对路径**（`/app/output/web_save/<id>_<ts>`），
  首页把它原样回传给 `/ai-report`，所以首页一直没事；
- 记录袋手上只有**目录名**（`<id>_<ts>`，因为它就是这么列出来的），也原样传了过去；
- 而 `app.py` 的 `/ai-report` 直接 `os.path.join(save_dir, f"poi_{rid}_unique.csv")` ——
  传进来的目录名是相对路径，于是拼成 `L460203_20260918_195639/poi_...csv`，
  相对于进程工作目录 `/app` 去找，必然不存在。

在容器里可以直接复现这个判断：

```sh
cd /app && ls L460203_20260918_195639        # → No such file or directory
ls /lzcapp/var/output/web_save/L460203_20260918_195639/poi_L460203_unique.csv   # → 在
```

修法（改的是 `sources/app.py`，两处小函数）：

1. `_record_dir()`：把 `save_dir` 归一成绝对目录 —— 绝对路径原样接受，
   单纯的目录名则挂到 `SAVE_ROOT` 下；带分隔符或 `..` 的一律拒绝（400）。
2. `_find_poi_csv()`：找 POI 表的顺序变成
   `记录目录/unique → 记录目录/未去重 → output/poi/unique → output/poi/未去重`。
   最后两条是新加的兜底：随记录走的 POI 副本可能被清理掉，而 `output/poi/` 下的
   原始产物通常还在，能救回来就不用重新抓一遍（**省高德配额**）。
3. `records_api._poi_fallback_exists()` 与第 2 条对齐，这样记录袋的
   `can_generate_ai_report` 判据和 `/ai-report` 的实际行为一致
   （否则按钮灰着、其实生成得出来）。
4. 记录袋前端启动时查一次 DeepSeek Key 状态，**没配就直接把「生成 AI 报告」置灰**
   并在 tooltip 里指向设置页，而不是让用户点了才报错。

验证：`test_ai_report_paths.py`（离线单测，抠出那两个纯函数跑）覆盖两种写法、
四种 POI 查找顺序、以及 `../` 穿越拒绝；线上实测记录袋那种「只传目录名」的写法
已经能真正跑出 AI 报告（返回 `html_ok: true`），绝对路径写法同样正常，
非法 `save_dir` 返回 400。

## 八、以后改这块要注意

- **别在应用里用 `window.open` / `location.href` 打开报告或文件** ——
  安卓上会把页面顶掉，内存里的结果就没了。预览一律走站内弹层，
  下载一律走 blob + `a.download`（懒猫拦截器只认这条路）。
- **记录袋入口的位置只有一处：首页功能按钮列的第 4 个按钮**
  （`.action-buttons` 里，紧跟「下载到本地」）。它是 `<a>` 但套了 `.action-btn`
  外观，且**始终可点** —— 不依赖本次会话有没有查询结果。
  两个踩过的坑，别再犯：
    1. 别放进「下载到本地」的展开区（`#download-options`）—— 用户要的是"按钮"，
       不是展开区里的附属链接；
    2. 别再往页头或页脚加入口 —— 页头要留给标题，页脚用户明确说"莫名其妙"。
  改动后跑 `verify_http.py`，H 段有 6 条断言专门盯这个位置与"全页只有一个入口"。
- `lazycat/backend/app/` 是 buildscript 生成的（gitignore 里忽略），
  **不要直接改**；要改前端就改项目根的 `index.html`。
