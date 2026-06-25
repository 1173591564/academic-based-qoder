# Scholar Studio — AI 学术研究助手

基于 Qoder/Claude Code IDE 的学术研究引擎，管理 **581 篇 AI 方向论文**，提供 RAG 语义检索、Neo4j 引用图谱、15 个学术 Skills、Lean4 形式化验证和 311 项自动化测试。

## 核心特性

- **581 篇论文**的结构化知识库（563 篇已解析，16,461 章节，6,940 公式，43,682 引用）
- **15 个学术 Skills**（8 原子 + 7 工作流），覆盖调研→精读→写作→复现全流程
- **双 IDE 支持**：Qoder 和 Claude Code 共享 `.scholar/` 配置源，自动同步
- **45 个 CLI 命令** + **55 个 MCP 工具**，IDE 内对话即可调用
- **三层解耦架构**：核心引擎（IDE 无关）→ MCP 桥接层 → IDE 适配层

## 快速开始

### 方式一：源码开发（推荐）

```bash
git clone <repo-url> && cd academic-based-qoder
pip install -r requirements.txt
# 启动数据库
.\startup.ps1
# 全量初始化（约 40 分钟）
python -m scholar bootstrap
```

在 Qoder 或 Claude Code 中打开项目目录，直接对话使用：

```
你：调研 Transformer 的注意力机制演进
你：精读 2401.04088
你：推荐接下来该读什么
你：scholar doctor          ← 检查配置完整性
```

### 方式二：全局安装

```bash
pip install -e .              # 开发模式安装
scholar init                  # 初始化 ~/.scholar-studio/
scholar stats                 # 验证
cd ~/any-project              # 进入任意项目
scholar init-workspace        # 生成 .qoder/ + .claude/ 配置
scholar doctor                # 验证配置
```

## 架构概览

```
+------------------------------------------------------+
|  .scholar/          Shared config source              |
|  scholar/templates/ Bundled in pip package            |
+---------------------------+--------------------------+
                            |
          sync-ide-config.py / _sync_ide_config()
                            |
                 +----------+----------+
                 v                     v
            .qoder/               .claude/
            (Qoder)               (Claude Code)
                 |                     |
                 +----------+----------+
                            v
+------------------------------------------------------+
|  scholar_mcp/   MCP Server (55 tools, IDE-neutral)   |
|  scholar/       Python CLI (45 commands, IDE-agnostic)|
+---------------------------+--------------------------+
                            v
+------------------------------------------------------+
|  PostgreSQL+pgvector   Neo4j         data/papers/    |
|  (Storage + RAG)       (Citation     (581 papers)    |
|                        Graph)                         |
+------------------------------------------------------+
```

### 三层解耦

| 层次 | 组件 | IDE 依赖 | 说明 |
|------|------|---------|------|
| 核心引擎 | `scholar/` CLI + `scholar_mcp/` | 无 | 45 命令 + 55 MCP 工具，纯 Python |
| 桥接层 | MCP Server (`FastMCP`) | 无 | 标准 MCP 协议，任意 IDE 可接入 |
| 适配层 | `.qoder/` `.claude/` | 有 | 由 `.scholar/` 模板自动生成 |

### 配置同步机制

`.scholar/` 是 single source of truth，包含：

```
.scholar/
  rules/           7 个规则（{IDE_NAME}/{IDE_DIR} 模板变量）
  skills/          15 个 Skills
  commands/        6 个快捷指令
  hooks/           4 个统一 Hook 脚本
  IDE_ENTRY.md     IDE 入口文档模板（生成 CLAUDE.md）
```

同步方式：
- **源码目录**：`python scripts/sync-ide-config.py`
- **全局安装**：`init_workspace()` 内嵌同步逻辑（`_sync_ide_config()`），无需外部脚本
- **CI 门控**：`sync-ide-config.py --check` 检测漂移，exit code 1 表示不一致

## 15 个学术 Skills

### 原子 Skills（8 个）

| Skill | 用途 |
|-------|------|
| `paper-ingestion` | 扫描、解析、导入论文 |
| `math-verification` | Lean4 数学公式验证 |
| `paper-recommendation` | 基于引用网络推荐论文 |
| `citation-network` | 引用网络分析 |
| `research-gap` | 研究空白发现 |
| `review-report` | 同行评审报告 |
| `cold-start` | 新领域入门引导 |
| `experiment-code` | 实验代码生成 |

