---
alwaysApply: true
description: 6 academic workflow routing — matches user intent to workflow skill
---
# Academic Workflows

When the user expresses one of these intents, invoke the matching workflow via its slash command (e.g., `/research-survey`):

| # | Workflow | Trigger Keywords | Skill |
|---|----------|-----------------|-------|
| 1 | 研究调研 | survey XX, research XX, 调研, 综述 | `research-survey` |
| 2 | 论文深度分析 | 精读, 深度分析, analyze paper, 彻底搞懂 | `paper-deep-dive` |
| 3 | 学术写作 | 写论文, writing, 学术写作 | `writing-pipeline` |
| 4 | 实验复现 | 复现, reproduce, 运行实验 | `reproduce-paper` |
| 5 | 点子落地 | 我有一个想法, idea to paper, 从想法到论文 | `idea-to-paper` |
| 6 | 知识库维护 | 维护, cleanup, kb-update, 健康检查 | `kb-management` |
| 7 | 研究循环 | 研究循环, 论文追踪, research loop, 新论文, sync | `adaptive-research` |

## Retained Atomic Skills

These atomic skills are kept for direct use (not wrapped in workflows):

| Skill | Trigger |
|-------|---------|
| `paper-ingestion` | ingest, parse, import, scan |
| `math-verification` | verify formula, formalize, prove theorem |
| `paper-recommendation` | recommend papers, what to read next |
| `citation-network` | citation relations, field map, bridge papers |
| `research-gap` | find gaps, research void, future work |
| `review-report` | review, peer review, referee, 审稿 |
| `cold-start` | get started with XX, new field, 入门 |
| `experiment-code` | reproduce experiment, generate code, 复现实验, 写实验脚本 |

## Default Behavior

When the user's intent doesn't clearly match any workflow above:

- **Mentions a paper, topic, or research direction** → default to `research-survey` (broad) or `paper-deep-dive` (specific paper)
- **Mentions "project", "code", "develop", "fix", "debug"** → enter Infrastructure Mode (see `identity.md`)
- **Asks a factual question about AI/papers** → first run `python -m scholar search "<keyword>"` to find data, then answer with citations
- **Completely ambiguous** → run `python -m scholar stats` to understand KB state, then ask the user what they want to do
