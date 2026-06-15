---
description: 研究方向同步 — 搜索 arXiv + 全流程入库
---

执行研究方向同步：

1. 运行 `python -m scholar interests list` 查看当前方向
2. 运行 `python -m scholar research-sync --max 10` 同步所有方向
3. 运行 `python -m scholar stats` 确认入库结果
4. 展示同步报告 `output/digests/sync-*.md`