### 工作流（7 个）

| 工作流 | 链路 |
|--------|------|
| `research-survey` | RAG + 图谱 + 分类 + 时间线 → 调研报告 |
| `paper-deep-dive` | 精读 + 质量评估 + 公式推导 + 实验代码 |
| `writing-pipeline` | 调研 → 撰写 → LaTeX 编译 → 审稿 |
| `reproduce-paper` | 环境配置 → 代码生成 → 运行 → 结果对比 |
| `idea-to-paper` | 调研 → 写作 → 复现 → 成文 |
| `kb-management` | 健康检查 + 数据清理 + 自动更新 |
| `adaptive-research` | 日志分析 → 方向提取 → 飞书推送 → 自动同步 |

## CLI 命令参考

```bash
# 论文库
python -m scholar stats                     # 知识库统计
python -m scholar search "<keyword>"        # 全文搜索
python -m scholar info <paper_id>           # 论文详情
python -m scholar list-papers [--year N]    # 按年份列出
python -m scholar export-bib                # 导出 BibTeX

# 解析与元数据
python -m scholar parse <paper_id>          # 解析单篇
python -m scholar parse-all                 # 批量解析
python -m scholar year-fix [--apply]        # 补全年份
python -m scholar author-fix [--apply]      # 补全作者
python -m scholar metadata-enrich [--apply] # 补全 arxiv_id/DOI

# 图谱（需 Neo4j）
python -m scholar graph-build               # 构建引用+概念图谱
python -m scholar graph-stats               # 图谱统计
python -m scholar cite-network              # 引用网络分析

# RAG 语义搜索（需 API Key）
python -m scholar rag-index                 # 构建向量索引
python -m scholar rag-search "<query>"      # 语义搜索
python -m scholar rag-search "<q>" --hybrid # 混合搜索

# 批处理
python -m scholar auto-notes                # 生成阅读笔记
python -m scholar quality-score --all       # 质量评分
python -m scholar classify --all            # 领域分类

# 知识库更新
python -m scholar arxiv-download "<query>"  # 从 arXiv 下载
python -m scholar kb-update --query "<t>"   # 一键搜索+下载+入库

# 研究循环
python -m scholar interests list            # 查看研究方向
python -m scholar research-sync             # 方向级同步

# 编排
python -m scholar bootstrap                 # 全量初始化
python -m scholar ingest <paper_id>         # 增量导入
python -m scholar survey "<topic>"          # 全量调研

# 诊断
python -m scholar doctor                    # 配置诊断
python -m scholar init                      # 全局初始化
python -m scholar init-workspace            # 工作区初始化
```

## 项目结构

```
.scholar/                共享配置源（rules/skills/hooks/commands 模板）
.qoder/                  Qoder IDE 配置（由 .scholar/ 同步生成）
.claude/                 Claude Code IDE 配置（由 .scholar/ 同步生成）

data/papers/<ULID>/      论文原文（paper.pdf + source.tar.gz）
output/
  parsed/<ULID>.json     563 篇结构化 JSON（核心数据源）
  notes/                 阅读笔记 + 质量评分
  drafts/                写作输出（综述、报告）
  bib/                   BibTeX
  experiments/           实验代码
  digests/               同步报告
  logs/                  对话日志

LEAN/                    Lean4 形式化验证
scholar/                 Python CLI 工具集
  commands/              9 个命令模块
  templates/             包内嵌配置模板（pip install 后可用）
  config.py              配置系统（双模式路径解析）
  db.py                  PostgreSQL 接口
  graph_db.py            Neo4j 图谱操作
  rag.py                 RAG 向量检索
  tex_parser.py          TeX 源码解析器
  id_resolver.py         Hybrid ID 解析（ULID/arXiv/DOI/slug）
scholar_mcp/             MCP Server（55 工具）
scripts/
  sync-ide-config.py     IDE 配置同步脚本
test/                    18 个测试文件，311 项测试
infra/                   Docker 编排（PostgreSQL + Neo4j）
```

## 数据规模

| 指标 | 数值 |
|------|------|
| 论文目录 | 581 |
| TeX 解析 | 563 (97%) |
| 章节 | 16,461 |
| 公式 | 6,940 |
| 引用 | 43,682 |
| 年份覆盖 | 515/563 (91%) |
| 作者覆盖 | 548/563 (97%) |
| 摘要覆盖 | 542/563 (96%) |
| Venue 覆盖 | 554/563 (98%) |

