# 小红书笔记批量处理 Agent

这个小 agent 会从 Excel 的 `笔记明细` sheet 读取笔记链接，批量提取/补全：

- 标题
- 封面
- 文案
- 话题
- 点赞数、收藏数、评论数、分享数
- 创意建议
- 人群圈选策略

它兼容部分平台导出的异常 `.xlsx` 文件，例如工作表 `dimension` 错误导致普通 Excel 库只能读到 `A1` 的情况。

如果你是第一次使用，建议先看纯小白教程：

```text
docs/BEGINNER_GUIDE.md
```

## 安装依赖

```powershell
pip install -r requirements.txt
playwright install chromium
```

`xhshow` 需要 Python 3.10+。如果本机默认 `python` 是 3.9，可以直接用 Codex 工作区自带的 Python 运行：

```powershell
& "C:\Users\15634\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --limit 1
```

如果只是先验证 Excel 读取和离线分析，可以不安装 Playwright，使用 `--no-crawl`。
不安装 Playwright 时，agent 会尝试用标准库做静态请求兜底，但小红书页面常需要登录态和动态渲染，正文/封面字段可能采集不完整。

## 快速运行

离线分析已有表格数据：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --no-crawl
```

采集网页详情并分析：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --limit 20
```

如果需要先扫码登录，让页面固定住，不要马上批量跳链接：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --profile ".\browser-profile" --login-first --download-covers
```

运行后浏览器会先停在小红书首页/登录页。扫码登录完成后，回到 PowerShell 按 Enter，agent 才会开始批量采集。

使用本机浏览器登录态目录：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --profile ".\browser-profile" --limit 20
```

首次运行如果页面要求登录，请在弹出的浏览器里登录小红书，登录态会保存在 `browser-profile`。
agent 会优先自动发现本机 Chrome/Edge，因此即使 Playwright 自带浏览器没有下载完成，也可以直接复用系统浏览器。

手动指定浏览器：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --browser-executable "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile ".\browser-profile" --limit 20
```

如果小红书登录页二维码一直刷新，使用真实 Chrome 调试端口：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="D:\xhs\chrome-debug-profile"
```

在这个 Chrome 窗口里手动打开并登录小红书：

```text
https://www.xiaohongshu.com
```

登录完成后，另开一个 PowerShell 运行：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_full.xlsx --cdp-url "http://127.0.0.1:9222" --download-covers --crawl-delay 10
```

## 参考 MediaCrawler 后的优化

当前版本借鉴了 MediaCrawler 的小红书采集思路：

- 优先用 CDP 连接真实 Chrome，复用用户真实登录态。
- 从 URL 中解析 `note_id`、`xsec_token`、`xsec_source`。
- 优先解析页面内的 `window.__INITIAL_STATE__` / `noteDetailMap`，比 DOM 文本更稳定。
- 评论区先合并详情页结构化数据、页面可见评论；不足 20 条时，会使用已登录浏览器 cookie 和签名接口继续分页补采。
- 达人粉丝量优先走 `user/otherinfo` 签名接口，减少跳达人主页触发身份验证的概率。
- Excel 已有的点赞、收藏、评论、分享数据优先保留，避免页面文本误判。
- 识别 `安全验证 / 请勿频繁操作` 页面，默认停止后续采集，避免继续触发风控。

遇到风控时，建议等待一段时间后慢速分批跑：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_slow.xlsx --cdp-url "http://127.0.0.1:9222" --download-covers --crawl-delay 15
```

如果你明确希望遇到风控也继续跑：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_continue.xlsx --cdp-url "http://127.0.0.1:9222" --no-stop-on-rate-limit
```

## 接入 LLM API

agent 支持 OpenAI-compatible 的 `/chat/completions` 接口。规则分析会先生成一版兜底结果，启用 LLM 后再优化：

- `内容类型`
- `标题结构`
- `核心卖点`
- `互动倾向`
- `创意建议`
- `人群圈选策略`

### 配置环境变量

PowerShell 示例：

```powershell
$env:LLM_API_KEY="你的 API Key"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4.1-mini"
```

也可以换成其他 OpenAI-compatible 服务，例如：

```powershell
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_MODEL="deepseek-v4-flash"
```

### 离线 LLM 分析

如果暂时不重新采集网页，只基于 Excel 已有标题和互动数据分析：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_llm.xlsx --no-crawl --use-llm
```

### 采集 + LLM 分析

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_full_llm.xlsx --cdp-url "http://127.0.0.1:9222" --download-covers --crawl-delay 15 --use-llm
```

也可以直接用命令参数传配置：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --no-crawl --use-llm --llm-api-key "你的 API Key" --llm-base-url "https://api.openai.com/v1" --llm-model "gpt-4.1-mini"
```

输出表会新增 `LLM状态`、`LLM模型` 两列。若单条 LLM 调用失败，会保留规则分析结果，并在 `LLM状态` 里记录失败原因。

