# XHS 数据抓取 Agent · 前端

基于 Vite + React 18 的可启动部署项目。

## 启动

```bash
cd app
npm install
npm run dev          # 开发模式 → http://localhost:5173
```

## 构建 & 部署

```bash
npm run build        # 产物输出到 dist/
npm run preview      # 本地预览构建产物 → http://localhost:4173
```

把 `dist/` 目录扔到任意静态服务器即可（Nginx / Vercel / Netlify / OSS / S3）。

## 目录

```
app/
├── index.html              入口 HTML
├── package.json
├── vite.config.js
└── src/
    ├── main.jsx            React 挂载
    ├── App.jsx             三栏主界面（历史 / 对话 / 预览）
    ├── tokens.js           设计令牌（颜色 / 字体）
    ├── mock.js             Mock 数据（笔记 / 缩略图 / JSON）
    ├── ui.jsx              通用组件 & 图标
    └── styles.css          全局样式
```

## 接入真实后端

`src/App.jsx` 中所有数据来自 `src/mock.js`，把对应数组替换为 `fetch('/api/...')` 即可：

- 笔记列表 → `MOCK_NOTES`
- 缩略图墙 → `MOCK_GRID`
- 单条 JSON 详情 → `JSON_SAMPLE`
- 图表数据 → `MOCK_CHART`

发送按钮位于 Composer 底部，将 `input` state 提交到后端 agent，逐步推送步骤事件回前端，渲染到 `<Steps>` 即可。
