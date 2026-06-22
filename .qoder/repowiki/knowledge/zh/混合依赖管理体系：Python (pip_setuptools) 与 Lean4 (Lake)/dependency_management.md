## 1. 系统概述
本项目采用**双语言混合依赖管理架构**，分别针对 Python 后端逻辑和 Lean4 形式化验证模块使用不同的包管理工具：
- **Python 部分**：基于 `setuptools` 和 `pip`，通过 `pyproject.toml` 定义项目元数据与核心依赖，辅以 `requirements.txt` 用于快速环境部署。
- **Lean4 部分**：位于 `LEAN/` 子目录，使用 Lean4 官方构建工具 **Lake** 进行依赖解析、版本锁定及编译管理。

## 2. Python 依赖管理
### 核心配置文件
- **`pyproject.toml`**：作为标准的 Python 项目配置入口，声明了构建系统 (`setuptools`)、项目基本信息（名称 `scholar-studio`、版本 `0.1.0`）以及核心运行时依赖。
- **`requirements.txt`**：提供了扁平化的依赖列表，包含核心库（如 `typer`, `rich`, `psycopg2-binary`, `neo4j`）及可选的 MCP 协议支持库。该文件通常用于 CI/CD 或生产环境的确定性安装。

### 依赖策略
- **最小版本约束**：在 `pyproject.toml` 中使用了 `>=` 语法（例如 `typer>=0.9.0`），允许向后兼容的版本更新，但未提供严格的上限锁定（如 `<2.0`），这在长期维护中可能带来兼容性风险。
- **可选依赖组**：通过 `[project.optional-dependencies]` 定义了 `mcp` 和 `all` 组，支持按需安装特定功能模块。
- **缺失锁文件**：项目中未观察到 `poetry.lock` 或 `Pipfile.lock` 等严格的锁文件，依赖版本的确定性主要依赖于 `requirements.txt` 的手动维护或运行时的环境状态。

## 3. Lean4 依赖管理
### 核心配置文件
- **`lakefile.toml`**：定义了 Lean4 项目的基本结构，包括项目名称 `AiEvolution`、版本以及默认构建目标（库 `AiEvolution` 和可执行文件 `aievolution`）。
- **`lake-manifest.json`**：由 Lake 自动生成的**依赖锁文件**。它精确记录了所有传递性依赖的 Git 提交哈希（`rev`）、URL 和输入修订版（`inputRev`），确保了构建的可复现性。
- **`lean-toolchain`**：指定了项目所需的 Lean 工具链版本（当前为 `lean4-local`），确保开发环境与 CI 环境使用一致的编译器版本。

### 依赖来源
- **Git 依赖为主**：Lean4 生态目前高度依赖 Git 仓库。`lake-manifest.json` 显示项目深度依赖 `mathlib` 以及 `leanprover-community` 下的多个社区库（如 `plausible`, `aesop`, `batteries` 等）。
- **路径依赖**：`mathlib` 被配置为 `type: "path"`，表明它可能被本地克隆或通过特定脚本管理，而非直接通过 Git 远程拉取，这通常用于加速大型库的构建或进行本地修改。

## 4. 开发者规范与建议
1. **Python 环境同步**：修改 `pyproject.toml` 后，应同步更新 `requirements.txt` 以保持开发环境与部署环境的一致性。
2. **Lean4 依赖更新**：避免手动编辑 `lake-manifest.json`。应使用 `lake update` 命令来升级依赖，并随后提交更新后的 manifest 文件以锁定新版本。
3. **工具链一致性**：新加入的开发者应确保其 Lean 环境符合 `lean-toolchain` 的要求，可通过 `lake exe cache get` 或相关工具链管理命令进行配置。
4. **私有依赖处理**：目前所有依赖均指向公共 GitHub 仓库。若引入私有库，需配置 Git 凭证或 SSH Key 以确保 Lake 能正常拉取代码。