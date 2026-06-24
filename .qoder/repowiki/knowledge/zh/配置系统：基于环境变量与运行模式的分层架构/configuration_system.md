## 1. 核心系统与策略
Scholar Studio 采用**“代码即配置 + 环境变量覆盖”**的混合配置策略。核心逻辑集中在 `scholar/config.py`，通过检测 Python 运行环境（开发模式 vs PyInstaller 打包模式）动态确定根目录 (`SCHOLAR_HOME`)。

- **分层加载**：优先读取 `.env` 文件，随后通过 `os.getenv` 读取系统环境变量进行覆盖。
- **双模运行**：
  - **开发模式**：以源码目录为根，便于调试和版本控制。
  - **打包模式 (Frozen)**：默认指向用户主目录下的 `~/.scholar-studio/`，确保可执行文件在任意位置运行时都能访问统一的知识库。

## 2. 关键配置文件
| 文件路径 | 作用描述 |
| :--- | :--- |
| `scholar/config.py` | 配置中枢。定义所有路径常量、数据库连接参数及 API 密钥加载逻辑。 |
| `.env.example` | 环境变量模板。提供 PostgreSQL、Neo4j 及 RAG 嵌入模型的默认值说明。 |
| `infra/docker-compose.yml` | 基础设施配置。定义了本地开发环境的数据库服务及其默认凭证。 |
| `pyproject.toml` | 项目元数据与依赖管理。声明了 `python-dotenv` 等配置相关依赖。 |
| `desktop/src-tauri/tauri.conf.json` | Tauri 桌面端应用配置。管理前端构建路径及窗口行为。 |
| `LEAN/lakefile.toml` | Lean4 形式化验证引擎的项目配置。 |

## 3. 架构约定与设计决策
### 3.1 路径解析优先级
系统通过 `_resolve_scholar_home()` 和 `_resolve_workspace_dir()` 实现了灵活的路径管理：
1. **全局知识库 (`SCHOLAR_HOME`)**：存储论文原文、解析结果及向量索引。可通过 `SCHOLAR_HOME` 环境变量自定义。
2. **工作区 (`WORKSPACE_DIR`)**：存储特定项目的草稿、笔记和日志。优先级为：`SCHOLAR_WORKSPACE` 环境变量 > 当前工作目录 (打包模式下) > `SCHOLAR_HOME`。

### 3.2 敏感信息管理
- **安全原则**：`.env` 文件已被加入 `.gitignore`，严禁提交真实密钥。
- **默认值兜底**：对于非敏感的数据库地址或端口，代码中提供了与 `docker-compose.yml` 匹配的默认值，实现“开箱即用”。
- **自动初始化**：`init_scholar_home()` 函数会在首次运行时自动创建目录结构并生成 `.env.example`。

## 4. 开发者规范
- **新增配置项**：必须在 `scholar/config.py` 中统一定义，并提供合理的默认值。
- **环境变量命名**：遵循 `SCHOLAR_<MODULE>_<KEY>` 格式（如 `SCHOLAR_PG_HOST`），避免与其他工具冲突。
- **跨模块引用**：所有业务模块应通过 `from scholar.config import ...` 导入配置，禁止硬编码路径或重复实现加载逻辑。
- **桌面端同步**：若涉及 Tauri 桌面端配置修改，需同步更新 `desktop/src-tauri/tauri.conf.json` 并确保 Rust 侧能正确读取对应的环境变量。