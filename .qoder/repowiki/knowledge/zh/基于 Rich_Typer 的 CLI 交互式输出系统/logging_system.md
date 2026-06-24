## 1. 系统概述
Scholar Studio 未采用传统的 `logging` 模块或文件日志系统，而是构建了一套基于 **Rich** 和 **Typer** 的**交互式控制台输出系统**。该系统主要服务于命令行界面（CLI）和 MCP（Model Context Protocol）服务器，通过结构化、色彩化的终端输出来提供实时反馈、状态报告和错误信息。

## 2. 核心组件与架构
- **控制台引擎 (Rich Console)**: 
  - 在 `scholar/_shared.py` 中初始化全局 `console = Console()` 实例。
  - 所有 CLI 命令均通过此实例输出，确保样式统一。
  - 使用 `Panel` 包裹统计信息和摘要，使用 `Table` 展示论文列表、搜索结果和元数据覆盖度。
- **CLI 框架 (Typer)**:
  - 使用 `typer.Typer` 定义应用入口，自动处理参数解析和帮助文档生成。
  - 通过 `@app.command()` 装饰器注册业务逻辑（如 `scan`, `parse`, `stats`）。
- **MCP 协议适配**:
  - `scholar_mcp/server.py` 暴露了 50+ 个工具函数。
  - 输出格式以**纯文本报告**或 **JSON** 为主，便于 IDE（如 Qoder）解析和展示。
  - 对于复杂操作（如 `survey`, `landscape`），会生成 Markdown 报告并返回文件路径及进度 JSON。

## 3. 输出规范与约定
- **状态标识**: 使用 `[green][OK][/green]`、`[yellow][!!][/yellow]`、`[red]Error[/red]` 等 Rich 标记直观展示操作结果。
- **结构化展示**:
  - **表格 (Table)**: 用于展示多行数据（如论文库扫描、搜索命中）。
  - **面板 (Panel)**: 用于突出显示关键统计（如知识库 Stats、Bootstrap 进度）。
- **JSON 模式**: 多数命令支持 `--json` 标志，直接输出机器可读的 JSON 数据，用于自动化脚本或 MCP 集成。
- **进度反馈**: 在长耗时任务（如 `bootstrap`, `parse-all`）中，通过分步打印（Step 1/8, Step 2/8...）提供进度感知。

## 4. 开发者指南
- **禁止直接使用 `print()`**: 在 CLI 命令实现中，应始终使用 `console.print()` 以支持富文本样式。
- **共享对象引用**: 新命令应从 `scholar._shared` 导入 `app`, `console`。
- **错误处理**: 捕获异常后，应通过 `console.print(f"[red]Error:[/] {e}")` 或返回包含 `error` 字段的 JSON 来报告失败。
- **MCP 工具开发**: 新增 MCP 工具应确保返回值简洁，避免冗长的堆栈跟踪；复杂结果应写入 `output/` 目录并返回路径。

## 5. 关键文件
- `scholar/_shared.py`: 定义全局 `console` 和 `app` 实例。
- `scholar/cli.py`: CLI 入口，组装各模块命令。
- `scholar/commands/*.py`: 具体业务逻辑与控制台输出实现。
- `scholar_mcp/server.py`: MCP 工具定义，负责将 CLI 能力转化为结构化 API 响应。