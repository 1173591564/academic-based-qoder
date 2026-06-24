Scholar Studio 采用了一套基于 **运行模式检测（Development vs Frozen）** 和 **环境变量分层** 的配置系统。该系统通过 `scholar/config.py` 统一管理 Python 后端、MCP 服务及桌面壳层的路径与运行时参数，确保在不同部署场景下的一致性。

### 1. 核心架构与运行模式

配置系统的核心逻辑位于 `scholar/config.py`，它通过检测 `sys.frozen` 属性来区分两种运行模式：

*   **开发模式 (Development Mode)**:
    *   **根目录 (`SCHOLAR_HOME`)**: 指向源码根目录（即 `scholar/` 的父目录）。
    *   **工作区 (`WORKSPACE_DIR`)**: 默认与 `SCHOLAR_HOME` 一致，可通过 `SCHOLAR_WORKSPACE` 环境变量覆盖以支持多项目隔离。
    *   **配置加载**: 优先加载源码根目录下的 `.env` 文件。

*   **打包模式 (Frozen/Production Mode)**:
    *   **根目录 (`SCHOLAR_HOME`)**: 指向用户全局目录 `~/.scholar-studio/`（可通过 `SCHOLAR_HOME` 环境变量覆盖）。
    *   **工作区 (`WORKSPACE_DIR`)**: 指向当前工作目录 (`cwd`)，支持基于项目的输出隔离。
    *   **初始化**: 提供 `init_scholar_home()` 函数，在首次运行时自动创建全局目录结构（`data/papers`, `output/`, `LEAN/` 等）并生成 `.env.example`。

### 2. 配置分层与优先级

配置加载遵循以下优先级（从高到低）：

1.  **环境变量**: 直接设置的环境变量（如 `SCHOLAR_PG_HOST`）具有最高优先级。
2.  **.env 文件**: 
    *   在开发模式下，加载项目根目录的 `.env`。
    *   在打包模式下，加载 `~/.scholar-studio/.env`。
    *   使用 `python-dotenv` 库加载，且 `override=False`，意味着已存在的环境变量不会被文件覆盖。
3.  **代码默认值**: 在 `config.py` 中硬编码的默认值（如 `localhost`, `scholar2024`），这些默认值与 `infra/docker-compose.yml` 中的基础设施配置保持同步。

### 3. 关键配置项

*   **数据库连接**:
    *   PostgreSQL: `SCHOLAR_PG_HOST`, `SCHOLAR_PG_PORT` (默认 5433), `SCHOLAR_PG_NAME`, `SCHOLAR_PG_USER`, `SCHOLAR_PG_PASS`.
    *   Neo4j: `SCHOLAR_NEO4J_URI` (默认 `bolt://localhost:7687`), `SCHOLAR_NEO4J_USER`, `SCHOLAR_NEO4J_PASS`.
*   **RAG 与 AI**:
    *   `SCHOLAR_EMBEDDING_PROVIDER`: 默认为 `zhipu`。
    *   `SCHOLAR_EMBEDDING_API_KEY`: 必须手动配置，否则 RAG 功能不可用。
    *   `SCHOLAR_EMBEDDING_MODEL`: 默认为 `embedding-2`。
*   **路径与工具**:
    *   `SCHOLAR_LATEX_CMD`: LaTeX 编译命令，默认为 `pdflatex`。
    *   `SCHOLAR_ARXIV_TIMEOUT/RETRIES`: arXiv API 请求的重试策略。

### 4. 桌面端与插件配置

*   **Tauri 桌面壳层**: 
    *   配置文件: `desktop/src-tauri/tauri.conf.json`。
    *   路径解析: Rust 代码 (`lib.rs`) 复用了与 Python 端一致的逻辑，在开发模式下通过 `CARGO_MANIFEST_DIR` 推导项目根目录，在生产模式下使用 `dirs::home_dir()`。
    *   MCP 集成: 桌面端通过动态生成临时 `mcp.json` 文件，将 `SCHOLAR_HOME` 和 `SCHOLAR_WORKSPACE` 注入到 MCP 服务器环境中。
*   **IDE 插件 (Claude/Qoder)**:
    *   配置模板位于 `.qoder/` 和 `.claude/` 目录。
    *   `init_workspace()` 函数会将这些规则、技能和 MCP 配置复制到当前工作区，实现“约定优于配置”的 IDE 集成。

### 5. 开发者规范

*   **敏感信息**: 严禁将 `.env` 文件提交至版本控制系统。所有密钥（如 API Key）应仅存在于本地 `.env` 或用户全局目录中。
*   **默认值同步**: 修改 `infra/docker-compose.yml` 中的数据库密码时，必须同步更新 `scholar/config.py` 中的默认值以及 `.env.example` 中的示例。
*   **路径访问**: 所有对数据目录（如 `PAPERS_DIR`, `OUTPUT_DIR`）的访问必须通过 `scholar.config` 模块提供的常量进行，禁止硬编码相对路径，以确保在打包模式下能正确指向 `~/.scholar-studio/`。