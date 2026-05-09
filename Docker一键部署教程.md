# Docker 一键部署教程

这份教程给完全不想安装 Python、Node 的同学使用。部署完成后，只需要打开网页：

```text
http://127.0.0.1:8000
```

就可以上传 Excel、提交任务、下载结果。

## 一、先准备这些东西

### 1. 安装 Docker Desktop

Windows / Mac 用户安装 Docker Desktop：

```text
https://www.docker.com/products/docker-desktop/
```

安装完成后，打开 Docker Desktop，确认左下角显示 Docker 正在运行。

### 2. 安装 Google Chrome

下载地址：

```text
https://www.google.com/chrome/
```

这个工具抓小红书时，需要复用一个已经登录的小红书 Chrome。

## 二、方式一：不安装 Git，直接部署

适合只想使用工具的同学。

打开 PowerShell，复制执行：

```powershell
mkdir xhs-agent-docker
cd xhs-agent-docker
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/cnbatmoven/xhs-agent/main/docker-compose.yml" -OutFile "docker-compose.yml"
mkdir data
mkdir outputs
docker compose up -d
```

启动完成后打开：

```text
http://127.0.0.1:8000
```

如果页面能打开，说明后端和前端已经通过 Docker 启动成功。

## 三、方式二：已经安装 Git 的部署方式

适合团队同学后续需要更新代码的情况。

```powershell
git clone https://github.com/cnbatmoven/xhs-agent.git
cd xhs-agent
docker compose up -d
```

打开：

```text
http://127.0.0.1:8000
```

## 四、启动小红书登录 Chrome

Docker 只负责运行工具本身，不能替你扫码登录小红书。所以还需要在宿主机打开一个专用 Chrome。

打开一个新的 PowerShell，进入你部署工具的目录，然后执行：

```powershell
$PROJECT = (Get-Location).Path
$CHROME = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
if (!(Test-Path $CHROME)) { $CHROME = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe" }
& $CHROME --remote-debugging-address=0.0.0.0 --remote-debugging-port=9222 --user-data-dir="$PROJECT\chrome-debug-profile" --no-first-run --no-default-browser-check https://www.xiaohongshu.com
```

Chrome 打开后：

1. 登录小红书。
2. 如果要抓蒲公英报价，也在这个 Chrome 里登录蒲公英后台。
3. 不要关闭这个 Chrome。

确认 Chrome 调试端口正常：

```text
http://127.0.0.1:9222/json/version
```

如果浏览器里能看到一段 JSON，说明 Chrome 已经准备好了。

网页里的 `Chrome CDP` 默认会使用：

```text
http://host.docker.internal:9222
```

## 五、使用工具

打开：

```text
http://127.0.0.1:8000
```

然后按顺序操作：

1. 上传 Excel。
2. 填写任务描述。
3. 确认 `Chrome CDP` 是 `http://host.docker.internal:9222`。
4. 第一次建议 `条数上限` 填 `1`，确认能跑通。
5. 点击提交任务。
6. 等状态变成 `succeeded`。
7. 下载 Excel。

第一次跑通后，再把条数上限改成 `20`、`50` 等。

## 六、配置 LLM

如果不需要 LLM，可以跳过这一节。

在部署目录新建 `.env` 文件，内容示例：

```env
LLM_API_KEY=你的 API Key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
DEFAULT_CDP_URL=http://host.docker.internal:9222
APP_PORT=8000
```

然后重启：

```powershell
docker compose down
docker compose up -d
```

## 七、停止和重启

停止工具：

```powershell
docker compose down
```

重新启动：

```powershell
docker compose up -d
```

查看运行状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f xhs-agent
```

## 八、更新到最新版

如果是方式一，不安装 Git：

```powershell
docker compose pull
docker compose up -d
```

如果是方式二，使用 Git：

```powershell
git pull
docker compose pull
docker compose up -d
```

`data/` 和 `outputs/` 目录会保留，不会因为更新丢失。

## 九、数据保存在哪里

Docker 部署后，本地会出现两个重要目录：

```text
data/      上传文件、任务记录、运行日志
outputs/   生成的 Excel、CSV、封面图
```

团队内部使用时，建议定期备份 `outputs/`。

## 十、常见问题

### 1. 网页打不开

先看容器是否运行：

```powershell
docker compose ps
```

如果没有运行，执行：

```powershell
docker compose up -d
```

再打开：

```text
http://127.0.0.1:8000
```

### 2. Docker 镜像拉不下来

可以换成本地构建：

```powershell
git clone https://github.com/cnbatmoven/xhs-agent.git
cd xhs-agent
docker compose -f docker-compose.build.yml up -d --build
```

### 3. Chrome CDP 连不上

先确认宿主机能打开：

```text
http://127.0.0.1:9222/json/version
```

如果打不开，说明专用 Chrome 没启动成功。关闭 Chrome 后重新执行第四步。

如果宿主机能打开，但网页里仍然连不上，把网页里的 `Chrome CDP` 改成：

```text
http://host.docker.internal:9222
```

Linux 服务器可以改成宿主机内网 IP，例如：

```text
http://192.168.1.10:9222
```

### 4. 抓不到评论或粉丝

常见原因：

- 专用 Chrome 没登录小红书。
- Chrome 被关掉了。
- 小红书触发安全验证。
- 跑得太快。
- 链接失效。

建议：

1. 在专用 Chrome 里重新打开小红书确认登录。
2. 第一次只跑 1 条。
3. 抓取间隔设置为 `20` 或 `30`。
4. 遇到安全验证先暂停 10 到 30 分钟。

## 十一、给管理员的安全提醒

- 不要把 `9222` Chrome 调试端口暴露到公网。
- 不要把 `.env` 里的 API Key 发到群里。
- 不要把 `data/`、`outputs/`、`chrome-debug-profile/` 提交到 GitHub。
- 部门多人共用时，建议只在可信内网使用。
