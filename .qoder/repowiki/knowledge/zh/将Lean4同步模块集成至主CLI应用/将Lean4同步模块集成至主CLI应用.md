---
kind: design
name: 将Lean4同步模块集成至主CLI应用
source: session
category: adr
---

# 将Lean4同步模块集成至主CLI应用

_来源：7877e84 → 7e09e16 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
`scholar/lean_sync.py` 原本作为一个独立的 Typer 应用存在，未注册到主 CLI (`scholar/cli.py`) 中，导致 Lean4 数据库同步和模板生成功能无法通过统一命令行入口访问，破坏了工具链的一致性。

## 决策驱动
- 统一命令行入口
- 模块化架构一致性
- 功能可用性

## 备选方案
- **保持 lean_sync.py 为独立可执行脚本** _（已否决）_ — 优点：模块隔离，依赖简单；缺点：用户需要记住不同的执行方式，无法享受主CLI的参数校验和帮助文档体系
- **重构为共享 App 模式并导入主 CLI** — 优点：统一入口，复用主CLI的基础设施（如 console 输出），便于统一管理命令；缺点：需要修改模块结构，引入对 `_shared` 的依赖

## 决策
重构 `scholar/lean_sync.py`，移除内部独立的 `typer.Typer()` 实例，改为从 `scholar._shared` 导入共享的 `app` 实例，并使用 `@app.command` 装饰器注册 `lean-sync` 和 `lean-templates` 命令。在 `scholar/cli.py` 中通过 `from . import lean_sync` 隐式导入以完成命令注册。

## 影响
用户可以通过 `scholar lean-sync` 和 `scholar lean-templates` 直接访问 Lean4 相关功能。Lean4 同步模块现在依赖于主 CLI 的共享上下文，增强了模块间的耦合但提升了整体一致性。