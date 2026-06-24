该代码库采用**非侵入式、防御性**的错误处理策略，主要依赖 Python 的 `try-except` 块进行局部捕获和静默降级，而非全局异常传播或自定义错误类型体系。

### 1. 核心策略：静默失败与降级 (Silent Failure & Degradation)
在核心数据处理模块（如 `scholar/tex_parser.py` 和 `scholar_mcp/server.py`）中，广泛使用 `try-except Exception: pass` 或 `except Exception as e: return error_message`。
- **解析容错**：在 TeX 解析、BibTeX 读取和元数据提取过程中，任何单个文件的解析失败都不会中断整体流程，而是被捕获并跳过，确保批量任务（如 `parse-all`）的鲁棒性。
- **服务降级**：在 MCP Server 中，对 Neo4j、PostgreSQL 或外部 API（arXiv）的调用均包裹在 try-except 中。如果服务不可用，函数会返回友好的提示信息（如 "Neo4j not available"）或空结果，而不是抛出崩溃性异常。

### 2. CLI 层错误呈现
在命令行接口（`scholar/commands/*.py`）中，错误处理侧重于用户反馈：
- **Typer Exit**：使用 `raise typer.Exit(1)` 来终止执行并返回非零退出码，通常配合 `console.print` 输出彩色错误提示。
- **Rich Console**：利用 `rich.console` 输出结构化错误信息，区分 `[red]ERROR[/]`、`[yellow]WARN[/]` 和 `[green]OK[/]`，提升可读性。

### 3. 缺乏统一错误类型
代码库中未定义自定义异常类（如 `ScholarError` 或 `ParseError`）。所有错误均直接使用内置的 `Exception`、`FileNotFoundError` 或 `json.JSONDecodeError`。这意味着错误处理逻辑高度分散，依赖于调用位置的上下文判断，而非通过异常类型进行分层处理。

### 4. 开发者规范
- **禁止裸奔**：在涉及 I/O、网络请求或复杂正则匹配的函数中，必须包裹 `try-except`。
- **日志记录**：在捕获异常时，应优先记录错误详情（当前实现中部分地方仅返回字符串，建议增强日志记录）。
- **返回值约定**：MCP Tool 函数在出错时应返回包含 `"error": "message"` 的 JSON 字符串，以便前端或 LLM 客户端能识别失败状态。