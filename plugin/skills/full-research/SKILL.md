---
name: full-research
description: "完整研究流程：调研 → 精读 → 对比 → 写 Related Work"
---

## 触发
当用户说"全面调研 XX"、"full research on XX"、"帮我系统研究 XX"时执行此流程。

## 概览
这是一个 **4 阶段** 组合工作流，覆盖从调研到写作的完整研究链路：

```
Stage 1: research-survey（发现论文）
    ↓ 关键论文列表 + 调研报告
Stage 2: deep-read（精读 Top 5）
    ↓ 5 份结构化阅读笔记
Stage 3: paper-compare（方法对比）
    ↓ 对比报告
Stage 4: related-work（撰写 Related Work）
    ↓ LaTeX 草稿 + BibTeX
```

**预计耗时**：30-60 分钟（取决于论文数量和解析状态）

## 执行

### Stage 1: 调研（research-survey）
执行 `/research-survey` 流程，产出调研报告。

**阶段交付物**：
- `output/drafts/survey-<topic>.md` — 调研报告
- 识别出 Top 5-10 关键论文（按被引次数、质量评分、概念中心度排序）

**交接规则**：
- 从调研报告的「关键论文详析」中提取论文 ULID 列表
- 按质量评分（如有）降序排列，取 Top 5
- 如果某论文没有预生成笔记（`output/notes/<ULID>.md`），标记为需要在 Stage 2 全量读取

### Stage 2: 精读（deep-read）
对 Stage 1 选出的 Top 5 论文，逐一执行 `/deep-read` 流程。

**执行策略**：
- 先检查 `output/notes/<ULID>.md` 是否已有笔记，有的话快速跳过
- 对没有笔记的论文做全文结构化阅读
- 每篇产出结构化笔记后，提取「核心贡献」和「关键公式」

**阶段交付物**：
- 5 份 `output/notes/<ULID>.md` — 结构化阅读笔记

**交接规则**：
- 汇总 5 份笔记中的「核心贡献」和「关键公式」
- 构建对比矩阵：论文 × 维度（方法类型、核心创新、关键技术、实验规模）

### Stage 3: 对比（paper-compare）
对 Stage 2 精读的论文执行 `/paper-compare` 流程。

**执行策略**：
- 使用 Stage 2 汇总的对比矩阵作为起点
- 重点分析：方法差异、演化关系、各自适用场景
- 检查 REPLACES 关系（概念演化证据）

**阶段交付物**：
- `output/drafts/compare-<topic>.md` — 对比报告

**交接规则**：
- 从对比报告中提取方法对比表
- 记录每篇论文的 ULID 和核心区别点

### Stage 4: 撰写 Related Work（related-work）
基于 Stage 1-3 的全部产出，执行 `/related-work` 流程。

**执行策略**：
- 以调研报告的「研究脉络」为叙事骨架
- 以对比报告的「方法对比表」为分析支撑
- 以精读笔记的「核心贡献」为引用素材
- 产出 LaTeX 格式的 Related Work 章节

**阶段交付物**：
- `output/drafts/related-work-<topic>.tex` — LaTeX 草稿
- `output/bib/<topic>.bib` — BibTeX 引用文件

## 最终产出摘要

| 文件 | 内容 | 用途 |
|------|------|------|
| `output/drafts/survey-<topic>.md` | 调研报告 | 领域全景了解 |
| `output/notes/<ULID>.md` × 5 | 精读笔记 | 单篇深度理解 |
| `output/drafts/compare-<topic>.md` | 对比报告 | 方法差异分析 |
| `output/drafts/related-work-<topic>.tex` | Related Work | 直接嵌入论文 |
| `output/bib/<topic>.bib` | BibTeX | 引用管理 |

## 注意事项
- 每个阶段之间，明确告知用户当前进度和下一步计划
- 如果某阶段执行失败（如 Neo4j 未启动），跳过并标注原因，不要中断整个流程
- 用户可以在任何阶段说"先到这里"，已完成的阶段产出仍然有效
- 如果论文数量很多（>10 篇），建议用户分批处理，先做 Top 5