### 领域分布

NLP: 327 | ML: 236 | CV: 95 | Systems: 74 | Safety: 38 | Multimodal: 24 | RL: 22

### Top 会议

NeurIPS (129), ICLR (58), ICML (53), CVPR (41), IEEE (36), Science (36), ACL (27)

## 自动化测试

311 项测试覆盖从单元到端到端的全链路：

```bash
pytest test/ -v                    # 全部测试
pytest test/test_workspace.py -v   # 工作区 + 模板 + 同步一致性
pytest test/test_mcp.py -v         # MCP 工具
pytest test/test_hooks.py -v       # Hook 脚本
pytest test/test_cli.py -v         # CLI 命令
pytest test/test_e2e.py -v         # 端到端流程
```

## 系统要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | CLI + MCP Server |
| Docker Desktop | 4.x+ | PostgreSQL + Neo4j |
| Qoder / Claude Code | 最新 | IDE + Skills + MCP |

## 常见问题

### Docker 启动失败

```bash
docker info                        # 检查 Docker 状态
netstat -ano | findstr "5433"     # 检查端口占用
```

### RAG 搜索无结果

1. 确认 `.env` 中有 `SCHOLAR_EMBEDDING_API_KEY`
2. 确认已运行 `python -m scholar rag-index`
3. 无 API Key 时自动 fallback 到全文搜索

### IDE 配置不一致

```bash
python scripts/sync-ide-config.py          # 重新同步
python scripts/sync-ide-config.py --check  # 检查漂移
python -m scholar doctor                   # 诊断
```
# Scholar Studio — AI 学术研究助手

基于 Qoder/Claude Code IDE 的学术研究引擎，管理 **581 篇 AI 方向论文**，提供 RAG 语义检索、Neo4j 引用图谱、15 个学术 Skills、Lean4 形式化验证和 311 项自动化测试。

## 核心特性

- **581 篇论文**的结构化知识库（563 篇已解析，16,461 章节，6,940 公式，43,682 引用）
- **15 个学术 Skills**（8 原子 + 7 工作流），覆盖调研→精读→写作→复现全流程
- **双 IDE 支持**：Qoder 和 Claude Code 共享 `.scholar/` 配置源，自动同步
- **45 个 CLI 命令** + **55 个 MCP 工具**，IDE 内对话即可调用
- **三层解耦架构**：核心引擎（IDE 无关）→ MCP 桥接层 → IDE 适配层

## 快速开始

### 方式一：源码开发（推荐）

```bash
git clone <repo-url> && cd academic-based-qoder
pip install -r requirements.txt
# 启动数据库
.\startup.ps1
# 全量初始化（约 40 分钟）
python -m scholar bootstrap
```

在 Qoder 或 Claude Code 中打开项目目录，直接对话使用：

```
你：调研 Transformer 的注意力机制演进
你：精读 2401.04088
你：推荐接下来该读什么
你：scholar doctor          ← 检查配置完整性
```

### 方式二：全局安装

```bash
pip install -e .              # 开发模式安装
scholar init                  # 初始化 ~/.scholar-studio/
scholar stats                 # 验证
cd ~/any-project              # 进入任意项目
scholar init-workspace        # 生成 .qoder/ + .claude/ 配置
scholar doctor                # 验证配置
```
+------------------------------------------------------+
|  .scholar/          Shared config source              |
|  scholar/templates/ Bundled in pip package            |
+---------------------------+--------------------------+
                            |
          sync-ide-config.py / _sync_ide_config()
                            |
                 +----------+----------+
                 v                     v
            .qoder/               .claude/
            (Qoder)               (Claude Code)
                 |                     |
                 +----------+----------+
                            v
+------------------------------------------------------+
|  scholar_mcp/   MCP Server (55 tools, IDE-neutral)   |
|  scholar/       Python CLI (45 commands, IDE-agnostic)|
+---------------------------+--------------------------+
                            v
