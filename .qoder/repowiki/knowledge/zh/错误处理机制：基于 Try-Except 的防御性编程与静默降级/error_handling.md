该代码库采用了一种**非集中式、基于惯例**的错误处理策略，主要依赖 Python 原生的 `try-except` 块和 `ValueError`/`Exception` 进行控制。系统没有定义自定义异常类体系，而是通过“静默降级”（Silent Degradation）和“结构化错误返回”来保证服务的可用性，特别是在 MCP Server 和 CLI 交互层。

### 1. 核心策略：静默降级与可用性优先
在涉及外部服务（Neo4j, PostgreSQL, arXiv API）或可选功能（RAG, Graph）时，代码倾向于捕获所有异常并返回友好的提示信息，而不是让程序崩溃。
- **服务连接检查**：在 `_shared.py` 和各类操作命令中，数据库连接失败会被捕获并返回 `None` 或状态标记，CLI 层据此显示 `[!!]` 警告而非堆栈跟踪。
- **MCP Server 容错**：`server.py` 中的几乎所有工具函数（如 `scholar_graph_query`, `scholar_rag_search`）都包裹在宽泛的 `try...except Exception` 中，确保单个工具的失败不会导致整个 MCP 服务器中断。

### 2. 错误传播模式
- **CLI 层**：使用 `typer.Exit(1)` 显式终止执行并返回非零退出码，配合 `rich.console` 输出彩色错误提示。
- **MCP 层**：将错误序列化为 JSON 对象（如 `{"error": "message"}`）或纯文本错误描述，以便 LLM 客户端能够解析并告知用户。
- **核心逻辑层**：在 `tex_parser.py` 等核心模块中，对于不可恢复的逻辑错误（如找不到主 TeX 文件、不支持的归档格式），直接抛出 `ValueError`，由上层调用者决定如何处理。

### 3. 关键约定与规则
- **禁止裸奔异常**：在业务逻辑中，避免使用空的 `except:`，至少应捕获 `Exception` 并记录或返回上下文信息。
- **输入校验前置**：在执行耗时操作（如解析、搜索）前，先校验输入参数（如 `paper_id` 是否存在、查询是否为空），无效输入直接返回错误信息。
- **资源安全关闭**：在使用 Neo4j 驱动等资源时，严格使用 `try...finally` 块确保连接关闭，防止资源泄漏。
- **路径遍历防护**：在处理用户上传的 ZIP/Tar 包时，显式检查路径是否超出目标目录（Zip Slip 漏洞防护），发现非法路径立即抛出 `ValueError`。

### 4. 典型实现示例
- **防御性数据库访问**：
  ```python
  def _get_db() -> Optional[dbmod.Database]:
      try:
          database = dbmod.Database()
          if database.available: return database
      except Exception: pass
      return None
  ```
- **MCP 工具错误封装**：
  ```python
  try:
      # ... logic ...
  except Exception as e:
      return json.dumps({"error": str(e)}, ensure_ascii=False)
  ```