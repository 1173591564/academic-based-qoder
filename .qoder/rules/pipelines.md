---
alwaysApply: true
description: 18 academic pipeline routing — matches user intent to skill
---
# Academic Pipelines

When the user expresses one of these intents, invoke the matching skill via its slash command (e.g., `/research-survey`):

| # | Pipeline | Trigger Keywords | Skill |
|---|----------|-----------------|-------|
| 1 | Paper Ingestion | ingest, parse, import, scan | `paper-ingestion` |
| 2 | Math Verification | verify formula, formalize, prove theorem | `math-verification` |
| 3 | Smart Survey | survey XX, research XX, 调研, 综述 | `research-survey` |
| 4 | Deep Reading | analyze paper, deep read, 精读, 分析 | `deep-read` |
| 5 | Paper Comparison | compare papers, diff XX and YY, 对比 | `paper-compare` |
| 6 | Paper Recommendation | recommend papers, what to read next | `paper-recommendation` |
| 7 | Related Work | write related work, literature review, 相关工作 | `related-work` |
| 8 | Citation Network | citation relations, field map, bridge papers | `citation-network` |
| 9 | Research Gap | find gaps, research void, future work | `research-gap` |
| 10 | Formula Derivation | derive formula, expand derivation | `formula-derivation` |
| 11 | Quality Check | check quality, is it reliable | `quality-check` |
| 12 | KB Maintenance | maintain, cleanup, health check | `kb-maintenance` |
| 13 | Reading Progress | reading progress, what have I read | `reading-progress` |
| 14 | Review Report | review, peer review, referee, 审稿 | `review-report` |
| 15 | Experiment Code | reproduce experiment, generate code | `experiment-code` |
| 16 | BibTeX Management | export bibtex, manage references | `bibtex-management` |
| 17 | Concept Evolution | concept evolution, tech replacement, 概念演化 | `concept-evolution` |
| 18 | Cold Start | get started with XX, new field, 入门 | `cold-start` |

Skills are in `.qoder/skills/<name>/SKILL.md`. Execute via slash command or read the SKILL.md for step-by-step instructions.

## Default Behavior

When the user's intent doesn't clearly match any pipeline above:

- **Mentions a paper, topic, or research direction** → default to `research-survey` (broad) or `deep-read` (specific paper)
- **Mentions "project", "code", "develop", "fix", "debug"** → enter Infrastructure Mode (see `identity.md`)
- **Asks a factual question about AI/papers** → first run `python -m scholar search "<keyword>"` to find data, then answer with citations
- **Completely ambiguous** → run `python -m scholar stats` to understand KB state, then ask the user what they want to do
