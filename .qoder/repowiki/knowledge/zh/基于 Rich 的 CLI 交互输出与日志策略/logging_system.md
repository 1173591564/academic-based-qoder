## 1. 系统概述
Scholar Studio 智能研究平台**未采用传统的持久化日志框架**（如 Python 标准库 `logging`、`loguru` 或 `structlog`）。其“日志”系统完全围绕 **CLI（命令行界面）交互体验**构建，核心目标是为用户提供实时、结构化且美观的控制台反馈。

- **核心组件**：`rich.console.Console`。
- **输出目标**：标准输出（stdout），主要用于终端显示。
- **持久化**：无统一的日志文件落盘机制。关键业务状态（如研究兴趣、同步报告、解析结果）通过 JSON 或 Markdown 文件显式保存到 `output/` 目录。
- **MCP 集成**：MCP Server 通过 `subprocess` 调用 CLI，捕获 stdout/stderr 作为工具调用的返回结果。

## 2. 关键实现细节

### 2.1 全局 Console 实例
在 `scholar/_shared.py` 中定义了全局共享的 `Console` 实例，确保整个应用使用统一的输出配置：
```python
from rich.console import Console
console = Console()
```
所有命令模块（`commands/*.py`）均通过 `_shared` 导入并使用该实例。

### 2.2 输出规范与样式
平台利用 Rich 的标记语言实现结构化输出：
- **状态标识**：使用 `[green][OK][/green]`、`[red]Error:[/]`、`[yellow][!!][/yellow]` 等标签区分操作成功、失败或警告。
- **信息面板**：使用 `Panel` 组件包裹关键摘要（如论文解析结果、知识库统计），提升可读性。
- **数据表格**：使用 `Table` 组件展示列表型数据（如论文库扫描、搜索结果）。
- **进度反馈**：在批量任务（如 `parse-all`）中使用 `Progress` 和 `SpinnerColumn` 提供实时进度条。

### 2.3 错误处理与反馈
- **即时反馈**：异常通过 `console.print` 打印红色错误信息，并配合 `typer.Exit(1)` 终止程序。
- **MCP 层捕获**：在 `scholar_mcp/server.py` 中，`_run_scholar` 函数捕获子进程的 `stderr`，并将其格式化为 `[ERROR] ...` 附加到返回字符串中，供 IDE 展示。

### 2.4 业务状态持久化（替代传统日志）
对于需要追踪的业务过程，平台采用“状态文件”而非“日志行”：
- **研究同步**：`research_loop.py` 将同步结果写入 `output/digests/sync-YYYY-MM-DD.md`。
- **分析状态**：使用 `output/logs/<project>/analyzed.json` 记录已处理的日志周次，避免重复分析。
- **解析产物**：论文解析结果以 JSON 形式存入 `output/parsed/`。

## 3. 开发者约定

1. **禁止使用 `print()`**：所有用户可见输出必须通过 `console.print()` 进行，以确保样式统一和测试友好。
2. **样式标准化**：
   - 成功：`[green]...[/green]`
   - 错误：`[red]...[/red]`
   - 警告/提示：`[yellow]...[/yellow]`
   - 次要信息：`[dim]...[/dim]`
3. **长任务反馈**：涉及网络请求或大量文件处理的操作，必须使用 `rich.progress.Progress` 提供可视化进度。
4. **MCP 兼容性**：命令输出的内容应兼顾人类阅读和机器解析。MCP 工具直接返回 CLI 的 stdout，因此避免在 stdout 中混入非预期的调试信息。
5. **调试信息**：如需临时调试，建议使用 `console.log()`（Rich 提供的类似 print 但支持更复杂对象渲染的方法），并在提交前移除。