---
name: paper-analysis-flow
description: "Deep analysis workflow: deep-read → quality-check → formula-derivation → experiment-code"
---

## 触发
当用户说"深度分析 XX 论文"、"analyze XX in depth"、"彻底搞懂 XX"时执行此流程。

## 概览
这是一个 **4 阶段** 论文深度分析工作流，从阅读到代码复现的完整链路：

```
Stage 1: deep-read（精读论文）
    ↓ 结构化笔记 + 核心公式列表
Stage 2: quality-check（质量评分）
    ↓ 7 维度评分卡 + 总评
Stage 3: formula-derivation（公式推导）
    ↓ 逐步推导过程 + 验证结果
Stage 4: experiment-code（实验复现）
    ↓ PyTorch 代码 + 运行说明
```

**预计耗时**：20-40 分钟

## 执行

### Stage 1: 精读（deep-read）
执行 `/deep-read` 流程，产出结构化阅读笔记。

**阶段交付物**：
- `output/notes/<ULID>.md` — 结构化阅读笔记
- 从笔记中提取：核心公式列表（LaTeX）、关键假设、方法论描述

**交接规则**：
- 将「关键公式」列表传递给 Stage 3（公式推导）
- 将「方法论描述」传递给 Stage 4（实验代码）
- 如果笔记中已有质量评分（`output/notes/<ULID>-quality.json`），跳过 Stage 2

### Stage 2: 质量评分（quality-check）
执行 `/quality-check` 流程，对论文做 7 维度评分。

**执行策略**：
- 利用 Stage 1 的精读笔记加速评分（不用重新读论文）
- 重点关注「方法论原创性」和「实验充分性」两个维度

**阶段交付物**：
- `output/notes/<ULID>-quality.json` — 7 维度评分卡
- 总评等级（A/B/C/D/F）

**交接规则**：
- 如果评分为 D 或 F，在 Stage 3-4 之前提醒用户："这篇论文质量较低，是否继续深度分析？"
- 评分中的「方法论原创性」分数影响 Stage 3 的推导策略（高分=值得深入推导）

### Stage 3: 公式推导（formula-derivation）
对 Stage 1 提取的核心公式执行 `/formula-derivation` 流程。

**执行策略**：
- 优先推导论文中声明为"核心贡献"的公式
- 对每个公式做逐步推导，检查量纲一致性
- 如果推导中发现论文公式有误，明确标注并给出修正

**阶段交付物**：
- 公式推导过程文档
- 标注：已验证 ✓ / 存疑 ? / 论文笔误 ✗

**交接规则**：
- 将「已验证的核心公式」及其符号定义传递给 Stage 4
- 如果推导失败，Stage 4 对应部分的代码要标注"公式待确认"

### Stage 4: 实验复现（experiment-code）
基于 Stage 1 的方法论和 Stage 3 的公式，执行 `/experiment-code` 流程。

**执行策略**：
- 从 Stage 1 笔记中提取实验设置（数据集、超参数、评估指标）
- 将 Stage 3 验证的公式直接翻译为 PyTorch 代码
- 每个关键公式对应代码中的一个函数，并注释论文中的公式编号
- 生成可运行的代码框架（含 `main()` 和示例输入）

**阶段交付物**：
- `output/experiments/<paper_id>.py` — PyTorch 实验代码
- 代码中的每个函数注释对应的论文公式编号

## 最终产出摘要

| 文件 | 内容 | 用途 |
|------|------|------|
| `output/notes/<ULID>.md` | 精读笔记 | 论文深度理解 |
| `output/notes/<ULID>-quality.json` | 质量评分 | 可靠性判断 |
| 公式推导文档（内存中） | 逐步推导 | 数学验证 |
| `output/experiments/<paper_id>.py` | 实验代码 | 方法复现 |

## 注意事项
- 如果论文涉及需要特定硬件（GPU 集群）的实验，Stage 4 生成缩小版本的代码
- 公式推导可能耗时很长，如果公式太多（>10 个），先做最重要的 3 个
- Stage 2 评分低不意味着跳过后续阶段——低质量论文的方法也可能有参考价值
- 每个阶段完成后向用户汇报关键发现，决定是否调整后续重点
