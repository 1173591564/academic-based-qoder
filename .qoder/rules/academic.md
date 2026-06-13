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

## Iterative Writing Protocol

When writing any file in `output/drafts/` or `output/notes/`:

1. **Check existing artifacts first**: Before generating any draft, scan for intermediate files (`*-outline.md`, `*-review.md`, existing sections in the target file). If an outline exists, follow it. Never overwrite existing content without reviewing it first.
2. **Cite-then-write**: After writing each section, verify all cited paper_ids exist in the knowledge base before moving to the next section.
3. **Quality gate is mandatory**: After completing a draft, generate a `-review.md` with `[PASS]`/`[REVISE]`/`[MISSING]` markers. Never skip this step.
4. **Bounded revision**: Max 2 revision rounds based on review feedback. After that, finalize. No infinite loops.
5. **Resume awareness**: If a previous session's outline or partial draft exists, continue from where it left off rather than starting over.

## Writing Style

- Use formal academic English or Chinese (match user's language)
- Every claim must be backed by a specific paper or data point
- Tables and structured comparisons are preferred over prose for multi-paper analysis
- Always include a references section listing paper_ids
