# 架构与开发交接

## 当前实现

单仓库，frontend/React，backend/FastAPI，业务图使用 LangGraph。

1. 创建 Brief：目标、受众、演示/真实模式、导入样本、音乐候选。
2. 调研图 research → plan：REST 采样、候选音乐、可选真实封面分析，生成三个角度。
3. 将结果写入 SQLite，awaiting_angle 状态等待用户；此人审门是应用层持久化状态，而非 LangGraph interrupt。
4. 生成图 write → review → 条件修正一次：返回 Draft/Slide schema。校验参考 ID、音乐 ID、页数、重复 ID 和文字密度。
5. 局部编辑与独立插画生成，保持同一 palette。审核记录绑定具体 revision。
6. Playwright 确定性 HTML 排版 PNG，检查实际版式溢出后 ZIP 导出。

数据库 JSON 状态字段包括 Brief、Trend、Plan、selected、Draft、issues、approval、image_ids。SQLite 表级更新带 revision 条件，防止并发覆盖；事件表序号用于 SSE 重连。后台任务与前端 SSE 分离，断线不取消生成。

## 独立设计

产品以知识/工具教程、收藏目标起步，视觉为低干扰编辑风，保留来源与修改能力。热点不是装饰提示词：同一 Trend 对象供策划、文案、视觉和音乐选择，生成输出只能引用其中存在的样本/音乐 ID。

热点排序首先由 XHS 搜索提供，当前不实现统计学流量归因。去重、窗口过滤与缺失字段显式保留。导入音乐来源由用户提供，程序验证字段存在，不自动证明曲名与页面完全一致；人工审核须核验。

## 复用接口

小红书 MCP：独立运行，HTTP REST，仅允许搜索与详情两种只读调用。接口核对日期 2026-10-13。若上游响应变化，更新 providers.py 与契约测试；不把整个上游服务器的写工具暴露给模型。

模型服务：通用 chat/completions，不使用厂商 SDK；结构化 schema 使用 Pydantic，最多一次纠错。插画调用单独 images/generations，保存 PNG 原始字节并通过本项目 UUID 提供预览。图片 URL 不交给服务端任意抓取；参考封面下载只允许 HTTPS *.xhscdn.com、不跟随重定向、限制类型与大小。

## 下一步（优先级）

1. 用真实配置验证小红书搜索、详情、视觉模型与图片接口，保存脱敏响应 fixture。
2. 添加原始资料搜索/事实 claim→evidence 映射，区分结构参考与事实依据。
3. 站内音乐来源适配或用户授权数据服务；完善候选曲目版本与热度日期。
4. 图文复用更细致的视觉 token 与图片参考一致性；逐页局部文案重写。
5. durable worker + PostgreSQL checkpoint，缓存/幂等/费用预算，替换进程内后台任务。
6. 20 个真实创作任务质量评估与人工修改耗时统计；线上服务前加鉴权。

当前没有模型质量或流量效果实测，不输出爆款概率。
