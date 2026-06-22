---
kind: design
name: Optimize MCP Server via direct domain calls and shared state
source: session
category: adr
---

# Optimize MCP Server via direct domain calls and shared state

_来源：71a964c → 6588a21 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
MCP tools were previously invoked via subprocess.run(), incurring ~4.7s latency per call due to Python startup and import overhead. This made interactive use sluggish. The goal was to reduce latency for frequent, fast operations while maintaining stability for long-running tasks.

## 决策驱动
- Reduce tool invocation latency (target <100ms)
- Reuse database connections and cached data across calls
- Avoid over-engineering a new service layer

## 备选方案
- **Extract full service layer (10+ new files)** _（已否决）_ — 优点：Clean separation of concerns；缺点：High refactoring cost (39 commands); over-engineering since domain modules already contain logic
- **Convert all tools to direct calls** _（已否决）_ — 优点：Maximum performance；缺点：Risk of memory leaks or blocking for long-running tasks (parsing, embedding); loss of process isolation
- **Hybrid approach: Direct calls for fast tools, subprocess for slow tools** — 优点：Best balance of performance and stability; leverages existing domain modules directly；缺点：Requires maintaining two invocation paths

## 决策
Introduce scholar/_state.py to manage shared state (PG connection pool, IDResolver cache, parsed JSON LRU cache) in the long-running MCP process. Convert 20 high-frequency tools (stats, search, info, etc.) to direct domain module calls (<100ms). Keep 18 long-running tools (parse, bootstrap, index) as subprocess calls for isolation. Modify scholar/db.py to accept an optional connection pool.

## 影响
Fast tool latency dropped from ~4.7s to <100ms. Database connections are pooled. ID resolution and parsed paper loading are cached in memory. Long-running tasks remain isolated in subprocesses to prevent blocking the main MCP thread.