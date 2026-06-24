Scholar Studio 项目未采用传统的结构化日志框架（如 `logging`、`loguru` 或 `structlog`），而是构建了一套基于 **Rich** 库的交互式控制台输出体系，并结合文件系统持久化作为“日志”的主要载体。

### 1. 核心输出机制：Rich Console
- **框架选择**：使用 `rich.console.Console` 作为唯一的用户交互输出接口。
- **实现位置**：在 `scholar/_shared.py` 中初始化全局 `console` 实例，并在所有 CLI 命令模块（`scholar/commands/*.py`）中通过 `console.print()` 输出带颜色、表格和面板（Panel）的结构化文本。
- **特点**：
  - **可视化强**：利用 Rich 的特性展示论文状态表格、搜索结果的进度条以及统计信息的卡片式布局。
  - **无等级管理**：没有定义 `DEBUG/INFO/WARN/ERROR` 等日志级别，所有输出均直接面向终端用户。
  - **错误处理**：通过捕获异常并打印 `[ERROR]` 标记的文本或黄色警告信息来处理运行时问题，而非记录堆栈跟踪到文件。

### 2. “日志”即数据：文件持久化策略
项目将运行过程中的关键状态和结果直接持久化为结构化文件，替代了传统的应用日志：
- **解析结果**：`output/parsed/*.json` 存储每篇论文的 TeX 解析元数据。
- **研究笔记**：`output/notes/*.md` 存储自动生成的阅读笔记。
- **质量评分**：`output/notes/*-quality.json` 存储论文的多维度评分。
- **同步报告**：`output/digests/sync-*.md` 记录 arXiv 同步的历史和结果。
- **兴趣画像**：`output/research-interests.json` 追踪用户的研究方向。
- **对话日志**：`output/logs/<project>/week-*.jsonl` 以 JSONL 格式存储 AI 对话历史，用于后续的兴趣提取和分析。

### 3. MCP 服务模式
- **静默执行**：`scholar_mcp` 作为长驻进程，主要通过标准输入/输出（STDIN/STDOUT）与 IDE 进行 MCP 协议通信。
- **状态共享**：通过 `scholar/_state.py` 维护内存中的连接池和缓存，不产生额外的运行时日志文件。

### 4. 开发者规范
- **禁止使用 `print()`**：在 CLI 模块中应统一使用 `console.print()` 以保持输出风格一致。
- **避免引入 `logging`**：除非为了调试第三方库，否则不应在业务逻辑中引入 Python 标准 `logging` 模块，以免破坏 Rich 输出的整洁性。
- **错误反馈**：关键错误应通过 `typer.Exit(1)` 退出并配合 `console.print` 提示用户，而非静默失败或抛出未捕获异常。