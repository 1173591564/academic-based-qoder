Scholar Studio 智能研究平台采用了一种**轻量级、防御性**的错误处理策略，主要依赖于 Python 标准库的异常捕获机制和 `typer` 框架的退出码控制。系统没有定义全局的自定义异常类或统一的错误响应中间件，而是通过在各功能模块中显式捕获异常并转换为友好的控制台输出来实现容错。

### 1. 核心策略：优雅降级 (Graceful Degradation)
系统在多个关键组件中实现了“失败即回退”的逻辑，确保单一服务不可用时不影响整体流程：
- **数据库层 (`scholar/db.py`)**：`Database` 类在初始化时尝试连接 PostgreSQL。如果连接失败（如 Docker 未启动或驱动缺失），`available` 属性返回 `False`。上层命令（如 `scan`, `search`）会检查此状态，若不可用则自动回退到基于本地 JSON 文件的读写模式 (`dbmod.list_parsed`, `dbmod.load_parsed`)。
- **图数据库层 (`scholar/commands/graph_ops.py`)**：在执行 `graph-build` 或 `graph-query` 前，代码会检查 Neo4j 的连接状态。若不可用，直接打印警告并退出，或在 `bootstrap` 等长流程中跳过该步骤并继续执行后续任务。
- **外部 API 调用**：在 `year_fix`、`author_fix` 和 `kb_update` 中，对 arXiv API 的请求被包裹在 `try...except` 块中。网络波动或解析错误只会导致当前条目跳过，不会中断整个批处理任务。

### 2. 异常传播与终止
- **CLI 退出码**：使用 `typer.Exit(1)` 作为主要的错误终止信号。当发生致命错误（如文件不存在、必要配置缺失、解析完全失败）时，命令会打印红色错误信息并抛出 `typer.Exit(1)`，确保脚本返回非零退出码，便于 CI/CD 或上游调用者感知失败。
- **MCP 服务器封装 (`scholar_mcp/server.py`)**：MCP 工具通过 `_run_scholar` 函数以子进程方式调用 CLI。它捕获子进程的 `stderr` 并将其格式化为 `[ERROR]` 前缀的消息返回给 IDE。这种设计将复杂的 Python 异常栈隔离在子进程中，向 LLM 客户端提供简化的错误上下文。

### 3. 结构化错误报告
- **LaTeX 编译诊断 (`scholar/commands/execution_ops.py`)**：针对 LaTeX 编译这一高频出错场景，系统实现了专用的 `_parse_latex_log` 函数。它不依赖 Python 异常，而是解析 `.log` 文件，将错误分类为 `FATAL`（致命）、`WARN`（警告，如 Overfull hbox）和 `INFO`。这种领域特定的错误解析比通用的堆栈跟踪更具指导意义。
- **实验运行监控**：`exp-run` 命令捕获 `subprocess.TimeoutExpired` 和非零返回码，将 `stdout` 和 `stderr` 写入 `run_log.txt`，并提供 `exp-debug` 命令通过正则匹配常见错误模式（如 `ModuleNotFoundError`, `CUDA out of memory`）来辅助诊断。

### 4. 开发者规范
- **禁止静默失败**：除了少数非关键的后台同步任务，大多数 `except Exception` 块都伴随 `console.print` 输出，明确告知用户发生了什么错误。
- **批量任务的容错**：在 `parse-all`、`batch-ingest` 等批量操作中，单个条目的失败会被记录在 `errors` 列表中，循环继续执行，最后在总结面板中统一展示失败项，避免因单点故障导致整个知识库更新中断。
- **配置校验**：在涉及 API 密钥（如 `rag-index`）或外部工具（如 `compile-paper` 检查 `pdflatex`）的命令入口处，进行前置检查并提前退出，避免在执行深处才报错。