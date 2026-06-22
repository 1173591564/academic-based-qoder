---
kind: design
name: 重构 CLI 模块以消除循环导入并拆分 God File
source: session
category: adr
---

# 重构 CLI 模块以消除循环导入并拆分 God File

_来源：a14a57f → bc6e785 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
原有的 scholar/cli.py 文件过于庞大（God File），包含所有命令定义和共享对象，导致维护困难。初步尝试将命令拆分到子模块时，因命令模块需引用 cli.py 中的 app 对象，而 cli.py 又需导入命令模块，产生了循环依赖。

## 决策驱动
- 代码可维护性与模块化
- 消除隐式的导入顺序依赖
- 保持 CLI 接口稳定性

## 备选方案
- **提取 _shared.py 存放共享状态** — 优点：彻底打破循环依赖，cli.py 仅作为入口，commands 模块单向依赖 _shared，结构清晰；缺点：增加了一个新的中间模块，需更新所有命令文件的导入路径
- **在 cli.py 中调整导入顺序** _（已否决）_ — 优点：不新增文件；缺点：依赖脆弱的导入时机，容易在重构中再次破坏，不符合最佳实践
- **保持单体 cli.py** _（已否决）_ — 优点：无重构成本；缺点：文件过长，难以定位和修改特定命令逻辑

## 决策
创建 scholar/_shared.py 集中定义 typer.App、console、parser 和数据库连接辅助函数。将原有 cli.py 拆分为 scholar/commands/ 包下的 10 个操作模块（如 core_ops, paper_ops 等）。cli.py 精简为仅导入 _shared 和 commands 的入口脚本。

## 影响
消除了循环导入风险，提升了代码可读性。PyInstaller 配置文件 (.spec) 需显式包含新的 commands 包和 _shared 模块以确保打包完整。