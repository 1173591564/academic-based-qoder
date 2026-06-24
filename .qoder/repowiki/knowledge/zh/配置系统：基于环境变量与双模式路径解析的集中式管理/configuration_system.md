Scholar Studio 采用**集中式配置模块** (`scholar/config.py`) 结合 **`.env` 文件**与**环境变量**的配置管理模式。系统设计兼顾了开发环境的灵活性与打包部署（PyInstaller）的便携性，并通过 `infra/docker-compose.yml` 提供基础设施的默认配置基准。

### 1. 核心架构与设计模式

*   **集中式配置中心**：所有运行时配置（数据库连接、API 密钥、目录路径、外部工具命令）均定义在 `scholar/config.py` 中。该模块在导入时立即执行，通过 `os.getenv` 读取环境变量，并提供合理的默认值。
*   **双模式路径解析 (Dual-Mode Path Resolution)**：
    *   **开发模式**：`PROJECT_ROOT` 指向源码根目录，便于直接运行 `python -m scholar`。
    *   **打包模式 (Frozen)**：当检测到 `sys.frozen` 为真时，`SCHOLAR_HOME` 默认指向用户主目录下的 `~/.scholar-studio/`。这确保了打包后的可执行文件将数据、日志和配置隔离在用户空间，避免权限问题并支持多项目隔离。
    *   **动态覆盖**：可通过设置 `SCHOLAR_HOME` 环境变量自定义知识库根目录。
*   **环境文件加载**：使用 `python-dotenv` 库。系统优先加载 `SCHOLAR_HOME/.env`，在开发模式下若存在源码根目录的 `.env` 也会加载（不覆盖已存在的环境变量）。
*   **基础设施即配置基准**：`infra/docker-compose.yml` 中定义的数据库密码、端口映射等与 `config.py` 中的默认值严格保持一致，实现了“开箱即用”的开发体验。

### 2. 关键配置文件与变量

| 文件/位置 | 作用 | 关键内容 |
| :--- | :--- | :--- |
| `scholar/config.py` | 配置逻辑核心 | 路径解析、环境变量读取、默认值定义、`.env` 加载逻辑 |
| `.env.example` | 配置模板 | 列出所有可选环境变量，提示用户复制为 `.env` 并填写敏感信息 |
| `infra/docker-compose.yml` | 基础设施配置 | PostgreSQL (pgvector) 和 Neo4j 的容器化部署配置，其凭证与 config 默认值同步 |
| `pyproject.toml` | 依赖管理 | 声明 `python-dotenv` 为必需依赖 |

**主要配置项分类：**
*   **数据库**：`SCHOLAR_PG_*` (Host, Port, Name, User, Pass), `SCHOLAR_NEO4J_*` (URI, User, Pass)
*   **AI/RAG**：`SCHOLAR_EMBEDDING_PROVIDER` (zhipu/openai), `SCHOLAR_EMBEDDING_API_KEY`, `SCHOLAR_EMBEDDING_MODEL`
*   **工具链**：`SCHOLAR_LATEX_CMD` (LaTeX 编译器路径)
*   **网络**：`SCHOLAR_ARXIV_TIMEOUT`, `SCHOLAR_ARXIV_RETRIES`

### 3. 初始化与生命周期

*   **自动初始化**：`config.init_scholar_home()` 函数用于在首次运行或打包环境中创建必要的目录结构（`data/papers`, `output/*`, `LEAN` 等）并生成 `.env.example`。
*   **懒加载与容错**：数据库连接 (`scholar/db.py`) 和 RAG 索引 (`scholar/rag.py`) 在运行时根据配置动态建立。若数据库不可用，系统会自动降级为文件-only 模式，确保核心功能可用。

### 4. 开发者规范

1.  **敏感信息管理**：严禁将真实的 API Key 或数据库密码提交到版本控制系统。所有敏感信息应存入 `.env` 文件（已在 `.gitignore` 中忽略）。
2.  **新增配置项**：
    *   在 `scholar/config.py` 中添加对应的 `os.getenv` 调用及默认值。
    *   在 `.env.example` 中补充说明和示例值。
    *   若涉及基础设施变更，同步更新 `infra/docker-compose.yml`。
3.  **路径引用**：所有文件路径应基于 `config.PROJECT_ROOT` 或 `config.SCHOLAR_HOME` 构建，避免使用硬编码的相对路径或绝对路径，以兼容打包模式。
4.  **环境同步**：修改 `docker-compose.yml` 中的数据库凭证时，必须同步更新本地 `.env` 文件或 `config.py` 中的默认值，否则会导致连接失败。