Scholar Studio 采用**防御性编程（Defensive Programming）**和**优雅降级（Graceful Degradation）**作为核心错误处理策略。代码库中未定义全局自定义异常类，而是广泛依赖 Python 内置异常、`try-except` 块以及状态检查来实现系统的健壮性。

### 1. 核心策略：优雅降级与可用性检查
系统在设计上允许关键基础设施（如 PostgreSQL, Neo4j）不可用，通过“可用性检查”模式自动切换到文件存储或跳过相关操作。
- **数据库层 (`scholar/db.py`, `scholar/graph_db.py`)**: 
  - 在初始化或执行操作前，通过 `available` 属性检查连接状态。
  - 捕获 `ImportError` 处理缺失的驱动包（如 `psycopg2`, `neo4j`）。
  - 捕获通用 `Exception` 处理连接失败，返回 `False` 或 `None`，使上层逻辑能无缝切换到 JSON 文件存储模式。
- **RAG 模块 (`scholar/rag.py`)**:
  - 嵌入生成失败时返回 `None`，索引过程会统计 `failed` 数量而非中断整个批处理。
  - 外部 API 调用（智谱/OpenAI）被包裹在 `try-except` 中，失败时打印日志并返回空结果。

### 2. CLI 交互层的错误呈现
命令行接口层负责将底层异常转化为友好的用户提示。
- **Typer 退出码**: 使用 `raise typer.Exit(1)` 在发生致命错误（如论文目录不存在、解析失败）时终止程序并返回非零退出码。
- **Rich 控制台输出**: 使用 `[red]Error:[/]` 和 `[yellow]Warning:[/]` 标记区分错误严重程度。
- **批量操作容错**: 在 `parse-all` 等批量任务中，单个文件的失败会被捕获并记录在 `errors` 列表中，任务继续执行，最后统一汇报成功与失败统计。

### 3. 资源管理与事务一致性
- **上下文管理器**: `scholar/db.py` 中的 `cursor()` 方法使用 `@contextmanager` 确保数据库游标正确关闭，并在异常发生时自动执行 `conn.rollback()`，保证数据一致性。
- **原子写入**: `scholar/research_loop.py` 和 `scholar/config.py` 中使用“先写临时文件再 `os.replace`”的模式，防止进程中断导致配置文件或状态文件损坏。

### 4. 开发者规范
- **禁止静默失败**: 除非是预期的降级逻辑（如 DB 不可用），否则 `except` 块中应记录错误或抛出异常。
- **避免裸 `except`**: 大部分代码遵循 `except Exception as e` 的模式，以便记录具体的错误信息。
- **外部依赖隔离**: 所有涉及网络请求或外部二进制调用的代码必须包含超时处理和异常捕获。