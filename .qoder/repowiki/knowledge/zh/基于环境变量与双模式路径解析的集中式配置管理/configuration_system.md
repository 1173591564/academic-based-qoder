### 1. 核心系统与架构
Scholar Studio 采用**集中式配置模块** (`scholar/config.py`) 结合 **`.env` 文件**与**系统环境变量**的管理方式。其核心设计目标是支持**开发模式**与**打包模式（PyInstaller）**的无缝切换，同时实现**全局知识库**与**项目级工作区**的逻辑分离。

- **配置加载器**：依赖 `python-dotenv` 库，在模块导入时自动从指定路径加载 `.env` 文件。
- **双模式路径解析**：通过检测 `sys.frozen` 标志位，动态决定 `SCHOLAR_HOME`（全局根目录）和 `WORKSPACE_DIR`（当前项目输出目录）的物理路径。
- **分层优先级**：
  1. 显式设置的环境变量（如 `SCHOLAR_PG_HOST`）。
  2. `.env` 文件中定义的键值对。
  3. 代码中硬编码的默认值（通常与 `infra/docker-compose.yml` 保持一致）。

### 2. 关键文件与职责
| 文件路径 | 职责描述 |
| :--- | :--- |
| `scholar/config.py` | **配置中枢**。定义所有路径常量、数据库连接参数、API 密钥及工具链路径。包含 `_resolve_scholar_home()` 等核心逻辑。 |
| `.env.example` | **配置模板**。提供所有可选环境变量的说明，指导用户如何覆盖默认配置。 |
| `infra/docker-compose.yml` | **基础设施配置**。定义 PostgreSQL (pgvector) 和 Neo4j 的容器化部署参数，其默认账号密码与 `config.py` 中的默认值严格对应。 |
| `pyproject.toml` | **依赖声明**。声明 `python-dotenv` 为运行时必需依赖。 |

### 3. 核心配置项分类
- **路径与环境**：
  - `SCHOLAR_HOME`：全局知识库根目录。开发模式下指向源码根目录，打包模式下指向 `~/.scholar-studio/`。
  - `SCHOLAR_WORKSPACE`：项目级输出目录。允许用户通过环境变量指定当前研究项目的独立工作区。
- **数据存储**：
  - **PostgreSQL**：`SCHOLAR_PG_HOST`, `SCHOLAR_PG_PORT` (默认 5433), `SCHOLAR_PG_NAME` 等。
  - **Neo4j**：`SCHOLAR_NEO4J_URI` (默认 bolt://localhost:7687), `SCHOLAR_NEO4J_USER/PASS`。
- **外部服务**：
  - **RAG Embedding**：`SCHOLAR_EMBEDDING_PROVIDER` (默认 zhipu), `SCHOLAR_EMBEDDING_API_KEY`。
  - **arXiv API**：支持通过 `SCHOLAR_ARXIV_TIMEOUT` 和 `SCHOLAR_ARXIV_RETRIES` 调整请求行为。
- **本地工具链**：
  - `SCHOLAR_LATEX_CMD`：指定本地 LaTeX 编译器路径。

### 4. 开发者规范与约定
1. **禁止硬编码敏感信息**：所有 API Key、数据库密码必须通过环境变量或 `.env` 文件注入。`.env` 文件已被 `.gitignore` 排除。
2. **保持默认值同步**：修改 `infra/docker-compose.yml` 中的数据库端口或密码时，必须同步更新 `scholar/config.py` 中的 `os.getenv` 默认值，以确保开发环境开箱即用。
3. **路径访问规范**：所有文件 I/O 操作必须引用 `config.py` 中导出的路径常量（如 `PAPERS_DIR`, `NOTES_DIR`），严禁使用相对路径字符串，以兼容打包后的单文件运行环境。
4. **初始化逻辑**：首次运行或部署时，应调用 `config.init_scholar_home()` 和 `config.init_workspace()` 确保目录结构完整并生成 `.env.example`。