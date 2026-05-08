

项目地址：

```text
https://github.com/cnbatmoven/xhs-agent.git
```

## 1. 这套工具是做什么的

它可以读取一个 Excel 文件里的小红书笔记链接，然后批量补全：

- 标题、封面、文案、话题
- 点赞、收藏、评论、分享等互动数据
- 达人昵称、达人 ID、达人链接、粉丝量
- 评论区前 20 条
- 蒲公英报价和 CPE
- 内容类型、核心卖点、创意建议、人群圈选策略

它有两种用法：

- 网页版：适合小白，打开浏览器点按钮操作。
- 命令行版：适合开发或批量自动跑。

建议新同学先用网页版。

## 2. 先安装这些软件

在新电脑上先安装 4 个东西。

### Git

下载并安装：

```text
https://git-scm.com/downloads
```

安装时一路默认即可。装好后，打开 PowerShell，输入：

```powershell
git --version
```

能看到版本号就说明安装成功。

### Python 3.10 或更高

下载并安装：

```text
https://www.python.org/downloads/
```

安装时请勾选：

```text
Add python.exe to PATH
```

装好后，在 PowerShell 输入：

```powershell
python --version
```

推荐看到 `Python 3.10`、`3.11`、`3.12` 或更高。

### Node.js

下载 LTS 版本并安装：

```text
https://nodejs.org/
```

装好后，在 PowerShell 输入：

```powershell
node --version
npm --version
```

能看到版本号就可以。

### Google Chrome

需要用真实 Chrome 登录小红书，降低登录和验证码问题。

下载地址：

```text
https://www.google.com/chrome/
```

## 3. 下载项目

找一个你想放项目的位置，比如 `D:\work`。

打开 PowerShell：

```powershell
cd D:\
mkdir work
cd work
git clone https://github.com/cnbatmoven/xhs-agent.git
cd xhs-agent
```

以后教程里的命令都默认在这个项目目录里执行。

可以输入下面命令确认你在正确目录：

```powershell
pwd
```

应该能看到类似：

```text
D:\work\xhs-agent
```

## 4. 安装后端依赖

后端是 Python 写的。先创建一个独立环境：

```powershell
python -m venv .venv
```

激活环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示不允许运行脚本，先执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，命令行前面通常会出现：

```text
(.venv)
```

安装 Python 依赖：

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

安装 Playwright 浏览器组件：

```powershell
python -m playwright install chromium
```

## 5. 安装前端依赖

前端是网页控制台。进入前端目录：

```powershell
cd frontend
npm install
cd ..
```

## 6. 准备 Excel 文件

你的 Excel 需要有一个工作表：

```text
笔记明细
```

里面至少要有小红书笔记链接列。常见列名可以是：

```text
笔记链接
笔记URL
链接
```

建议先用 1 到 5 条数据测试，不要一开始就跑 50 条或 100 条。

## 7. 启动小红书登录浏览器

采集网页内容时，最好用真实 Chrome 登录小红书。

在项目根目录打开一个新的 PowerShell，执行：

```powershell
$PROJECT = (Get-Location).Path
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PROJECT\chrome-debug-profile" --no-first-run --no-default-browser-check https://www.xiaohongshu.com
```

这会打开一个新的 Chrome 窗口。

在这个窗口里：

1. 打开小红书。
2. 扫码登录。
3. 如果要抓蒲公英报价，也在同一个 Chrome 里登录蒲公英后台。
4. 登录完成后不要关闭这个 Chrome。

这个 Chrome 的调试地址是：

```text
http://127.0.0.1:9222
```

后面网页控制台里的 `cdp_url` 就填它。

## 8. 启动后端

在项目根目录打开一个 PowerShell。

如果还没激活 Python 环境，先激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

启动后端：

```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

看到类似下面内容就表示成功：

```text
Uvicorn running on http://127.0.0.1:8001
```

不要关闭这个窗口。

可以用浏览器打开检查：

```text
http://127.0.0.1:8001/health
```

正常会看到：

```json
{"status":"ok"}
```

## 9. 启动前端网页

再打开一个新的 PowerShell，进入项目目录：

```powershell
cd D:\work\xhs-agent
cd frontend
npm run dev
```

看到类似下面内容就表示成功：

```text
Local: http://127.0.0.1:5173/
```

用浏览器打开：

```text
http://127.0.0.1:5173/
```

如果 `5173` 被占用，Vite 可能会显示 `5174` 或别的端口，以它实际显示的地址为准。

## 10. 在网页里跑一次任务

打开网页控制台后，按这个顺序操作：

1. 上传你的 Excel 文件。
2. 确认 `cdp_url` 是：

```text
http://127.0.0.1:9222
```

3. 第一次测试建议设置：

```text
limit = 1 或 5
crawl_delay = 10 到 30
download_covers = 开
embed_covers = 开
crawl_pgy = 先关
use_llm = 先关
```

4. 点击创建任务或运行任务。
5. 看任务状态从 `queued` 到 `running`，最后变成 `succeeded`。
6. 在结果文件里下载 Excel 或 CSV。

输出文件默认会在项目目录的：

```text
outputs/
```

## 11. 使用 LLM 分析

如果要让系统生成更丰富的创意建议，需要准备一个 OpenAI-compatible API Key，例如 OpenAI 或 DeepSeek。

在启动后端的 PowerShell 里，先设置环境变量，再启动后端：

```powershell
$env:LLM_API_KEY="你的 API Key"
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_MODEL="deepseek-v4-flash"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

