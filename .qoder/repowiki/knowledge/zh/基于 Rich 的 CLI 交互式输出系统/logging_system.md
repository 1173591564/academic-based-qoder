该仓库（Scholar Studio）未采用传统的文件日志系统（如 Python `logging` 模块、Loguru 或结构化 JSON 日志），而是构建了一套**基于 `rich` 库的命令行交互式输出系统**。其核心目标是为用户提供清晰、美观且结构化的终端反馈，而非用于后端服务监控或故障排查。

### 1. 核心架构与组件
*   **统一控制台实例 (`console`)**：
    *   在 `scholar/_shared.py`中定义了全局共享的 `rich.console.Console` 实例。
    *   所有命令模块（`commands/*.py`）均通过 `from .._shared import console` 引入，确保输出行为的一致性。
*   **富文本格式化**：
    *   广泛使用 `rich.panel.Panel` 包裹关键操作的结果摘要（如解析统计、图谱构建状态、质量评分）。
    *   使用 `rich.table.Table` 展示列表数据（如论文列表、搜索结果、图谱节点统计）。
    *   使用 `rich.progress.Progress` 和 `SpinnerColumn` 提供长时任务（如批量解析 `parse-all`）的实时进度反馈。
*   **颜色与状态标记**：
    *   约定俗成的颜色语义：`[green]` 表示成功/完成，`[red]` 表示错误/失败，`[yellow]` 表示警告/跳过/不可用，`[cyan]` 表示当前操作步骤，`[dim]` 表示次要信息或路径。

### 2. 输出策略与惯例
*   **CLI 交互优先**：
    *   所有用户可见的输出均通过 `console.print()` 进行。这种方式支持自动换行、Markdown 渲染和表情符号，提升了 CLI 工具的可读性。
    *   **错误处理**：严重错误通常伴随 `typer.Exit(1)` 抛出，并在退出前通过 `console.print` 输出红色错误信息。
*   **静默与结构化输出模式**：
    *   部分命令（如 `info`, `search`, `stats`）支持 `--json` 标志。当启用该标志时，系统会绕过 `console`，直接使用原生 `print(json.dumps(...))` 输出纯 JSON 字符串，以便与其他脚本或管道集成。
*   **后台任务的日志降级**：
    *   在少数涉及网络请求或后台处理的模块（如 `rag.py` 中的嵌入生成失败），由于缺乏统一的日志框架，开发者使用了 `print(..., file=sys.stderr)` 将错误信息输出到标准错误流。这是一种临时的、非结构化的“日志”处理方式，仅用于调试或极端异常捕获。

### 3. 缺失的传统日志功能
*   **无持久化日志**：系统中没有发现将运行日志写入文件（如 `.log` 文件）的配置或代码。`output/logs/` 目录在代码中被引用（如 `research_loop.py`），但其用途是存储**用户对话历史**（JSONL 格式）而非应用程序的运行日志。
*   **无日志级别控制**：不存在 `DEBUG/INFO/WARN/ERROR` 级别的动态切换机制。输出的详细程度硬编码在业务逻辑中。
*   **无结构化日志字段**：除了 JSON 导出模式外，常规运行输出为非结构化的富文本，无法直接被 ELK 或 Prometheus 等监控系统采集。

### 4. 开发者指南
*   **如何添加输出**：
    *   始终使用 `from .._shared import console` 获取控制台实例。
    *   使用 `console.print("[cyan]Step 1: Processing...[/]")` 标记步骤。
    *   使用 `console.print(Panel(...))` 包装最终结果块。
    *   避免使用 `print()`，除非是在 `--json` 模式下输出机器可读内容。
*   **错误报告**：
    *   对于可恢复的警告，使用 `console.print("[yellow]Warning: ...[/]")`。
    *   对于致命错误，使用 `console.print("[red]Error: ...[/]")` 并随后 `raise typer.Exit(1)`。
*   **调试建议**：
    *   由于缺乏 `logging.debug`，调试时通常临时插入 `console.print` 或使用 `pdb`。建议在开发环境中通过环境变量控制是否打印详细的中间状态。