+------------------------------------------------------+
|  PostgreSQL+pgvector   Neo4j         data/papers/    |
|  (Storage + RAG)       (Citation     (581 papers)    |
|                        Graph)                         |
+------------------------------------------------------+
```
┌──────────────────────────────────────────────────────┐
│  .scholar/          共享配置源（rules/skills/hooks）    │
│  scholar/templates/ 包内嵌副本（pip install 后可用）    │
└──────────────┬───────────────────────────────────────┘
               │ sync-ide-config.py / _sync_ide_config()
       ┌───────┴───────┐
       ▼               ▼
  .qoder/          .claude/           ← IDE 适配层（自动生成）
  (Qoder)          (Claude Code)
       │               │
       └───────┬───────┘
               ▼
┌──────────────────────────────────────────────────────┐
│  scholar_mcp/    MCP Server（55 工具，IDE 中立）       │
│  scholar/        Python CLI（45 命令，IDE 无关）        │
└──────────────┬───────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector    Neo4j    data/papers/       │
│  (结构化存储 + RAG)    (引用图谱)   (581 篇论文)       │
└──────────────────────────────────────────────────────┘
```

### 三层解耦

| 层次 | 组件 | IDE 依赖 | 说明 |
|------|------|---------|------|
| 核心引擎 | `scholar/` CLI + `scholar_mcp/` | 无 | 45 命令 + 55 MCP 工具，纯 Python |
| 桥接层 | MCP Server (`FastMCP`) | 无 | 标准 MCP 协议，任意 IDE 可接入 |
| 适配层 | `.qoder/` `.claude/` | 有 | 由 `.scholar/` 模板自动生成 |

### 配置同步机制

`.scholar/` 是 single source of truth，包含：

```
.scholar/
  rules/           7 个规则（{IDE_NAME}/{IDE_DIR} 模板变量）
  skills/          15 个 Skills
  commands/        6 个快捷指令
  hooks/           4 个统一 Hook 脚本
  IDE_ENTRY.md     IDE 入口文档模板（生成 CLAUDE.md）
```

同步方式：
- **源码目录**：`python scripts/sync-ide-config.py`
- **全局安装**：`init_workspace()` 内嵌同步逻辑（`_sync_ide_config()`），无需外部脚本
- **CI 门控**：`sync-ide-config.py --check` 检测漂移，exit code 1 表示不一致

## 15 个学术 Skills

### 原子 Skills（8 个）

| Skill | 用途 |
|-------|------|
| `paper-ingestion` | 扫描、解析、导入论文 |
| `math-verification` | Lean4 数学公式验证 |
| `paper-recommendation` | 基于引用网络推荐论文 |
| `citation-network` | 引用网络分析 |
| `research-gap` | 研究空白发现 |
| `review-report` | 同行评审报告 |
| `cold-start` | 新领域入门引导 |
| `experiment-code` | 实验代码生成 |

### 工作流（7 个）

| 工作流 | 链路 |
|--------|------|
| `research-survey` | RAG + 图谱 + 分类 + 时间线 → 调研报告 |
| `paper-deep-dive` | 精读 + 质量评估 + 公式推导 + 实验代码 |
| `writing-pipeline` | 调研 → 撰写 → LaTeX 编译 → 审稿 |
| `reproduce-paper` | 环境配置 → 代码生成 → 运行 → 结果对比 |
| `idea-to-paper` | 调研 → 写作 → 复现 → 成文 |
| `kb-management` | 健康检查 + 数据清理 + 自动更新 |
| `adaptive-research` | 日志分析 → 方向提取 → 飞书推送 → 自动同步 |

## CLI 命令参考

