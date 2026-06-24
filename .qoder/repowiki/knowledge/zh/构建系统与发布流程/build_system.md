## 1. 核心构建体系
项目采用 **多语言混合构建** 策略，主要包含 Python 后端、Lean4 形式化验证模块以及 Tauri 桌面前端。

*   **Python 后端 (`scholar/`)**：基于 `pyproject.toml` (setuptools) 进行依赖管理和包定义。通过 `scripts/build_exe.py` 调用 **PyInstaller** 将 CLI 工具打包为 Windows 可执行文件 (`scholar.exe`)，支持 `onedir`（推荐）和 `onefile` 两种模式。
*   **Lean4 模块 (`LEAN/`)**：使用 **Lake** 作为构建工具，通过 `lakefile.toml` 定义库与可执行目标。CI 流程中会尝试运行 `lake build` 进行编译验证。
*   **桌面端 (`desktop/`)**：基于 **Tauri + Vite + React**。通过 `package.json` 管理脚本，使用 `tauri` CLI 进行桌面应用的开发与打包。

## 2. 自动化测试与 CI
*   **GitHub Actions**：配置了 `.github/workflows/test.yml`，在 `ubuntu-latest` 环境下针对 Python 3.11 运行自动化测试。
*   **测试框架**：使用 **pytest**，配置文件位于 `pytest.ini`。测试套件涵盖单元测试、集成测试及 MCP 服务器导入验证。
*   **环境初始化**：CI 步骤中包含自动安装开发依赖 (`pip install -e ".[dev]"`) 并运行全量测试。

## 3. 基础设施与容器化
*   **Docker Compose**：`infra/docker-compose.yml` 定义了研发所需的基础设施服务，包括 **PostgreSQL (pgvector)** 用于向量检索和 **Neo4j** 用于知识图谱存储。
*   **启动脚本**：提供 `scripts/startup.ps1` 等 PowerShell 脚本，用于在 Windows 环境下快速拉起本地开发环境。

## 4. 开发者规范
*   **依赖管理**：所有 Python 依赖应在 `pyproject.toml` 中声明。开发环境建议使用 `pip install -e .` 进行链接安装。
*   **打包约定**：若需分发独立 CLI 工具，应使用 `python scripts/build_exe.py`。PyInstaller 的隐藏导入列表在 `scripts/scholar.spec` 中维护，新增子模块时需同步更新。
*   **版本控制**：当前项目版本统一标记为 `0.1.0`，分布在 `pyproject.toml`、`desktop/package.json` 及 `LEAN/lakefile.toml` 中。