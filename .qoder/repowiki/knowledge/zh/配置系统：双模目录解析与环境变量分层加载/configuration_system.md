Scholar Studio 采用了一套基于 **Python 动态解析** 与 **环境变量分层注入** 的配置系统，旨在无缝支持“开发模式”与“打包分发模式”。

### 1. 核心架构与运行模式
- **双模目录解析 (`scholar/config.py`)**：系统通过检测 `sys.frozen` 标志自动切换根目录逻辑。
  - **开发模式**：以源码目录为根，便于调试和即时修改。
  - **打包模式 (Frozen)**：默认指向用户主目录下的 `~/.scholar-studio/`（可通过 `SCHOLAR_HOME` 覆盖），确保程序在分发后拥有独立的全局知识库空间。
- **工作区隔离 (`WORKSPACE_DIR`)**：引入 `SCHOLAR_WORKSPACE` 环境变量，允许用户在特定项目目录下生成输出文件（如草稿、笔记），实现全局知识库与局部工作区的解耦。

### 2. 配置加载流程
1. **环境初始化**：启动时优先从 `SCHOLAR_HOME/.env` 加载配置，若处于开发模式则额外加载源码根目录的 `.env`。
2. **依赖管理**：使用 `python-dotenv` 库进行非覆盖式加载（`override=False`），确保命令行或系统级环境变量具有最高优先级。
3. **自动补全**：提供 `init_scholar_home()` 函数，在首次运行时自动创建标准化的目录结构（如 `data/papers`, `output/logs`）并生成 `.env.example` 模板。

### 3. 关键配置项分类
- **基础设施连接**：PostgreSQL (pgvector) 和 Neo4j 的连接参数均带有 `SCHOLAR_` 前缀，默认值与 `infra/docker-compose.yml` 保持严格同步。
- **AI 服务集成**：支持通过 `SCHOLAR_EMBEDDING_PROVIDER` 切换智谱（Zhipu）或 OpenAI 等 Embedding 提供商。
- **外部工具链**：通过 `SCHOLAR_LATEX_CMD` 等变量定位本地编译工具，增强了对不同操作系统的兼容性。

### 4. 桌面端配置同步
- **Tauri 桥接**：桌面端 (`desktop/src-tauri`) 通过 Rust 代码读取相同的 `SCHOLAR_HOME` 环境变量，并在调用 CLI 子进程时显式注入，确保了 GUI 与后端逻辑配置的一致性。
- **动态 MCP 配置**：在启动 AI 代理会话时，系统会动态生成包含当前工作区路径的 `mcp.json` 临时文件，实现上下文感知的工具链挂载。