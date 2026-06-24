## 1. 系统与方法 (System & Approach)
该项目为纯命令行（CLI）工具，**不存在 Web 前端界面**。其“前端”风格体现为终端用户界面（TUI）的视觉规范，主要依赖以下技术栈：
- **核心框架**: `Typer` 用于构建命令行接口结构。
- **渲染引擎**: `Rich` 库负责所有终端输出的样式化，包括颜色、表格、面板和进度条。
- **设计原则**: 采用语义化颜色编码（如 `[cyan]` 表示状态/步骤，`[green]` 表示成功，`[red]` 表示错误）和结构化布局（`Panel` 包裹关键结果，`Table` 展示多维数据）。

## 2. 关键文件 (Key Files)
- `scholar/_shared.py`: 定义全局共享的 `Console()` 实例和 `Typer` app 对象，确保全项目输出风格统一。
- `scholar/commands/*.py`: 各功能模块（如 `batch_ops.py`, `graph_ops.py`）通过导入共享的 `console` 对象执行具体的样式化输出。
- `build_exe.py`: 在打包配置中显式包含 `rich.console`, `rich.panel`, `rich.table` 等模块，证明 Rich 是运行时 UI 的核心依赖。

## 3. 架构与约定 (Architecture & Conventions)
- **集中式控制台管理**: 通过 `_shared.py` 单例化 `Console` 对象，避免在不同模块中重复初始化，保证日志与输出的一致性。
- **组件化输出**: 
  - **Panel (面板)**: 用于包裹命令执行的核心结果或阶段性总结（如 `Bootstrap` 进度、`Auto-Note` 生成状态）。
  - **Table (表格)**: 用于展示结构化数据，如论文质量评分维度（`quality-score`）、标签统计分布（`classify --list-tags`）。
  - **Color Tags (颜色标签)**: 使用 Rich 标记语言（如 `[bold]`, `[yellow]`）直接在字符串中嵌入样式，实现高可读性的状态提示。

## 4. 开发者规范 (Rules for Developers)
- **禁止使用原生 print**: 所有用户可见的输出必须通过 `scholar._shared.console` 进行，以支持统一的样式控制和未来的输出重定向。
- **样式语义化**: 
  - 流程步骤使用 `[cyan]`。
  - 成功/完成状态使用 `[green]`。
  - 错误/失败状态使用 `[red]`。
  - 警告/跳过状态使用 `[yellow]`。
- **结构化展示**: 对于超过两行的关键返回数据，应使用 `rich.panel.Panel` 进行包裹；对于列表型数据，应优先使用 `rich.table.Table`。