---
name: gap-analysis-flow
description: "Gap discovery workflow: citation-network → concept-evolution → research-gap → recommendation"
---

## 触发
当用户说"找研究空白"、"gap analysis on XX"、"发现研究机会"、"这个方向还有什么可以做的"时执行此流程。

## 概览
这是一个 **4 阶段** 研究空白发现工作流：

```
Stage 1: citation-network（引用网络分析）
    ↓ 关键论文 + 桥接节点 + 引用结构
Stage 2: concept-evolution（概念演化分析）
    ↓ 替代链 + 当前主流技术 + 演化趋势
Stage 3: research-gap（研究空白发现）
    ↓ 空白列表 + 证据链 + 方向建议
Stage 4: paper-recommendation（填补空白的论文推荐）
    ↓ 推荐列表 + 与空白的对应关系
```

**预计耗时**：15-30 分钟

## 执行

### Stage 1: 引用网络分析（citation-network）
执行 `/citation-network` 流程，分析目标方向的引用网络。

**阶段交付物**：
- `output/drafts/citation-network-<topic>.md` — 引用网络分析报告
- 提取：Top 被引论文、桥接论文、子领域结构、引用断裂带

**交接规则**：
- 将「桥接论文」列表传递给 Stage 2（它们是概念演化的关键节点）
- 将「引用断裂带」标记传递给 Stage 3（可能是研究空白的信号）
- 如果 Neo4j 未启动，跳过此阶段，从 Stage 2 开始

### Stage 2: 概念演化分析（concept-evolution）
执行 `/concept-evolution` 流程，追踪核心概念的替代链。

**执行策略**：
- 优先分析 Stage 1 中桥接论文涉及的概念
- 识别 REPLACES 关系：什么技术替代了什么？什么正在被替代？
- 关注演化链的"末端"——当前最新的技术是什么？

**阶段交付物**：
- 概念演化链列表（格式：旧技术 → 过渡技术 → 当前主流）
- 标注每个概念的活跃年份和代表性论文

**交接规则**：
- 「当前主流技术」传递给 Stage 3，分析其局限性
- 「演化链末端」是寻找空白的最佳切入点

### Stage 3: 研究空白发现（research-gap）
执行 `/research-gap` 流程，综合 Stage 1-2 的证据发现空白。

**执行策略**：
- 从引用断裂带（Stage 1）寻找"没人连接"的子领域
- 从概念演化末端（Stage 2）寻找"当前方法的未解决问题"
- 交叉验证：空白是否有论文证据支撑（不能凭空臆想）

**阶段交付物**：
- `output/drafts/research-gap-<topic>.md` — 研究空白报告
- 每个空白包含：描述、证据（哪些论文提到了相关问题）、可能的方向

**交接规则**：
- 将空白列表中的「可能方向」传递给 Stage 4
- 优先级排序：证据最充分 × 当前最热门 × 可行性最高

### Stage 4: 论文推荐（paper-recommendation）
执行 `/paper-recommendation` 流程，推荐可能填补空白的论文。

**执行策略**：
- 针对每个研究空白，搜索可能相关的论文（本地库 + arXiv）
- 区分：本地库已有（可直接阅读）vs 库外（需要下载）
- 为每篇推荐论文标注它对应哪个研究空白

**阶段交付物**：
- 推荐论文列表，按与空白的关联度排序
- 每篇论文包含：ULID/标题、对应空白、推荐理由

## 最终产出摘要

| 文件 | 内容 | 用途 |
|------|------|------|
| `output/drafts/citation-network-<topic>.md` | 引用网络 | 理解领域结构 |
| 概念演化链（内存中） | 替代关系 | 理解技术趋势 |
| `output/drafts/research-gap-<topic>.md` | 研究空白 | 发现研究方向 |
| 推荐论文列表 | 填补空白 | 指导下一篇读什么 |

## 注意事项
- 研究空白的发现质量取决于知识库覆盖度——如果某方向论文很少，空白可能只是"我们库里没有"
- Stage 1 需要 Neo4j，如果未启动则从 Stage 2 开始，用 `graph-query` 替代
- 最终推荐时明确区分"库内论文"和"库外论文"，库外的提供 arXiv 链接
- 每个阶段之间向用户展示中间结果，确认方向是否匹配预期
