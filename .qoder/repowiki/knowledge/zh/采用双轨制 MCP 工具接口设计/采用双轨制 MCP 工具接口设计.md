---
kind: design
name: 采用双轨制 MCP 工具接口设计
source: session
category: adr
---

# 采用双轨制 MCP 工具接口设计

_来源：7729a25 → 7877e84 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
桌面端（Shell）需要结构化 JSON 数据以渲染引用网络、雷达图等学术视图，而外部 IDE（Brain/Agent）依赖文本输出进行推理。现有的单一文本返回模式导致桌面端无法可视化，而统一改为 JSON 会破坏 Agent 的推理体验。

## 决策驱动
- 桌面端可视化需求
- Agent 推理稳定性
- 架构解耦

## 备选方案
- **现有 MCP 工具统一改为 JSON 返回** _（已否决）_ — 优点：接口统一，简化后端逻辑；缺点：破坏 Agent 已习惯的文本输出格式，严重影响推理质量
- **双轨制：保留文本工具 + 新增 scholar_get_* 结构化工具** — 优点：Agent 继续使用文本工具保持推理能力；桌面端通过专用结构化工具获取 {nodes, edges} 等数据进行渲染；缺点：MCP 工具数量增加，需在文档中明确区分用途以防混淆

## 决策
在 scholar_mcp/server.py 中新增以 scholar_get_ 为前缀的结构化工具（如 scholar_get_citation_graph），返回严格 schema 约束的 JSON；保留原有文本工具供 Agent 使用。

## 影响
桌面端可实现引用网络图谱和质量雷达图渲染；需通过命名规范和 tools.md 文档明确区分两类工具的受众，防止 Agent 误调用结构化工具导致上下文膨胀。