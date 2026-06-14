---
description: 自适应研究循环：方向管理 → 自动搜索 → 全流程入库
trigger: 研究循环, 论文追踪, research loop, research sync, 新论文, /sync
---

# Adaptive Research Loop

自动追踪研究方向，定期从 arXiv 获取最新论文并全流程入库。

## 工作流步骤

### Step 1: 查看/管理研究方向
```bash
python -m scholar interests list
```
展示当前所有研究方向、关键词、搜索历史。

管理操作：
```bash
python -m scholar interests add --keywords "sparse attention, efficient transformer" --category "LLM Efficiency"
python -m scholar interests remove --category "3D Vision"
```

### Step 2: 方向级同步（搜索 + 下载 + 全流程入库）
```bash
# 同步单个方向
python -m scholar research-sync --category "LLM Efficiency" --max 10

# 同步所有方向
python -m scholar research-sync --max 10
```

每个方向自动完成：搜索 arXiv → 下载 TeX → 解析 → 图谱更新 → RAG 索引 → 阅读笔记 → 质量评分 → 分类打标签。

### Step 3: 查看同步结果
```bash
python -m scholar stats
```
确认新论文已入库，检查知识库状态。

### Step 4: 配置定时任务（Qoder Work）

在 Qoder Work 的「定时任务」中创建一个任务：

| 字段 | 内容 |
|------|------|
| 任务名称 | Scholar Studio 研究同步 |
| 计划时间 | 每周日 09:00 |
| 工作目录 | Scholar Studio 项目根目录 |

指令：
```
执行研究同步任务：
1. 运行 python -m scholar interests logs 获取未分析的对话日志
2. 阅读日志，提取研究方向信号（忽略纯技术操作）
3. 运行 python -m scholar interests list 查看已有方向，去重后写入新方向
4. 运行 python -m scholar interests mark-analyzed 标记该周完成
5. 将研究方向列表发送到飞书，让用户确认要追踪哪些方向
6. 用户回复后，对确认的每个方向运行 python -m scholar research-sync --category "方向名"
7. 输出同步报告
```

## Next Steps

- 同步完成后 → 用 `research-survey` 对某个方向做深度调研
- 发现感兴趣的论文 → 用 `paper-deep-dive` 精读
- 查看知识库健康度 → 用 `kb-management` 维护