如果用 OpenAI，可以改成：

```powershell
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4.1-mini"
```

然后在网页里打开：

```text
use_llm
```

第一次建议先跑 1 到 3 条测试。

## 12. 使用蒲公英报价

蒲公英报价更容易触发权限、登录或风控问题。建议这样做：

1. 先在第 7 步打开的 Chrome 里登录蒲公英后台。
2. 网页里打开：

```text
crawl_pgy = 开
pgy_safe_mode = 开
pgy_delay = 12 或更高
pgy_max_retries = 2
```

3. 先跑 1 到 3 条。
4. 如果稳定，再慢慢增加条数。

## 13. 遇到安全验证怎么办

如果 Chrome 出现小红书安全验证、验证码、请勿频繁操作：

1. 先暂停继续跑大批量任务。
2. 在 Chrome 里手动完成验证。
3. 等 10 到 30 分钟。
4. 把 `crawl_delay` 调大，例如：

```text
30
60
```

5. 分批跑，不要一次跑太多。

建议：

- 普通小红书采集：每批 10 到 50 条。
- 蒲公英报价：每批 1 到 10 条。
- 遇到风控后不要连续重试。

## 14. 常见问题

### 打不开网页控制台

确认前端是否启动：

```powershell
cd frontend
npm run dev
```

看终端显示的地址，例如：

```text
http://127.0.0.1:5173/
```

### 网页显示后端离线

确认后端是否启动：

```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

再打开：

```text
http://127.0.0.1:8001/health
```

### 端口被占用

如果 `8001` 被占用，可以先看看是谁占用：

```powershell
netstat -ano | findstr :8001
```

结束对应进程，或者换一个端口。但如果换后端端口，也要同步改：

```text
frontend/vite.config.js
```

### Python 依赖安装失败

先确认 Python 版本：

```powershell
python --version
```

建议 Python 3.10 或更高。

然后升级 pip：

```powershell
python -m pip install --upgrade pip
```

再重新安装：

```powershell
pip install -r requirements.txt
```

### npm install 很慢

可以换 npm 镜像：

```powershell
npm config set registry https://registry.npmmirror.com
npm install
```

### Chrome 没有启动或 CDP 连不上

确认这个地址能打开：

```text
http://127.0.0.1:9222/json
```

如果打不开，重新执行第 7 步的 Chrome 启动命令。

### Excel 提示找不到工作表

确认 Excel 里有工作表：

```text
笔记明细
```

不是文件名叫这个，而是 Excel 底部的 sheet 名称叫这个。

### 结果为空或很多 failed

常见原因：

- 没登录小红书。
- Chrome 不是用 `--remote-debugging-port=9222` 启动的。
- 小红书触发安全验证。
- 链接失效。
- 跑得太快。

建议先只跑 1 条，把 `crawl_delay` 调到 `30`。

## 15. 开发同学如何提交代码

第一次下载：

```powershell
git clone https://github.com/cnbatmoven/xhs-agent.git
cd xhs-agent
```

每天开始开发前先拉最新代码：

```powershell
git pull
```

改完后提交：

```powershell
git status
git add .
git commit -m "你的修改说明"
git push
```

不要提交这些目录：

```text
outputs/
data/
browser-profile/
chrome-debug-profile/
frontend/node_modules/
frontend/dist/
```

这些已经写在 `.gitignore` 里，正常不会被提交。

## 16. 最小启动命令速查

第一次安装：

```powershell
git clone https://github.com/cnbatmoven/xhs-agent.git
cd xhs-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
cd frontend
npm install
cd ..
```

每次使用：

```powershell
cd D:\work\xhs-agent
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

再开一个 PowerShell：

```powershell
cd D:\work\xhs-agent\frontend
npm run dev
```

再开一个 PowerShell，启动登录浏览器：

```powershell
cd D:\work\xhs-agent
$PROJECT = (Get-Location).Path
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PROJECT\chrome-debug-profile" --no-first-run --no-default-browser-check https://www.xiaohongshu.com
```

然后打开前端显示的地址，例如：

```text
http://127.0.0.1:5173/
```
