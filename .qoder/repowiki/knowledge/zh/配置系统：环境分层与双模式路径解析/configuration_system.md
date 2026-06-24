## 1. 核心架构与策略
Scholar Studio 采用**“代码即配置” (Code-as-Configuration)** 与 **环境变量驱动** 相结合的混合配置策略。系统通过 `scholar/config.py` 集中管理所有运行时参数，支持从开发环境到打包部署（PyInstaller）的无缝切换。

### 关键设计模式：
- **双模式路径解析 (Dual-Mode Resolution)**：自动检测 `sys.frozen` 状态。在开发模式下，根目录指向源码父目录；在打包模式下，指向用户主目录下的 `~/.scholar-studio/`，确保数据持久化与程序解耦。
- **环境变量优先级**：遵循 `Env Var > .env File > Code Defaults` 的加载顺序。利用 `python-dotenv` 库在模块初始化时自动加载 `.env` 文件。
- **基础设施同步**：Python 端的默认数据库凭证（PostgreSQL, Neo4j）与 `infra/docker-compose.yml` 中的定义严格保持一致，实现“开箱即用”的开发体验。

## 2. 关键配置文件
| 文件路径 | 作用描述 |
| :--- | :--- |
| `scholar/config.py` | **配置中枢**。定义所有路径常量、数据库连接串、API Key 及 arXiv 请求参数。包含 `init_scholar_home()` 用于首次运行时的目录初始化。 |
| `.env.example` | **变量模板**。提供所有可配置项的说明，明确标注了哪些是必填项（如 Embedding API Key），哪些有安全默认值。 |
| `infra/docker-compose.yml` | **基础设施配置**。定义 PostgreSQL (pgvector) 和 Neo4j 的容器化部署参数，其 `environment` 字段是 Python 配置的默认值来源。 |
| `desktop/src-tauri/tauri.conf.json` | **桌面壳层配置**。定义 Tauri 应用的窗口属性、构建路径及安全策略。 |
| `desktop/src-tauri/Cargo.toml` | **Rust 依赖配置**。管理桌面端原生功能的依赖库。 |

## 3. 配置分层与加载逻辑
1. **路径层**：通过 `_resolve_scholar_home()` 确定 `SCHOLAR_HOME`。若存在 `SCHOLAR_HOME` 环境变量则优先使用，否则根据运行模式自动推导。
2. **工作空间层**：引入 `WORKSPACE_DIR` 概念，支持多项目隔离。输出目录（如 `output/drafts`）会根据 `SCHOLAR_PROJECT_NAME` 动态创建子文件夹。
3. **服务层**：
   - **数据库**：通过 `SCHOLAR_PG_*` 和 `SCHOLAR_NEO4J_*` 系列变量控制。
   - **AI 能力**：通过 `SCHOLAR_EMBEDDING_PROVIDER` (zhipu/openai) 和 `SCHOLAR_EMBEDDING_API_KEY` 切换模型提供商。
   - **外部工具**：支持通过 `SCHOLAR_LATEX_CMD` 自定义 LaTeX 编译器路径。

## 4. 开发者规范
- **敏感信息管理**：严禁将真实的 API Key 或数据库密码提交至 Git。所有密钥必须存放在 `.env` 文件中（该文件已在 `.gitignore` 中排除）。
- **默认值维护**：修改 `config.py` 中的默认端口或密码时，必须同步更新 `infra/docker-compose.yml` 和 `.env.example`，防止本地开发环境与容器环境脱节。
- **跨语言配置同步**：Tauri 后端 (`lib.rs`) 通过 `get_scholar_home()` 复用了 Python 端的路径逻辑。若修改全局目录结构，需同时检查 Rust 端的 `dirs::home_dir()` 调用逻辑。