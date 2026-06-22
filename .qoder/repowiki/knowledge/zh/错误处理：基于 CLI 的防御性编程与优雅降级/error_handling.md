该代码库采用**防御性编程（Defensive Programming）**与**优雅降级（Graceful Degradation）**相结合的错误处理策略，主要服务于命令行工具（CLI）和学术数据处理流水线。由于缺乏统一的异常类体系或全局错误中间件，错误处理逻辑分散在各个模块中，遵循“尽力而为、失败静默或提示”的原则。

### 1. 核心策略与模式

*   **优雅降级 (Graceful Degradation)**:
    *   **数据库层**: `scholar.db.Database` 和 `scholar.graph_db.GraphDB` 在初始化或操作前会检查 `available` 属性。如果 PostgreSQL 或 Neo4j 不可用（连接失败或缺少驱动），系统会自动回退到文件系统操作（JSON 文件存储）或跳过相关步骤，而不是直接崩溃。
    *   **依赖检查**: 使用 `_try_import_psycopg2()` 等辅助函数动态导入可选依赖。如果导入失败，返回 `None` 并触发降级逻辑。

*   **CLI 退出码管理**:
    *   使用 `typer.Exit(1)` 在命令执行失败时（如论文未解析、目录不存在）终止程序并返回非零退出码，确保脚本调用的可观测性。
    *   错误信息通过 `rich.console.Console` 以红色面板或文本形式输出，提供清晰的用户反馈。

*   **静默失败与日志记录**:
    *   在非关键路径（如 RAG 索引更新、图谱增量同步、兴趣日志分析）中，广泛使用 `try...except Exception: pass` 或 `except Exception as e: print/log warning`。这种模式确保了主流程（如论文解析）不会因为辅助功能（如向量入库）的失败而中断。
    *   例如，`scholar.rag.store_chunks_pg` 在存储失败时仅打印错误信息，不抛出异常。

*   **资源安全与原子性**:
    *   **数据库事务**: `scholar.db.Database.cursor` 使用上下文管理器确保事务提交或回滚，防止数据不一致。
    *   **文件原子写入**: `scholar.research_loop.save_interests` 和 `mark_week_analyzed` 采用“先写临时文件 `.tmp`，再 `os.replace`”的模式，防止进程中断导致配置文件损坏。

### 2. 关键文件与实现细节

*   **`scholar/_shared.py`**:
    *   `_get_db()`: 封装了数据库连接的获取逻辑，捕获所有异常并返回 `None`，是全局降级策略的入口。

*   **`scholar/db.py`**:
    *   `Database.available`: 通过尝试建立短连接来探测数据库状态，捕获 `Exception` 并返回布尔值。
    *   `cursor()`: 实现 `commit/rollback` 逻辑，确保 SQL 操作的原子性。

*   **`scholar/graph_db.py`**:
    *   `GraphDB.available`: 类似地探测 Neo4j 连接。
    *   所有图操作方法均假设驱动可用，但在 CLI 调用层（如 `commands/graph_ops.py`）通常会先检查可用性。

*   **`scholar/tex_parser.py`**:
    *   **输入验证**: 在 `parse_archive` 和 `parse_directory` 中，如果找不到 `.tex` 文件或主文件，主动抛出 `ValueError`，由上层 CLI 捕获并显示错误。
    *   **容错解析**: 在读取文件内容时使用 `errors="ignore"`，防止编码问题导致解析崩溃。

*   **`scholar/rag.py`**:
    *   **API 容错**: `_zhipu_embedding` 和 `_openai_embedding` 捕获所有网络或 API 异常并返回 `None`，允许上层逻辑决定重试或跳过。
    *   **混合搜索**: `search_rag_hybrid` 结合了向量搜索和 BM25，即使向量索引不可用，BM25 仍可提供基础搜索结果。

*   **`scholar/research_loop.py`**:
    *   **日志分析**: `get_unanalyzed_logs` 在读取 JSONL 日志时捕获 `json.JSONDecodeError`，跳过损坏的行，确保分析流程不因单条坏数据而停止。

### 3. 开发者规范与建议

*   **不要吞没关键错误**: 仅在辅助功能（如缓存更新、统计收集）中使用裸 `except Exception: pass`。核心业务逻辑（如论文解析、数据入库）必须抛出异常或返回明确的错误状态。
*   **使用 `typer.Exit`**: 在 CLI 命令中，遇到无法恢复的错误时，应使用 `raise typer.Exit(1)` 而非 `sys.exit()`，以便 Typer 正确处理退出逻辑。
*   **优先使用 `console.print`**: 所有用户可见的错误信息应通过 `rich.console.Console` 输出，保持界面风格一致。
*   **原子写入配置**: 修改 JSON 配置文件时，务必遵循“写临时文件 + `os.replace`”的模式，防止数据损坏。
*   **检查 `available` 属性**: 在调用数据库或图谱功能前，应检查 `db.available` 或 `gdb.available`，并提供友好的降级提示。