# NotePilot

面向个人创作者的小红书图文 Agent。输入意图与目标 → 调研同领域样本 → 选择创作方向 → 联合生成文案、配图方案和 BGM 选择 → 逐页编辑 → 人工审核 → 下载发布包。

首批以知识科普、工具教程为主。独立 React 工作台 + FastAPI + LangGraph；复用开源编排与采集能力，不依赖 RedInk 源码。

## 快速开始（本地）

要求 Python 3.11+、Node.js 20+。以下命令先在仓库根目录执行。

```bash
git clone https://github.com/xhy2539/notepilot.git
cd notepilot
python3 -m venv .venv
source .venv/bin/activate
pip install -e './backend[test]'
python -m playwright install chromium
cd frontend
npm ci
npm run build
cd ../backend
cp ../.env.example .env
uvicorn notepilot.app:app --env-file .env --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。默认离线演示无需 Key。演示样本和文案明确标注为示例，不是实时热门数据；演示不编造歌曲、互动数或参考链接。

Windows：使用 `python -m venv .venv`，随后 `.venv\Scripts\Activate.ps1`；复制配置用 `Copy-Item .env.example backend/.env`，其余 Python/npm 命令相同。先在根目录安装后端，再进入 frontend 构建，最后在 backend 启动。

开发时可单独运行 frontend 的 `npm run dev`（127.0.0.1:5173，代理 /api 到 8000）。前端构建字体通过 @fontsource/noto-sans-sc 提供；PNG 渲染也读取该字体依赖，所以仅跑后端时也需先执行 frontend 的 npm ci。

## 真实生成

在 **backend/.env** 配置，重启后端。不要把 Key 发到聊天或提交 Git。

| 环境变量 | 用途 |
|---|---|
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | 支持 chat/completions 的模型服务，返回结构化 JSON |
| XHS_BASE_URL | 已运行并登录的 xiaohongshu-mcp REST 服务地址 |
| VISION_MODEL | 可选，与文本同服务/Key，支持图片输入；分析最多两张实际参考封面 |
| IMAGE_BASE_URL / IMAGE_API_KEY / IMAGE_MODEL | 可选 images/generations 接口；首版要求 b64_json PNG，1024×1024 |
| DOUYIN_CLIENT_TOKEN | 可选抖音官方音乐飙升榜 token，须已获得 data.external.billboard_music 权限 |

模型名称由你选择，不绑定某个厂商。兼容网关对 JSON、视觉、图片响应的支持不同，需使用该服务真实支持的模型与端点。图片接口不支持 b64_json 或指定尺寸时会显示失败，原稿保留。

### 小红书采集复用

使用 [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) 的独立服务。按上游文档安装、启动并完成你自己的扫码登录；NotePilot **只调用**：

- `POST /api/v1/feeds/search`：最多 2 个关键词 × 最多收藏/最新两种排序，时间一周内。
- `POST /api/v1/feeds/detail`：最多深读 4 条，提取正文、日期和评论需求。

不调用发布、点赞、收藏、评论。应用没有收集登录 Cookie 的接口。服务暂不可用时可以导入样本，结果会标记覆盖不完整。上游模型当前未提供可靠音乐字段，所以不宣称能自动取得每篇笔记的 BGM。

### 热门音乐与参考样本导入

首页展开 JSON 导入框，格式如下。此处只是字段演示；请替换为实际链接、日期与数据。

```json
{
  "samples": [{
    "id": "reference-1",
    "title": "参考笔记的真实标题",
    "text": "你取得的正文内容",
    "url": "https://www.xiaohongshu.com/explore/实际笔记ID",
    "published_at": "2026-10-13T10:00:00+08:00",
    "saves": 120,
    "likes": 300,
    "questions": ["实际评论中的读者问题"]
  }],
  "music": [{
    "id": "music-1",
    "title": "实际曲名",
    "artist": "实际艺人",
    "version": "实际版本",
    "platform": "xiaohongshu",
    "source_url": "https://www.xiaohongshu.com/实际音乐或笔记页面",
    "mood": "你观察到的情绪风格",
    "availability": "unknown"
  }]
}
```

缺失数字填 null 或省略，不能猜。音乐导入链接不会自动下载音频；真实模型仅从给定候选选择。可接官方抖音飙升榜，但在界面清晰标为跨平台参考，发布时仍需核对小红书曲库和版本。榜单获取不代表音频授权。

## 已实现

- 近期样本采集/导入，数据覆盖与缺口提示。
- 三个原创角度与参考 ID；人工选方向后生成。
- LangGraph 状态图、文案/音乐/视觉联合规划、结构质检与最多一次修正。
- 三套可编辑视觉风格；自有排版与装饰，选中页可调用图片服务生成插画。
- 页面文字、发布正文、配图描述与音乐选择编辑；修改不会重生成整组图片。
- SQLite 持久化作品与阶段事件、SSE 进度、显式取消、重启中断标记。
- 乐观版本校验；编辑使旧审核失效；导出只接受已审核当前版本。
- 1080×1440 PNG 与 caption.md、sources.json、music.md、project.json ZIP 导出。
- 无 Key 的完整离线演示。

## 当前边界

这是本地单用户 MVP，不要直接开放公网。默认服务绑定 loopback，并校验 Host/浏览器 Origin；多用户权限、共享数据隔离与线上鉴权尚未实现。

事实核验目前由用户审核：平台样本不是权威证据；首版没有联网搜索原始文档的独立事实核查工具。不要把草稿里的待核实内容直接发布。参考图片只做可选视觉分析，不直接搬运。

作品和事件会持久化，但运行时任务在进程内。重启后标记 interrupted，重试会重新运行当前阶段，**不是 checkpoint 恢复**；上游已收费调用不保证幂等，图片响应不明时也无法保证不重复计费。每个作品成功生成插画上限 12 张；失败调用费用仍由上游决定。

没有自动发布、自动音频下载、音频内容识别、全站热度排行、长期记忆或发布后增长归因。视觉分析只有启用 VISION_MODEL 并实际读到封面才显示已完成。实时外部服务需要你配置后实测；仓库测试通过不表示已连接你的账号。

## 测试

```bash
cd backend
pytest -q
cd ../frontend
npm run build
```

PNG 测试需已安装 Playwright Chromium，且 frontend/npm ci 已完成。测试覆盖版本冲突、审核失效、无效样本/音乐引用、取消、来源缺失、转义、采集适配器契约和 PNG 导出。后端精确依赖快照见 requirements.lock；前端用 package-lock.json。

## 设计与复用

- [架构与后续工作](docs/architecture.md)
- [第三方依赖与许可](THIRD_PARTY_NOTICES.md)
- [原始 MVP 设计](docs/product-design.md)

代码通过依赖/独立服务复用 LangGraph 和小红书 MCP。redbook 可作为未来替代采集/渲染适配器，本版未接入。RedInk 仅调研其公开功能，未复制源代码或资产。

## Docker（可选）

先创建 backend/.env，再在仓库根目录执行 `docker compose up --build`。容器访问宿主机小红书服务时，将 XHS_BASE_URL 改为 `http://host.docker.internal:18060`。默认端口只映射本机。Docker 镜像构建未在本次环境实测。
