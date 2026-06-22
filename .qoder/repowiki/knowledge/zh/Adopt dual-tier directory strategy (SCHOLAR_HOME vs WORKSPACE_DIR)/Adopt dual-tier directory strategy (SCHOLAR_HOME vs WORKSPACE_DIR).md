---
kind: design
name: Adopt dual-tier directory strategy (SCHOLAR_HOME vs WORKSPACE_DIR)
source: session
category: adr
---

# Adopt dual-tier directory strategy (SCHOLAR_HOME vs WORKSPACE_DIR)

_来源：71a964c → 6588a21 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
The application needs to support both a global shared knowledge base (parsed papers, ~50MB) and isolated per-project workspaces (drafts, notes, logs). Previously, all outputs were tied to PROJECT_ROOT, causing deployment inconsistencies between the CLI and MCP server and preventing clean project isolation without duplicating large shared datasets.

## 决策驱动
- Avoid duplication of large shared KB (parsed/)
- Project-level isolation for user-generated content
- Backward compatibility with existing dev mode

## 备选方案
- **Windows junction/symlink for parsed/** _（已否决）_ — 优点：Keeps a single physical location while appearing in workspace；缺点：Over-engineered; complex cross-platform handling; unnecessary since code can read from global path directly
- **Full copy of all data per workspace** _（已否决）_ — 优点：Complete isolation；缺点：Wastes disk space (50MB+ per project); slow initialization
- **Dual-tier path resolution (SCHOLAR_HOME + WORKSPACE_DIR)** — 优点：Shared KB remains global; drafts/notes/logs are per-project; zero behavior change in dev mode；缺点：Slightly more complex path logic in config

## 决策
Split paths into two tiers: SCHOLAR_HOME for shared resources (data/papers, output/parsed, bib, experiments) and WORKSPACE_DIR (resolved from env var or cwd) for per-project outputs (drafts, notes, logs). Introduced init_workspace() to scaffold the workspace structure.

## 影响
CLI and MCP server now share consistent path resolution via scholar.config. MCP server no longer reads from source directory incorrectly. Dev mode remains unchanged (WORKSPACE_DIR == SCHOLAR_HOME).