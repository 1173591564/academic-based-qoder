该项目采用**混合构建体系**，同时管理 Python 应用（Scholar Studio）和 Lean4 形式化验证库（AiEvolution）。

### 1. Python 应用构建 (Scholar Studio)
- **依赖与包管理**：基于 `pyproject.toml` 使用 `setuptools` 进行标准化管理。定义了核心依赖（如 `typer`, `rich`, `psycopg2-binary`）及可选依赖（MCP 支持）。
- **可执行文件打包**：通过 `build_exe.py` 脚本驱动 **PyInstaller** 实现跨平台分发。
  - **模式选择**：支持 `onedir`（默认，启动快、易调试）和 `--onefile`（单文件，便于分发）两种模式。
  - **配置策略**：使用 `scholar.spec` 显式声明 `hiddenimports`（解决动态导入问题）和 `excludes`（剔除 matplotlib, torch 等重型未使用库以减小体积）。
  - **全局安装**：支持 `python build_exe.py --install` 通过 `pip install -e .` 将 CLI 命令注册到系统环境。
- **插件构建**：`build_plugin.py` 负责将 `.qoder` 目录下的 Skills、Commands、Rules 和 Hooks 聚合到 `plugin/` 目录，并根据 `plugin.json` 中的版本号自动打包为 `scholar-studio-{version}.zip` 供 Qoder IDE 安装。

### 2. Lean4 形式化验证构建 (AiEvolution)
- **构建工具**：使用 Lean4 官方构建工具 **Lake**。
- **配置**：`LEAN/lakefile.toml` 定义了库名 `AiEvolution` 和可执行目标 `aievolution`。
- **CI 集成**：通过 `.github/workflows/lean_action_ci.yml` 配置了 GitHub Actions，在 push 或 PR 时自动触发 `leanprover/lean-action@v1` 进行编译和验证。

### 3. 基础设施与环境编排
- **容器化部署**：`infra/docker-compose.yml` 定义了开发/运行所需的基础设施服务：
  - **PostgreSQL + pgvector**：用于结构化数据存储及 RAG 向量检索（端口 5433）。
  - **Neo4j**：用于构建概念图谱和引用网络（端口 7474/7687），并启用了 APOC 插件。
- **初始化脚本**：通过 `init.sql` 自动初始化数据库 schema。

### 4. 测试体系
- **框架**：使用 `pytest`，配置见 `pytest.ini`。
- **标记**：定义了 `slow`（网络/编译相关）和 `integration`（需运行服务）标记，便于分层执行测试。

### 开发者指南
- **构建 EXE**：运行 `python build_exe.py`。
- **构建插件**：运行 `python build_plugin.py`。
- **启动依赖服务**：在 `infra/` 目录下运行 `docker-compose up -d`。
- **运行测试**：执行 `pytest` 或 `pytest -m "not slow and not integration"` 进行快速单元测试。