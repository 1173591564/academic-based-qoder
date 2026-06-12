---
description: Academic research principles and writing standards
globs:
  - "output/drafts/**"
  - "output/notes/**"
  - "output/bib/**"
  - "output/parsed/**"
alwaysApply: false
---

# Academic Research Principles

## Core Rules

1. **Data-driven**: Always retrieve information from parsed paper data first. Never fabricate citations or facts.
2. **Citation accuracy**: Use paper_id format (e.g., "Attention_Is_All_You_Need") for all references. Verify each citation exists in the knowledge base before citing.
3. **Formula precision**: Extract LaTeX from the `formulas` field of parsed JSON. Do not re-type formulas from memory.
4. **Academic writing**: Use natbib format (`\cite{key}`) in LaTeX output. All generated content goes to `output/drafts/`.
5. **Incremental operations**: Process papers one-by-one in batch operations. Report progress. Failures should not block the whole batch.
6. **Lean4 integration**: When verifying formulas, reference formal definitions in `LEAN/AiEvolution/`.
7. **Output convention**: All generated artifacts (notes, reports, code, BibTeX) go into `output/` directory.

## Writing Style

- Use formal academic English or Chinese (match user's language)
- Every claim must be backed by a specific paper or data point
- Tables and structured comparisons are preferred over prose for multi-paper analysis
- Always include a references section listing paper_ids
