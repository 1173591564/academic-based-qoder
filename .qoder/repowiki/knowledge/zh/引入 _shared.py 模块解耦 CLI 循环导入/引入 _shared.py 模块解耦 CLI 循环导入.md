---
kind: design
name: 引入 _shared.py 模块解耦 CLI 循环导入
source: session
category: adr
---

# 引入 _shared.py 模块解耦 CLI 循环导入

_来源：bc6e785 → 71a964c 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
`scholar/cli.py` 与 `commands/*.py` 之间存在双向依赖：`cli.py` 定义全局对象（app, console, parser）并被命令模块导入，同时 `cli.py` 又导入所有命令模块以注册路由。这种模式导致脆弱的 import 顺序依赖，阻碍了代码的模块化扩展。

## 决策驱动
- 消除循环导入
- 明确模块依赖方向
- 简化入口文件职责

## 备选方案
- **维持现状（依赖 import 顺序）** _（已否决）_ — 优点：无需重构现有文件结构；缺点：隐式依赖容易在新增功能时引发 ImportError，难以维护
- **提取 scholar/_shared.py** — 优点：建立单向依赖链（commands -> _shared <- cli），彻底消除循环，使 cli.py 成为纯入口；缺点：需要批量更新 9 个命令模块的 import 语句

## 决策
新建 `scholar/_shared.py` 承载 `app`, `console`, `parser` 及 `_get_db` 等共享对象。`cli.py` 精简为仅负责导入命令模块并启动 app 的入口文件，所有命令模块改为从 `_shared` 导入共享依赖。

## 影响
CLI 模块结构更加清晰，消除了因 import 顺序导致的潜在运行时错误。后续新增命令模块时无需担心循环导入问题，但需注意 `_shared.py` 不应反向依赖具体的命令实现。