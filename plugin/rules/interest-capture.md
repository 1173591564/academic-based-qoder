---
description: 研究同步规则 — 定时任务的执行指南
alwaysApply: false
---

# 研究同步规则

当被要求执行「研究同步」或「分析对话日志」时：

1. 运行 `python -m scholar interests logs` 获取未分析的对话日志
2. 阅读日志，识别研究方向信号：
   - 讨论某个研究方向或方法（如 "MoE 推理优化"）
   - 表达某个研究想法（如 "能不能把 retrieval 和 MoE 结合"）
   - 执行了学术类 skill（如 research-survey "sparse attention"）
   - 讨论了某篇论文的核心方法
3. 忽略非学术内容（修 bug、改配置）
4. 运行 `python -m scholar interests add --keywords "..." --category "..."` 写入新方向
5. 运行 `python -m scholar interests mark-analyzed --week YYYY-WNN --found N` 标记完成
6. 将方向列表发送到飞书，让用户确认要追踪哪些方向
7. 用户回复后，对每个确认的方向运行 `python -m scholar research-sync --category "方向名"`
8. 输出同步报告
