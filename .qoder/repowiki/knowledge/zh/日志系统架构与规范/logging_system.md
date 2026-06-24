Scholar Studio 采用**分层混合**的日志策略，根据组件（桌面端 Rust vs 引擎 Python）和运行环境（开发 vs 生产）选择不同的输出方式。

### 1. 桌面端 (Tauri/Rust)
- **框架**: 使用 `tauri-plugin-log` (v2) 和 `log` crate。
- **配置**: 在 `desktop/src-tauri/src/lib.rs` 中初始化。
- **环境差异**:
  - **Debug 模式**: 启用 `tauri_plugin_log::Builder`，日志级别设为 `Info`。日志会输出到控制台和文件（默认 Tauri 行为）。
  - **Release 模式**: 未显式配置日志插件，依赖 Tauri 默认行为或静默。
- **临时调试**: 在 `lib.rs` 中存在少量 `eprintln!` 用于进程管理（如 `taskkill`）的紧急错误输出，这通常被视为临时措施而非正式日志。

### 2. 引擎端 (Python/Scholar CLI)
- **框架**: **无专用日志框架**。未使用 `logging`、`loguru` 或 `structlog`。
- **输出方式**:
  - **用户界面**: 主要使用 `rich.console.Console` (`scholar/_shared.py`) 进行结构化、带颜色的终端输出。这些输出旨在供人类阅读，而非机器解析。
  - **数据交换**: 在 MCP Server (`scholar_mcp/server.py`) 和 CLI 命令中，大量使用 `print()` 输出 JSON 字符串或纯文本结果，以便上层应用（如 Qoder IDE）捕获。
  - **错误处理**: 异常通常通过 `typer.Exit(1)` 或返回包含 `error` 字段的 JSON 来处理，而不是记录到日志文件。
- **持久化**: 没有发现将 Python 端日志持久化到文件的逻辑。研究循环的“日志” (`output/logs/week-*.jsonl`) 实际上是**业务数据**（对话历史），而非系统运行日志。

### 3. 开发者规范
- **Rust 端**: 
  - 优先使用 `log::info!`, `log::error!` 等宏。
  - 避免在生产代码中使用 `println!` 或 `eprintln!`，除非是极底层的进程控制且无法通过日志框架捕获。
- **Python 端**:
  - **禁止**直接使用 `print()` 进行调试或状态报告。应使用 `console.print()` (来自 `rich`) 以保持 UI 一致性。
  - **MCP 工具**: 必须返回字符串或 JSON 字符串，严禁直接打印副作用信息，以免污染 MCP 协议通信。
  - **缺乏持久化**: 目前 Python 端没有运行时日志文件。若需排查后台任务（如 `research_loop`）的错误，需依赖调用方的捕获或增强错误返回机制。

### 4. 关键文件
- `desktop/src-tauri/src/lib.rs`: Rust 日志插件配置。
- `desktop/src-tauri/Cargo.toml`: 依赖 `tauri-plugin-log`。
- `scholar/_shared.py`: 定义全局 `console` 对象。
- `scholar_mcp/server.py`: Python 端输出逻辑示例。