下载封面到本地：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --profile ".\browser-profile" --download-covers
```

## 输出

默认输出到：

```text
outputs/xhs_note_analysis.xlsx
outputs/covers/
```

结果表包含三类信息：

- `采集字段`：标题、链接、封面、文案、话题、互动数据
- `内容分析`：内容类型、核心卖点、标题结构、互动倾向
- `策略建议`：创意建议、人群圈选策略

## 新增字段：达人、评论、蒲公英成本

当前输出表新增：

- `达人昵称`
- `达人ID`
- `达人链接`
- `粉丝量`
- `评论区前20条`
- `总互动量`
- `蒲公英链接`
- `蒲公英报价`
- `CPE`
- `内容类型分组`

评论区前 20 条会优先从小红书详情页结构化数据里提取，并合并页面可见评论；如果不足 20 条，默认会用 `xsec_token` 和登录态 cookie 调用评论分页接口补采。若要关闭接口补采，只保留页面可见评论，可加：

```powershell
--no-comment-api
```

### 内容类型分组

脚本会把内容进一步分到：

- 攻略/选购指南
- 家庭场景种草
- 痛点解决/体验改善
- 技术卖点解释
- 真实体验分享
- 节点/事件内容
- 泛种草内容

### 蒲公英报价和 CPE

如果源 Excel 有这些列，脚本会直接读取：

- `达人ID`
- `达人链接`
- `蒲公英链接`
- `蒲公英报价`

`CPE = 蒲公英报价 / (点赞数 + 收藏数 + 评论数 + 分享数)`

## 后端部署

现在项目同时支持两种运行方式：

- `CLI`：继续直接运行 `xhs_note_agent.py`
- `HTTP API`：运行 FastAPI 后端，对外提供同步执行和后台任务接口

启动后端：

```powershell
uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

健康检查：

```text
GET /health
```

创建后台任务：

```text
POST /api/v1/jobs
```

同步执行一次任务：

```text
POST /api/v1/run-sync
```

示例请求体：

```json
{
  "input": "D:/xhs/空调内容分析/发现【产品种草】「近30日」「阅读率」top榜单.xlsx",
  "output": "D:/xhs/outputs/api_run.xlsx",
  "limit": 50,
  "cdp_url": "http://127.0.0.1:9222",
  "download_covers": true,
  "embed_covers": true,
  "crawl_pgy": true,
  "pgy_delay": 8,
  "use_llm": true,
  "llm_base_url": "https://api.deepseek.com/v1",
  "llm_model": "deepseek-v4-flash"
}
```

查询任务状态：

```text
GET /api/v1/jobs/{job_id}
```

## 蒲公英双报价

当前输出新增：

- `蒲公英图文报价`
- `蒲公英视频报价`
- `图文CPE`
- `视频CPE`

说明：

- `蒲公英报价` 继续保留，默认等于 `蒲公英图文报价`，用于兼容旧表格和旧逻辑
- `CPE` 继续保留，默认等于 `图文CPE`
- 当账号已登录蒲公英且可访问达人详情页时，脚本会优先直达达人详情页抓取 `图文笔记一口价` 和 `视频笔记一口价`

如果要尝试进入蒲公英后台抓报价，需要先在同一个真实 Chrome 里登录蒲公英后台，然后运行：

```powershell
python .\xhs_note_agent.py --input "C:\Users\15634\Documents\内容种草-发现-阅读-近30天.xlsx" --output outputs\xhs_note_analysis_pgy.xlsx --cdp-url "http://127.0.0.1:9222" --crawl-pgy --no-crawl
```

说明：蒲公英后台页面和权限会随账号版本变化。当前脚本会优先使用 `蒲公英链接`，没有链接时用 `达人ID/达人链接` 打开蒲公英搜索入口，并从页面文本里识别报价和粉丝量；识别失败会写入 `异常信息`，不会影响已有数据和 CPE 计算。
## API Additions

- `GET /api/v1/jobs/{job_id}/summary`: returns aggregate metrics for one completed job.
- `POST /api/v1/run-sync`: now returns `summary` together with output paths.
- `POST /api/v1/jobs`: accepted new Pugongying controls:
  - `pgy_safe_mode`
  - `pgy_max_retries`

Recommended Pugongying settings for lower risk:

```json
{
  "crawl_pgy": true,
  "pgy_delay": 12,
  "pgy_safe_mode": true,
  "pgy_max_retries": 2
}
```

## LangGraph Execution

The backend queue now runs through a LangGraph wrapper while keeping the existing crawler available.

Current graph:

```text
parse_intent -> plan_steps -> validate_input -> run_legacy_agent -> summarize -> preview
```

Important compatibility rule:

- `run_legacy_agent` still calls `xhs_note_agent.run(args)`.
- Existing CLI commands continue to work.
- XHS and Pugongying crawling are not split apart yet, so the proven crawler path remains available.
- If LangGraph cannot be imported, the backend falls back to the legacy runner.

The next refactor step is to split `run_legacy_agent` into smaller nodes:

```text
load_notes -> crawl_xhs -> analyze_rules -> crawl_pgy -> llm_analyze -> write_outputs
```
