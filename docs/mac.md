# Mac 本地运行（百炼预设）

## 一条启动命令

```bash
git clone https://github.com/xhy2539/notepilot.git
cd notepilot
bash scripts/start-mac.sh
```

已拉过仓库则在 notepilot 目录执行 `git pull --ff-only`，再运行启动命令。

也可在 Finder 中打开 `Start-NotePilot.command`。若系统阻止脚本，直接使用终端命令；不要关闭系统安全机制。

启动脚本会：
1. 下载项目专用 uv，并在需要时准备 Python 3.12 与 .venv。
2. 安装固定版本的后端依赖、Playwright Chromium。
3. 复用 Node 20+；若未安装则下载官方 Node 22 Mac 包并校验 SHA256，不修改系统 Node。
4. 安装前端和中文字体，构建完整本地 UI。
5. 创建 backend/.env，终端隐藏输入百炼 Key；回车跳过则可先看离线演示。
6. Apple Silicon 自动下载经 SHA256 校验的 xiaohongshu-mcp v2.5.5，绑定本机 18060；首次会下载其浏览器。
7. 启动完整 FastAPI 服务并自动打开 http://127.0.0.1:8000 。

首次需联网下载依赖，耗时取决于网络，不能离线完成首次安装。不要求 Homebrew、Docker 或 Go。后续启动会复用已下载环境，但仍检查依赖。运行中保持终端打开；Ctrl+C 清理本次启动的进程，不关闭已有外部服务。

## 真实体验

第一次启动在终端输入北京地域百炼 Key。Key 不显示在终端，也不上传 Git。默认一份 Key 用于文案、看图与图片生成。

打开工作台后：
1. 看顶部“文本模型 / 生图 / 小红书”配置状态；“已配置”不等于已通过付费接口实测。
2. 点击“小红书扫码登录”，用手机小红书 App 扫码。首次浏览器下载时可稍后重试。
3. 选择“真实调研与生成”，输入意图并开始策划。
4. 选择创作方向，查看草稿；点击“为这一页生成 AI 插画”使用百炼真实生图。
5. 编辑、保存、人工核对事实，再审核和下载图文发布包。

扫码登录需你本人完成，不能预先写进 Git。小红书是否能取到样本取决于账号、服务和当时平台；未取到时可导入实际参考样本，不会伪造热门数据。不要将 Key、二维码、Cookie 或含签名的图片 URL 发到公开 Issue。

## 配置说明

`backend/.env` 由首次启动创建，不在 GitHub 中。文件权限设为仅当前用户可读写。

```env
DASHSCOPE_API_KEY=只在本地填写
LLM_PROVIDER=bailian
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
VISION_MODEL=qwen-vl-plus
IMAGE_PROVIDER=bailian
IMAGE_MODEL=qwen-image-2.1-turbo
```

模型、API Key 与 URL 必须同地域。百炼官方也支持业务空间专属地址，例如 `https://你的业务空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`，可在首次向导填写；这是实际控制台 ID，不是仓库中固定字符串。

图片服务默认复用文本服务地址和 Key。需要独立配置时填 IMAGE_BASE_URL/IMAGE_API_KEY。其他服务需改 LLM_PROVIDER/IMAGE_PROVIDER 为 openai，并填对应字段。

已有 Key 想重配：`bash scripts/start-mac.sh --configure`；或编辑 backend/.env 后重启。脚本保留已有配置，更新代码不会覆盖 Key。

## BGM 当前边界

小红书上游没有可依赖的音乐元数据字段。现在可导入真实音乐候选，或配置已获权限的抖音音乐榜 token；抖音榜只是跨平台参考。不会自动保证拿到“小红书热门 BGM”，也不自动下载音乐。发布时核对平台曲库和版本。

## 常见问题

- 下载失败：重新运行启动命令；需能访问 astral.sh、GitHub、PyPI、Node 官网、npm 和浏览器下载源。不要用替换未知下载地址的方式处理校验失败。
- 8000 被占用：关闭之前运行的 NotePilot 终端，或访问已经运行的工作台。
- 18060 已有服务：脚本不重复启动。让 backend/.env 的 XHS_API_TOKEN 与已有服务 AUTH_TOKEN 一致；无 Token 的外部服务将 XHS_API_TOKEN 留空。
- 小红书未就绪：查看 `.tools/logs/xhs.log`，首次需下载浏览器；等待完成再扫码。
- 百炼 HTTP 401/403：检查 Key、地域和模型权限；429 检查额度/限流。Key 不要贴到错误反馈里。
- 生图超时：原文案保留。确认控制台模型可用；上游调用可能已计费，重试前先查看百炼调用记录。
- Intel Mac：完整 UI/百炼可运行；固定上游 release 仅提供 Mac arm64 小红书二进制。可自行安装 Docker 后按上游文档运行小红书服务，再配置 XHS_BASE_URL/Token；或直接导入参考样本。M 系列 Mac 使用自动路径。
- 双击脚本没有执行权限：在仓库目录运行 `bash scripts/start-mac.sh`。

## 验证范围

已进行百炼请求/URL 下载契约测试、Key 不转发到图片存储测试、登录代理测试、配置文件保护测试、脚本语法检查、前端构建和本地完整链路测试。当前执行环境是 Linux，不能声称已在真实 M5 Mac 上安装运行；也没有你的百炼 Key/小红书账号，付费调用与本人扫码需要在你的机器上完成。

资料：
- 百炼图像接口：https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference
- uv 安装：https://docs.astral.sh/uv/getting-started/installation/
- 上游小红书 release：https://github.com/xpzouying/xiaohongshu-mcp/releases/tag/v2.5.5
