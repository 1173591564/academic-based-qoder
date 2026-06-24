Scholar Studio 采用多语言、多模块的混合构建策略，针对 Python 后端、Lean4 形式化验证引擎、Tauri 桌面端以及 IDE 插件分别建立了独立的构建与发布流程。

### 1. 核心构建系统
- **Python 后端 (scholar)**：基于 `pyproject.toml` 和 `setuptools` 进行依赖管理与打包。通过 `scripts/build_exe.py` 结合 `PyInstaller` 实现跨平台可执行文件（`.exe`）的自动化构建，支持 `onedir`（推荐调试）和 `onefile`（单文件分发）两种模式，并自动处理复杂的隐藏导入（如 `psycopg2`, `neo4j`, `rich` 等）。
- **Lean4 引擎 (LEAN)**：使用 `lake` 作为包管理器与构建工具。`lakefile.toml` 定义了 `AiEvolution` 库及 `aievolution` 可执行目标。CI 流程中会自动检测并执行 `lake build` 以验证形式化证明的正确性。
- **桌面客户端 (desktop)**：基于 Tauri + React + Vite 技术栈。通过 `package.json` 中的脚本调用 `vite build` 进行前端资源编译，并利用 `@tauri-apps/cli` 完成原生应用的打包。

### 2. 基础设施与容器化
- **Docker Compose**：在 `infra/docker-compose.yml` 中定义了 PostgreSQL (含 pgvector) 和 Neo4j 服务，用于支撑结构化数据存储、向量检索及知识图谱。配置了健康检查（healthcheck）以确保服务就绪。
- **一键启动脚本**：提供 PowerShell 脚本 (`scripts/startup.ps1`) 实现环境预检（Docker/Python/.env）、容器拉起、服务等待及知识库状态检查的自动化流程。

### 3. 持续集成 (CI)
- **GitHub Actions**：`.github/workflows/test.yml` 配置了自动化测试流水线。在 Ubuntu 环境下安装 Python 依赖，运行 `pytest` 套件，并尝试构建 Lean4 项目。同时包含对 MCP 服务器导入的完整性校验。

### 4. 插件化构建
- **Qoder/Claude 插件**：通过 `scripts/build_plugin.py` 将分散在 `.qoder/skills`、`commands`、`rules` 等目录下的资产自动聚合到 `plugin/` 目录，并打包为符合 IDE 规范的 `.zip` 分发文件。

### 5. 开发者规范
- **版本管理**：各子模块（Python, Lean, Desktop）均独立维护版本号（当前均为 `0.1.0`）。
- **测试约定**：遵循 `pytest.ini` 配置，测试代码位于 `test/` 目录，支持 `slow` 和 `integration` 标记以区分测试类型。
- **环境隔离**：建议通过 `.env` 文件管理敏感配置，并通过 `pip install -e .` 进行开发模式安装以保持全局命令可用。