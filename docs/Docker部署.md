# Docker 部署

这个部署方式面向普通团队成员：只需要 Docker，不需要本机安装 Python、Node 或手动启动前端。

## 1. 启动宿主机 Chrome

Docker 容器里的后端需要连接一份已经登录小红书的 Chrome。请先在宿主机打开专用 Chrome。

Windows PowerShell：

```powershell
$PROJECT = (Get-Location).Path
$CHROME = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
if (!(Test-Path $CHROME)) { $CHROME = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe" }
& $CHROME --remote-debugging-address=0.0.0.0 --remote-debugging-port=9222 --user-data-dir="$PROJECT\chrome-debug-profile" --no-first-run --no-default-browser-check https://www.xiaohongshu.com
```

在打开的 Chrome 里登录小红书。如果要抓蒲公英报价，也在同一个 Chrome 里登录蒲公英后台。

注意：`9222` 是浏览器调试端口，不要暴露到公网。只在可信内网或本机 Docker 环境使用。

## 2. 直接拉镜像运行

项目默认镜像地址：

```text
ghcr.io/cnbatmoven/xhs-agent:latest
```

启动：

```powershell
docker compose up -d
```

打开网页：

```text
http://127.0.0.1:8000
```

停止：

```powershell
docker compose down
```

## 3. 配置 LLM

如果要启用 LLM，先复制 `.env.example` 为 `.env`，再填写：

```env
LLM_API_KEY=你的 API Key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
```

然后重新启动：

```powershell
docker compose up -d
```

## 4. 数据目录

Docker 会把数据保存在项目目录：

```text
data/      任务记录、上传文件、日志
outputs/   导出的 Excel / CSV / 封面图
```

升级镜像时，这两个目录不会丢。

## 5. 本地构建镜像

如果你是开发者，想从当前代码构建：

```powershell
docker compose -f docker-compose.build.yml up -d --build
```

## 6. 常见问题

### Chrome CDP 连不上

确认宿主机能打开：

```text
http://127.0.0.1:9222/json/version
```

如果宿主机能打开、Docker 里连不上，请确认启动 Chrome 时带了：

```text
--remote-debugging-address=0.0.0.0
```

网页里的 Chrome CDP 默认应为：

```text
http://host.docker.internal:9222
```

### Linux 服务器部署

Linux 上 `host.docker.internal` 依赖 Docker 的 `host-gateway` 能力，`docker-compose.yml` 已经配置了：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

如果仍然无法连接，请把网页里的 Chrome CDP 改成宿主机实际内网 IP，例如：

```text
http://192.168.1.10:9222
```

### 看不到网页

确认容器健康：

```powershell
docker compose ps
docker compose logs -f xhs-agent
```

然后打开：

```text
http://127.0.0.1:8000
```
