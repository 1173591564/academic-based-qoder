---
name: writing-flow
description: "学术写作流程：调研 → 对比 → Related Work → BibTeX → 审稿"
---

## 触发
当用户说"帮我写论文"、"writing flow"、"写 Related Work"、"从调研到写作"时执行此流程。

## 概览
这是一个 **5 阶段** 学术写作工作流，从素材收集到可发表的 Related Work 章节：

```
Stage 1: research-survey（素材收集）
    ↓ 调研报告 + 论文列表
Stage 2: paper-compare（方法对比）
    ↓ 对比表 + 演化关系
Stage 3: related-work（撰写章节）
    ↓ LaTeX 草稿
Stage 4: bibtex-management（引用管理）
    ↓ .bib 文件
Stage 5: review-report（自审自查）
    ↓ 审稿报告 + 修改建议
```

**预计耗时**：30-50 分钟

## 执行

### Stage 1: 素材收集（research-survey）
执行 `/research-survey` 流程，收集相关论文和素材。

**执行策略**：
- 搜索范围覆盖用户指定的方向及其相关子方向
- 利用分类标签（`classify --list-tags`）发现相关论文
- 不仅搜索方法论文，也要搜索综述论文（综述是 Related Work 的重要素材）

**阶段交付物**：
- `output/drafts/survey-<topic>.md` — 调研报告
- 按子方向分组的论文列表（每组 3-5 篇代表性论文）

**交接规则**：
- 将「按子方向分组的论文列表」传递给 Stage 2
- 确保每个子方向至少有 2 篇论文用于对比
- 如果某方向论文不足，标注"需补充"，Stage 3 中简要提及即可

### Stage 2: 方法对比（paper-compare）
执行 `/paper-compare` 流程，对比各子方向的论文。

**执行策略**：
- 按子方向分组对比，而非所有论文两两对比
- 对比维度：方法类型、核心创新、适用场景、实验规模、年份
- 检查 REPLACES 关系，标注技术演化证据

**阶段交付物**：
- `output/drafts/compare-<topic>.md` — 对比报告
- 每个子方向的方法对比表

**交接规则**：
- 将「方法对比表」传递给 Stage 3，直接嵌入 Related Work
- 将演化关系（谁替代了谁）作为叙事线索

### Stage 3: 撰写 Related Work（related-work）
执行 `/related-work` 流程，撰写 LaTeX 格式的 Related Work 章节。

**执行策略**：
- 结构：按子方向分小节，每个小节内部按时间或方法演化排列
- 每个小节开头用 1 句话概括该方向的核心问题
- 引用论文时使用 `\cite{paper_id}` 格式
- 在叙事中融入 Stage 2 的对比分析（不是简单罗列）

**阶段交付物**：
- `output/drafts/related-work-<topic>.tex` — LaTeX 草稿

**交接规则**：
- 从 `.tex` 文件中提取所有 `\cite{}` 引用，传递给 Stage 4
- 记录草稿的字数和结构概览

### Stage 4: 引用管理（bibtex-management）
执行 `/bibtex-management` 流程，导出 Stage 3 引用的所有论文的 BibTeX。

**执行策略**：
- 只导出 Stage 3 中实际引用的论文（不是全库）
- 检查每条 BibTeX 的完整性（作者、年份、会议/期刊名）
- 如有缺失字段，用 `python -m scholar info <ULID>` 补充

**阶段交付物**：
- `output/bib/<topic>.bib` — BibTeX 文件
- 引用完整性检查报告

**交接规则**：
- BibTeX 文件路径告知用户，可直接用于 LaTeX 编译
- 如果发现有论文缺少 BibTeX 信息，记录到 Stage 5 的审查报告

### Stage 5: 自审自查（review-report）
对 Stage 3 产出的 Related Work 执行 `/review-report` 流程（审稿模式）。

**执行策略**：
- 以审稿人视角审查 Related Work 章节
- 检查维度：覆盖完整性（是否遗漏重要论文）、叙事连贯性、引用准确性、分析深度
- 对比 Stage 1 调研报告，确认没有遗漏关键子方向

**阶段交付物**：
- `output/notes/review-related-work-<topic>.md` — 审查报告
- 包含：优点、问题列表、修改建议、总体评价

## 最终产出摘要

| 文件 | 内容 | 用途 |
|------|------|------|
| `output/drafts/survey-<topic>.md` | 调研报告 | 素材基础 |
| `output/drafts/compare-<topic>.md` | 对比报告 | 分析支撑 |
| `output/drafts/related-work-<topic>.tex` | Related Work 章节 | **核心产出**，直接嵌入论文 |
| `output/bib/<topic>.bib` | BibTeX | 引用管理 |
| `output/notes/review-related-work-<topic>.md` | 审查报告 | 质量保证 |

## 注意事项
- Related Work 的核心价值是**叙事**而非**罗列**——每个小节要有分析性的过渡和总结
- Stage 5 审查后，根据修改建议更新 `.tex` 文件
- 如果用户有特定的论文模板（如 ACL/CVPR 格式），在 Stage 3 开始前告知
- 最终 `.tex` 文件确保可以用 `pdflatex` 直接编译（含完整的 `\documentclass` 和 `\bibliography`）