```bash
# 论文库
python -m scholar stats                     # 知识库统计
python -m scholar search "<keyword>"        # 全文搜索
python -m scholar info <paper_id>           # 论文详情
python -m scholar list-papers [--year N]    # 按年份列出
python -m scholar export-bib                # 导出 BibTeX

# 解析与元数据
python -m scholar parse <paper_id>          # 解析单篇
python -m scholar parse-all                 # 批量解析
python -m scholar year-fix [--apply]        # 补全年份
python -m scholar author-fix [--apply]      # 补全作者
python -m scholar metadata-enrich [--apply] # 补全 arxiv_id/DOI

# 图谱（需 Neo4j）
python -m scholar graph-build               # 构建引用+概念图谱
python -m scholar graph-stats               # 图谱统计
python -m scholar cite-network              # 引用网络分析

# RAG 语义搜索（需 API Key）
python -m scholar rag-index                 # 构建向量索引
python -m scholar rag-search "<query>"      # 语义搜索
python -m scholar rag-search "<q>" --hybrid # 混合搜索

# 批处理
python -m scholar auto-notes                # 生成阅读笔记
python -m scholar quality-score --all       # 质量评分
python -m scholar classify --all            # 领域分类

# 知识库更新
python -m scholar arxiv-download "<query>"  # 从 arXiv 下载
python -m scholar kb-update --query "<t>"   # 一键搜索+下载+入库

# 研究循环
python -m scholar interests list            # 查看研究方向
python -m scholar research-sync             # 方向级同步

# 编排
python -m scholar bootstrap                 # 全量初始化
python -m scholar ingest <paper_id>         # 增量导入
python -m scholar survey "<topic>"          # 全量调研

# 诊断
python -m scholar doctor                    # 配置诊断
python -m scholar init                      # 全局初始化
python -m scholar init-workspace            # 工作区初始化
```

## 项目结构

```
.scholar/                共享配置源（rules/skills/hooks/commands 模板）
.qoder/                  Qoder IDE 配置（由 .scholar/ 同步生成）
.claude/                 Claude Code IDE 配置（由 .scholar/ 同步生成）

data/papers/<ULID>/      论文原文（paper.pdf + source.tar.gz）
output/
  parsed/<ULID>.json     563 篇结构化 JSON（核心数据源）
  notes/                 阅读笔记 + 质量评分
  drafts/                写作输出（综述、报告）
  bib/                   BibTeX
  experiments/           实验代码
  digests/               同步报告
  logs/                  对话日志

LEAN/                    Lean4 形式化验证
scholar/                 Python CLI 工具集
  commands/              9 个命令模块
  templates/             包内嵌配置模板（pip install 后可用）
  config.py              配置系统（双模式路径解析）
  db.py                  PostgreSQL 接口
  graph_db.py            Neo4j 图谱操作
  rag.py                 RAG 向量检索
  tex_parser.py          TeX 源码解析器
  id_resolver.py         Hybrid ID 解析（ULID/arXiv/DOI/slug）
scholar_mcp/             MCP Server（55 工具）
scripts/
  sync-ide-config.py     IDE 配置同步脚本
test/                    18 个测试文件，311 项测试
infra/                   Docker 编排（PostgreSQL + Neo4j）
```

## 数据规模

| 指标 | 数值 |
|------|------|
| 论文目录 | 581 |
| TeX 解析 | 563 (97%) |
| 章节 | 16,461 |
| 公式 | 6,940 |
| 引用 | 43,682 |
| 年份覆盖 | 515/563 (91%) |
| 作者覆盖 | 548/563 (97%) |
| 摘要覆盖 | 542/563 (96%) |
| Venue 覆盖 | 554/563 (98%) |

### 领域分布

NLP: 327 | ML: 236 | CV: 95 | Systems: 74 | Safety: 38 | Multimodal: 24 | RL: 22

### Top 会议

NeurIPS (129), ICLR (58), ICML (53), CVPR (41), IEEE (36), Science (36), ACL (27)

## 自动化测试

311 项测试覆盖从单元到端到端的全链路：

```bash
pytest test/ -v                    # 全部测试
pytest test/test_workspace.py -v   # 工作区 + 模板 + 同步一致性
pytest test/test_mcp.py -v         # MCP 工具
pytest test/test_hooks.py -v       # Hook 脚本
pytest test/test_cli.py -v         # CLI 命令
pytest test/test_e2e.py -v         # 端到端流程
```

## 系统要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | CLI + MCP Server |
| Docker Desktop | 4.x+ | PostgreSQL + Neo4j |
| Qoder / Claude Code | 最新 | IDE + Skills + MCP |

## 常见问题

### Docker 启动失败

```bash
docker info                        # 检查 Docker 状态
netstat -ano | findstr "5433"     # 检查端口占用
```

### RAG 搜索无结果

1. 确认 `.env` 中有 `SCHOLAR_EMBEDDING_API_KEY`
2. 确认已运行 `python -m scholar rag-index`
3. 无 API Key 时自动 fallback 到全文搜索

### IDE 配置不一致

```bash
python scripts/sync-ide-config.py          # 重新同步
python scripts/sync-ide-config.py --check  # 检查漂移
python -m scholar doctor                   # 诊断
```
