# Scholar Studio — AI 学术研究助手

基于 Qoder IDE 的学术研究引擎，管理 **570 篇 AI 方向论文**，提供 RAG 语义检索、Neo4j 引用图谱、15 个学术 skills（8 原子 + 7 工作流）、Lean4 形式化验证、Adaptive Research Loop（自适应研究闭环）和 121 项自动化测试。

> **核心理念**：把 570 篇论文的 TeX 源码变成可查询、可推理、可组合的学术数据层，然后通过 Qoder Agent + Skills + Hooks 自动化完成调研→精读→对比→写作→追踪的全流程。

---

## 从零开始：5 分钟搭建

### 系统要求

| 组件 | 最低版本 | 用途 | 安装 |
|------|---------|------|------|
| Docker Desktop | 4.x+ | PostgreSQL + Neo4j 容器 | [下载](https://www.docker.com/products/docker-desktop/) |
| Python | 3.10+ | CLI 工具集 + MCP Server | [下载](https://www.python.org/downloads/) |
| Qoder IDE | 最新版 | Agent + Skills + MCP 集成 | [下载](https://qoder.com/) |
| Git | 任意版本 | 代码版本管理 | [下载](https://git-scm.com/) |

> **Windows 用户注意**：如果同时使用 VMware，Docker Desktop 的 WSL2 后端可能冲突。启动 Docker 前确保 WSL2 已启用：`wsl --set-default-version 2`

### Step 1: 克隆仓库

```bash
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder
```

### Step 2: 安装 Python 依赖

```bash
# 推荐先创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：

| 包 | 用途 |
|---|------|
| `typer` + `rich` | CLI 框架 + 终端美化输出 |
| `psycopg2-binary` | PostgreSQL 连接 |
| `neo4j` | Neo4j 图数据库驱动 |
| `python-dotenv` | 环境变量加载 |
| `PyMuPDF` | PDF 论文处理 |
| `mcp` | MCP Server 协议（Qoder 集成） |

### Step 3: 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 智谱 embedding API（RAG 语义搜索必需）
# 获取方式：https://open.bigmodel.cn/ → 注册 → API Keys
SCHOLAR_EMBEDDING_API_KEY=your_api_key_here
```

> **没有 API Key 也能用**：只是 RAG 语义搜索不可用，全文搜索、图谱分析、Skills 执行都正常。
>
> 数据库密码**不需要**放在 `.env` 中，由 Docker 容器内部管理（见 `infra/docker-compose.yml`）。

### Step 4: 启动数据库

```powershell
.\startup.ps1
```

脚本自动完成：
1. 启动 Docker 容器（`infra/docker-compose.yml`）
2. 等待 PostgreSQL（端口 **5433**）和 Neo4j（端口 **7474/7687**）健康检查通过
3. 显示当前知识库统计

容器信息：

| 容器 | 镜像 | 端口 | 凭证 |
|------|------|------|------|
| `scholar-pg` | `pgvector/pgvector:pg16` | 5433 | scholar / scholar2024 |
| `scholar-neo4j` | `neo4j:5-community` | 7474, 7687 | neo4j / scholar2024 |

> 端口 5433 而非常规 5432，避免与本地已安装的 PostgreSQL 冲突。

### Step 5: 全量初始化（Bootstrap）

```bash
python -m scholar bootstrap
```

Bootstrap 按顺序执行 **9 步**，全程约 **40 分钟**：

| # | 命令 | 产出 | 耗时 |
|---|------|------|------|
| 1 | `parse-all` | 570 篇论文的 TeX → JSON | ~5 min |
| 2 | `year-fix` | 补全缺失年份（交叉引用 Lean4 + arXiv API） | ~1 min |
| 3 | `author-fix` | 补全缺失作者（arXiv API） | ~1 min |
| 4 | `graph-build` | Neo4j 图谱（论文 + 概念 + Lean4 关系） | ~3 min |
| 5 | PG sync | PostgreSQL 写入 sections/formulas/citations | ~2 min |
| 6 | `rag-index` | 向量索引（需 API Key） | ~30 min |
| 7 | `auto-notes` | 自动生成 556 份阅读笔记 | ~3 min |
| 8 | `quality-score` | 534 篇论文 7 维度评分 | ~2 min |
| 9 | `classify` | 555 篇论文领域分类 | ~1 min |

> **断点续传**：如果中途中断，重新运行 `bootstrap` 会自动跳过已完成的步骤。

### Step 6: 在 Qoder 中打开

1. 用 Qoder 打开项目目录
2. Qoder 自动读取 `.qoder/mcp.json`，后台启动 **Scholar MCP Server**（43 个工具）
3. 在对话框中直接开始使用

### Step 7: 验证一切正常

在 Qoder 对话框中输入：

```
你：查看知识库状态
```

或直接在终端运行：

```bash
python -m scholar stats
```

期望输出：

```
╭────────────────────── Knowledge Base Stats ───────────────────────╮
│ Paper folders:   570                                              │
│ Parsed:          555                                              │
│ Total sections:  16344                                            │
│ Total formulas:  6776                                             │
│ Total citations: 43397                                            │
│ Database:        connected                                        │
│                                                                   │
│ Metadata Coverage:                                                │
│   Year:      457/555 (82%)                                        │
│   Authors:   540/555 (97%)                                        │
│   Abstract:  534/555 (96%)                                        │
│   Venue:     475/555 (85%)                                        │
╰───────────────────────────────────────────────────────────────────╯
```

---

## 快速开始（已部署用户）

### 启动数据库

```powershell
.\startup.ps1
```

### 对话即可使用

```
你：调研 Transformer 的注意力机制演进
你：精读 2401.04088                  ← 支持 arXiv ID / DOI / ULID / 关键词
你：帮我写一篇 Attention 方向的论文
你：复现 LoRA 论文的实验
你：分析 RLHF 和 DPO 的研究空白
你：入门 State Space Model
你：推荐接下来该读什么
你：维护知识库
你：研究循环                        ← 触发 Adaptive Research Loop
```

### 一键开始（Deeplinks）

点击链接直接唤起 Qoder 并开始任务：

| 工作流 | 一键入口 | 说明 |
|--------|----------|------|
| 文献调研 | [调研 Transformer](qoder://aicoding.aicoding-deeplink/chat?text=%E8%B0%83%E7%A0%94+Transformer+%E6%B3%A8%E6%84%8F%E5%8A%9B%E6%9C%BA%E5%88%B6%E7%9A%84%E5%8F%91%E5%B1%95%E5%8E%86%E7%A8%8B%EF%BC%8C%E6%8C%89%E6%97%B6%E9%97%B4%E7%BA%BF%E6%95%B4%E7%90%86%E5%85%B3%E9%94%AE%E8%AE%BA%E6%96%87&mode=agent) | RAG + 图谱 + 时间线 → 调研报告 |
| 深度分析 | [精读 Attention Is All You Need](qoder://aicoding.aicoding-deeplink/chat?text=%E7%B2%BE%E8%AF%BB%E8%AE%BA%E6%96%87+01KT6MTBBH03MN0Z6PK902XKC2+%28Attention+Is+All+You+Need%29%EF%BC%8C%E8%BE%93%E5%87%BA%E7%BB%93%E6%9E%84%E5%8C%96%E5%88%86%E6%9E%90&mode=agent) | 精读 + 质量评估 + 公式推导 + 实验代码 |
| 学术写作 | [写 Attention 方向的论文](qoder://aicoding.aicoding-deeplink/chat?text=%E5%B8%AE%E6%88%91%E5%86%99%E4%B8%80%E7%AF%87+Attention+Mechanism+%E6%96%B9%E5%90%91%E7%9A%84%E8%AE%BA%E6%96%87&mode=agent) | 调研 → 撰写 → LaTeX 编译 → 审稿 |
| 实验复现 | [复现 LoRA 论文](qoder://aicoding.aicoding-deeplink/chat?text=%E5%A4%8D%E7%8E%B0+LoRA+%E8%AE%BA%E6%96%87%E7%9A%84%E5%AE%9E%E9%AA%8C%EF%BC%8C%E7%94%9F%E6%88%90%E4%BB%A3%E7%A0%81%E5%B9%B6%E8%BF%90%E8%A1%8C&mode=agent) | 环境配置 → 代码生成 → 运行 → 结果对比 |
| 研究空白 | [RLHF 研究空白](qoder://aicoding.aicoding-deeplink/chat?text=%E5%88%86%E6%9E%90+RLHF+%E5%92%8C+DPO+%E6%96%B9%E5%90%91%E7%9A%84%E7%A0%94%E7%A9%B6%E7%A9%BA%E7%99%BD%E5%92%8C%E6%9C%AA%E6%9D%A5%E6%96%B9%E5%90%91&mode=agent) | 跨论文局限性分析 → 研究缺口报告 |
| 领域入门 | [入门 State Space Model](qoder://aicoding.aicoding-deeplink/chat?text=%E5%85%A5%E9%97%A8+State+Space+Model%EF%BC%8C%E5%BB%BA%E7%AB%8B%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E5%92%8C%E5%AD%A6%E4%B9%A0%E8%B7%AF%E5%BE%84&mode=agent) | 构建知识地图 + 学习路径 |
| 论文推荐 | [推荐接下来该读什么](qoder://aicoding.aicoding-deeplink/chat?text=%E6%A0%B9%E6%8D%AE%E6%88%91%E7%9A%84%E7%9F%A5%E8%AF%86%E5%BA%93%EF%BC%8C%E6%8E%A8%E8%8D%90%E6%8E%A5%E4%B8%8B%E6%9D%A5%E8%AF%A5%E8%AF%BB%E5%93%AA%E4%BA%9B%E8%AE%BA%E6%96%87&mode=agent) | 基于引用网络 + 阅读缺口推荐 |
| 知识库维护 | [维护知识库](qoder://aicoding.aicoding-deeplink/chat?text=%E6%A3%80%E6%9F%A5%E7%9F%A5%E8%AF%86%E5%BA%93%E5%81%A5%E5%BA%B7%E7%8A%B6%E6%80%81%E5%B9%B6%E6%B8%85%E7%90%86%E6%95%B0%E6%8D%AE&mode=agent) | 健康检查 + 数据清理 + 自动更新 |

---

## 15 个学术 Skills

在 Qoder 对话中直接使用，或输入 `/skill-name` 触发：

### 原子 Skills（8 个）

| 类别 | Skill | 用法示例 |
|------|-------|--------|
| **论文管理** | `paper-ingestion` | "导入新论文" |
| **数学验证** | `math-verification` | "用 Lean4 验证这个定理" |
| **论文推荐** | `paper-recommendation` | "推荐接下来该读什么" |
| **引用分析** | `citation-network` | "分析 NLP 领域的引用网络" |
| **研究缺口** | `research-gap` | "找 RLHF 方向的研究空白" |
| **审稿报告** | `review-report` | "写一篇审稿报告" |
| **入门引导** | `cold-start` | "入门 State Space Model" |
| **实验代码** | `experiment-code` | "复现 LoRA 的实验代码" |

每个 skill 末尾都有 **Next Steps** 引导，执行完后自动建议下一步操作。

### 工作流（7 个）

串联多个原子 skill，自动传递数据，一键完成完整研究流程：

| Workflow | 链路 | 用法示例 |
|----------|------|--------|
| `research-survey` | RAG + 图谱 + 分类 + 时间线 | "调研 Diffusion Model 的发展历程" |
| `paper-deep-dive` | 精读 + 质量 + 推导 + 代码 | "深度分析 Attention Is All You Need" |
| `writing-pipeline` | 调研 → 撰写 → 编译 → 审稿 | "帮我写一篇论文" |
| `reproduce-paper` | 环境 → 代码 → 运行 → 对比 | "复现这篇论文的实验" |
| `idea-to-paper` | 调研 → 写作 → 复现 → 成文 | "我有一个想法" |
| `kb-management` | 健康检查 + 自动更新 + 入库 | "维护知识库" |
| `adaptive-research` | 日志分析 + 方向提取 + 飞书推送 + 自动同步 | "研究循环" |

---

## Adaptive Research Loop

自适应研究闭环是本系统的核心差异化能力——从被动记录到主动发现到自动入库：

```
日常使用 Qoder 做研究（调研/精读/写作/复现）
         ↓
  Stop Hook 自动采集查询 → week-*.jsonl     [log-conversation.ps1]
         ↓
  定时任务分析日志提取方向                    [Qoder Work 定时任务]
         ↓
  飞书推送新方向待确认                        [Qoder Work 飞书连接器]
         ↓
  用户回复确认                               [飞书 IM 内直接回复]
         ↓
  sync-direction 自动下载 + 全流程入库        [research-sync CLI]
         ↓
  新论文进入知识库，等待下一轮循环
```

### 研究方向管理

```bash
python -m scholar interests list                # 查看研究方向
python -m scholar interests add --keywords "..." --category "..."  # 添加方向
python -m scholar interests remove --category "..."  # 删除方向
python -m scholar interests logs                # 查看未分析的对话日志
python -m scholar research-sync --category "..." --max 10  # 方向级同步
```

### Qoder Work 定时任务

在 Qoder Work 中配置每周定时任务，自动执行日志分析 → 方向提取 → 飞书推送，实现全链路闭环。

---

## Architecture Overview

```
+=====================================================================+
|                          Qoder IDE                                   |
|                                                                      |
|   +-----------+    +------------+    +--------------------------+    |
|   |  7 Rules  |    | 15 Skills  |    |  3 Hooks + 6 Commands    |    |
|   | (always)  |    | (SKILL.md) |    |  (automation/shortcuts)  |    |
|   +-----+-----+    +-----+------+    +--------------------------+    |
|         |                |                                             |
|         +-------+--------+                                             |
|                 |                                                      |
|                 v                                                      |
|   +-----------------------------------------------------------------+ |
|   |           Scholar MCP Server  (43 tools)                        | |
|   |           Qoder <-> CLI bridge layer                            | |
|   +------------------------------+----------------------------------+ |
+==================================|====================================+
                                   |  CLI commands
                                   v
+---------------------------------------------------------------------+
|                    scholar/ Python CLI  (39 commands)                |
|                                                                      |
|    cli.py (entry) <--- _shared.py (app / console / parser / _get_db)|
|        |                                                             |
|        v                                                             |
|    commands/                                                         |
|      +-- core_ops.py ........ init, scan, info, search, stats       |
|      +-- paper_ops.py ....... parse, parse-all, ingest, export-bib  |
|      +-- metadata_ops.py .... year-fix, author-fix, venue-fix       |
|      +-- graph_ops.py ....... graph-build, graph-stats, cite-*      |
|      +-- rag_ops.py ......... rag-index, rag-search                 |
|      +-- batch_ops.py ....... auto-notes, quality, classify, kb-*   |
|      +-- research_ops.py .... interests, research-sync, survey      |
|      +-- execution_ops.py ... compile-paper, exp-run/compare/setup  |
|      +-- external_ops.py .... arxiv-search, arxiv-download          |
|                                                                      |
|    Domain Modules:                                                   |
|      config.py | tex_parser.py | db.py | graph_db.py | rag.py       |
+------+----------------------------+------------------+--------------+
       |                            |                  |
       v                            v                  v
+----------------+    +------------------+    +------------------+
|  PostgreSQL    |    |      Neo4j       |    |  data/papers/    |
|  + pgvector    |    |  Citation Graph  |    |  570 Papers      |
|  port 5433     |    |  Concept Graph   |    |  (PDF + TeX)     |
+----------------+    |  port 7474/7687  |    +------------------+
                      +------------------+

+=====================================================================+
|                       Qoder Work  (Scheduled Tasks)                  |
|                                                                      |
|   Log Analysis --> Direction Extraction --> Feishu Push --> Confirm  |
|                                                           --> Sync   |
+=====================================================================+
```

### Data Flow

```
Paper TeX Sources -----> parse -----> JSON (parsed/<ULID>.json)
    |                        |
    v                        v
PostgreSQL               Neo4j
 (sections,               (papers, concepts,
  formulas,                REPLACES relations)
  citations)
    |
    v
RAG Vector Index (Zhipu embedding-2, HNSW)

Conversation Logs --> week-*.jsonl --> Direction Extraction --> interests.json
                                                                  |
                                                    Feishu Push --> Confirm --> Auto-Ingest
```

### Output Directory (Project-Isolated)

Drafts and logs under `output/` are auto-partitioned by project name:

```
output/
  drafts/<project_name>/    <-- survey / landscape reports (per-project)
  logs/<project_name>/      <-- conversation logs (cross-project capture)
  parsed/                   <-- shared globally (one knowledge base)
  notes/                    <-- shared globally
```

---

## CLI 命令参考

全局安装后，在任意目录直接使用 `scholar` 命令：

```bash
# 全局安装（一次配置，处处可用）
pip install -e .              # 开发模式
# 或
python build_exe.py           # 打包为独立 scholar.exe

# 论文库
scholar stats                     # 知识库统计
scholar search "attention"        # 全文搜索
scholar list-papers --year 2024   # 按年份列出
scholar info <paper_id>           # 论文详情（支持 ULID/arXiv/DOI/slug）
scholar export-bib                # 导出 BibTeX

# 图谱查询（需 Neo4j 运行）
python -m scholar graph-stats               # 图谱统计
python -m scholar graph-query "attention"   # 概念查询
python -m scholar cite-network              # 全局引用网络
python -m scholar cite-network <paper_id>   # 单篇前后向引用

# 语义搜索（需 RAG 索引 + API Key）
python -m scholar rag-search "query"        # 向量搜索
python -m scholar rag-search "q" --hybrid   # 混合搜索（向量+BM25+RRF）

# 批处理
python -m scholar auto-notes                # 生成全部阅读笔记
python -m scholar quality-score --all       # 7 维度评分（A-F）
python -m scholar classify --all            # 领域/子领域/方法分类

# 研究循环
python -m scholar interests list            # 查看研究方向
python -m scholar interests logs            # 查看未分析日志
python -m scholar research-sync             # 方向级同步

# KB 更新（arXiv 下载 + 全流程入库）
python -m scholar arxiv-download "<query>" [--max 10] [--pdf]
python -m scholar batch-ingest [--ulids "id1,id2"]
python -m scholar kb-update --query "<topic>" --max 10

# 编排
python -m scholar bootstrap                 # 全量初始化（首次部署）
python -m scholar ingest <paper_id>         # 增量导入单篇

# 外部
python -m scholar arxiv-search "query"      # 搜索 arXiv

# 测试
cd test && pytest                           # 运行 121 项自动化测试
```

---

## 项目结构

```
.qoder/
  rules/           7 个 Agent 规则（identity, pipelines, tools, academic, onboarding, memory-policy, interest-capture）
  skills/          15 个学术 skills（8 原子 + 7 工作流）
  commands/        6 个快捷指令（stats, find, paper, health, resume, sync）
  hooks/           3 个自动化钩子（log-conversation + task-done + block-dangerous）
  settings.json    Hooks 配置
  mcp.json         MCP Server 配置

data/papers/       570 篇论文（每篇：paper.pdf + source.tar.gz）
output/
  parsed/          555 篇结构化 JSON（核心数据源，全局共享）
  notes/           556 份阅读笔记 + 534 份质量评分 JSON（全局共享）
  drafts/<project>/  综述、Related Work、报告（按项目隔离）
  bib/             BibTeX 文件
  experiments/     实验代码复现
  digests/         研究同步报告
  logs/<project>/  对话日志（按项目隔离，跨 Qoder 项目采集）
  research-interests.json  研究方向画像

LEAN/              Lean4 形式化验证（125 创新节点 + 7 定理）
scholar/           Python CLI 工具集（39 命令）
  _shared.py       共享对象（app, console, parser, _get_db）
  cli.py           入口文件（导入 _shared + 命令模块）
  commands/        9 个命令模块（按功能分组，消除循环导入）
    core_ops.py       init, scan, info, search, list-papers, stats
    paper_ops.py      parse, parse-all, ingest, export-bib
    metadata_ops.py   year-fix, author-fix, venue-fix, metadata-enrich
    graph_ops.py      graph-build, graph-stats, graph-query, cite-network, cite-resolve
    rag_ops.py        rag-index, rag-search
    batch_ops.py      auto-notes, quality-score, classify, bootstrap, batch-ingest, kb-update
    research_ops.py   interests, research-sync, survey, landscape
    execution_ops.py  compile-paper, exp-run, exp-compare, exp-setup, exp-debug, dataset-download
    external_ops.py   arxiv-search, arxiv-download
  config.py        双模式配置（dev → 源码目录 / frozen → ~/.scholar-studio/）
  tex_parser.py    TeX 源码解析器
  db.py            PostgreSQL 接口
  graph_db.py      Neo4j 图谱操作
  rag.py           RAG 向量检索
  ...              其他领域模块
scholar_mcp/       MCP Server（43 工具，Qoder 桥接层）
test/              自动化测试套件（8 个文件，121 项测试）
  conftest.py      共享 fixtures
  test_config.py   配置路径与环境变量
  test_id_resolver.py  Hybrid ID 解析器
  test_research_loop.py  研究循环逻辑
  test_kb_update.py  KB 更新流程
  test_db.py       数据库层操作
  test_cli.py      CLI 集成测试（smoke + execution + error）
  test_hooks.py    Hook 脚本逻辑验证
  test_e2e.py      端到端全流程测试
infra/             Docker 编排（PostgreSQL + Neo4j）
  docker-compose.yml
  init.sql         PostgreSQL 建表脚本（papers, sections, formulas, citations, chunks）

# 打包与分发
build_exe.py       PyInstaller 一键构建脚本
scholar.spec       PyInstaller 配置文件
scholar_cli.py     PyInstaller 独立入口脚本
pyproject.toml     包元数据 + console_scripts 入口点

plugin/            Qoder Plugin 分发版
```

---

## 数据规模

| 数据层 | 数量 |
|--------|------|
| 论文目录 | 570 |
| TeX 解析 | 555 篇（97.4%） |
| Sections | 16,344 |
| Formulas | 6,776 |
| Citations | 43,397 |
| 阅读笔记 | 556 |
| 质量评分 | 534 |
| 领域分类 | 555 |
| 年份覆盖 | 510/555 (91%) |
| 作者覆盖 | 540/555 (97%) |
| 摘要覆盖 | 534/555 (96%) |
| Venue 覆盖 | 548/555 (98%) |

### 领域分布

| Domain | 论文数 |
|--------|--------|
| NLP | 327 |
| ML | 236 |
| CV | 95 |
| Systems | 74 |
| Safety | 38 |
| Multimodal | 24 |
| RL | 22 |

> 论文可属于多个领域（多标签分类）

### Top 会议来源

NeurIPS (129), ICLR (58), ICML (53), CVPR (39), IEEE (36), Science (35), ACL (27), ACM (15), arXiv (15), SIGGRAPH (13)

---

## 自动化测试

121 项测试覆盖从单元到端到端的全链路：

| 测试文件 | 测试数 | 覆盖范围 |
|----------|--------|----------|
| `test_config.py` | 10 | 路径解析、环境变量、默认值 |
| `test_id_resolver.py` | 14 | ULID/arXiv/DOI/slug 解析、模糊匹配、缓存 |
| `test_research_loop.py` | 16 | 兴趣 CRUD、日志分析、方向同步 |
| `test_kb_update.py` | 10 | arXiv XML 解析、ULID 生成、批量入库 |
| `test_db.py` | 11 | JSON 读写、目录操作、DB 连接检测 |
| `test_cli.py` | 33 | 全部 CLI 命令 smoke test + 执行测试 |
| `test_hooks.py` | 19 | 标签剥离、ISO 周号、transcript 解析 |
| `test_e2e.py` | 8 | ingest pipeline + adaptive research loop |

```bash
# 运行全部测试
pytest

# 运行单个文件
pytest test/test_cli.py

# 运行 E2E 测试
pytest test/test_e2e.py -v
```

---

## 自动化 Hooks

配置在 `.qoder/settings.json`，Qoder 重启后生效：

| Hook | 事件 | 作用 |
|------|------|------|
| `log-conversation.ps1` | Stop | 自动采集对话查询 → 写入 week-*.jsonl（3×800ms 重试 + 全目录搜索） |
| `task-done.ps1` | Stop | Agent 完成任务后弹出 Windows 桌面通知 |
| `block-dangerous.ps1` | PreToolUse | 拦截 `DROP TABLE`、`docker rm` 等危险操作 |

## 快捷指令

放在 `.qoder/commands/`，在对话中输入 `/` 即可调用：

| 指令 | 用法 |
|------|------|
| `/stats` | 查看知识库状态（论文数、图谱、RAG 覆盖） |
| `/find` | 全文 + 语义混合搜索论文 |
| `/paper` | 查看单篇论文详情 + 引用关系 |
| `/health` | 知识库健康检查 + 修复建议 |
| `/resume` | 断点恢复：扫描中间产物自动定位未完成任务 |
| `/sync` | 研究方向同步：搜索 arXiv + 全流程入库 |

---

## Qoder Plugin

本项目可封装为 **Qoder Plugin**，在 Quest 模式下安装使用。Plugin 包含全部 15 个 Skills + 6 个 Commands + MCP Server。

### 构建 Plugin

```bash
python build_plugin.py
```

产出在 `plugin/` 目录：

```
plugin/
  .qoder-plugin/plugin.json   ← 插件元数据
  skills/                     ← 15 个 Skills
  commands/                   ← 6 个快捷指令
  rules/                      ← Agent 规则
  .mcp.json                   ← MCP Server 配置
```

### 安装使用

1. 在 Qoder Quest 中安装此 Plugin
2. 克隆主仓库并执行 `pip install -r requirements.txt` + `python -m scholar bootstrap`
3. 启动数据库后，所有 15 个 Skills 即可使用

> **本地 IDE 用户**：不需要 Plugin，直接 clone 本仓库即可，`.qoder/skills/` 会自动加载。

---

## 打包为独立 EXE（PyInstaller）

将 Scholar Studio 打包为独立可执行文件，无需 Python 环境即可使用：

### 方式一：pip 全局安装（最简单）

```powershell
pip install -e .              # 开发模式，改代码即时生效
scholar stats                 # 任意目录可用
scholar search "transformer"  # 全局命令
```

### 方式二：PyInstaller 打包

```powershell
# onedir 模式（推荐，启动快）
python build_exe.py
# 产物：dist/scholar/scholar.exe

# onefile 模式（单文件）
python build_exe.py --onefile
# 产物：dist/scholar.exe
```

### 首次使用

```powershell
scholar init          # 初始化 ~/.scholar-studio/ 目录结构
# 配置 .env（API keys）
# 启动 Docker（PostgreSQL + Neo4j）
scholar stats         # 验证一切正常
```

### 数据目录

| 运行模式 | 数据/输出位置 | 切换方式 |
|---------|-------------|----------|
| pip 安装（开发） | 源码目录 `output/` | 固定，不随 cwd 变化 |
| PyInstaller 打包 | `~/.scholar-studio/output/` | `SCHOLAR_HOME` 环境变量覆盖 |

---

## 自定义改造：换成你自己的论文库

Scholar Studio 可以管理**任意领域**的 TeX 论文。以下步骤把它改造成你自己的学术研究助手：

### 1. 准备论文

将你的论文放入 `data/papers/<ULID>/` 目录，每篇论文一个文件夹：

```
data/papers/
  01KT6MTBBH03MN0Z6PK902XKC2/
    paper.pdf           # PDF 原文（可选，用于展示）
    source.tar.gz       # TeX 源文件压缩包（必须，用于解析）
```

> **ULID 命名**：每个文件夹名用 ULID 格式（26 位字母数字），可用在线工具生成：https://ulidgenerator.com/
>
> **TeX 源文件**：压缩包内包含 `.tex`、`.bib` 等文件。Scholar 解析 TeX 提取标题、摘要、章节、公式、引用。

### 2. 批量导入

```bash
# 扫描所有论文
python -m scholar scan

# 批量解析
python -m scholar parse-all

# 补全缺失年份和作者
python -m scholar year-fix --apply
python -m scholar author-fix --apply
```

### 3. 重建数据层

```bash
# 重建图谱（Neo4j）
python -m scholar graph-build

# 重建 RAG 索引（需 API Key）
python -m scholar rag-index

# 生成阅读笔记 + 质量评分 + 分类
python -m scholar auto-notes
python -m scholar quality-score --all
python -m scholar classify --all
```

### 4. 更新 Lean4 形式化层（可选）

编辑 `LEAN/AiEvolution/Database.lean`，添加你的领域的创新节点和定理。然后重新编译：

```bash
cd LEAN && lake build
```

### 5. 修改 Agent 规则

编辑 `.qoder/rules/identity.md`，更新项目描述和心智模型，让 Agent 适配你的研究方向。

---

## 常见问题

### Docker 容器启动失败

```bash
# 检查 Docker 是否在运行
docker info

# 检查端口是否被占用
netstat -ano | findstr "5433"
netstat -ano | findstr "7474"

# 如果端口被占用，修改 infra/docker-compose.yml 中的端口映射
```

### PostgreSQL 连接超时

端口 5433 而非常规 5432，是刻意设计避免冲突。所有连接字符串硬编码了 5433：

```
postgresql://scholar:scholar2024@localhost:5433/scholar
```

### RAG 搜索无结果

1. 确认 `.env` 中有有效的 `SCHOLAR_EMBEDDING_API_KEY`
2. 确认 `python -m scholar rag-index` 已成功执行
3. 没有 API Key 时，`rag-search` 会自动 fallback 到全文搜索

### Bootstrap 中断恢复

直接重新运行 `python -m scholar bootstrap`，已完成的步骤会自动跳过。如果需要强制重跑某一步：

```bash
python -m scholar parse-all          # 重新解析所有论文
python -m scholar graph-build        # 重建图谱
python -m scholar rag-index          # 重建 RAG 索引（先 TRUNCATE chunks 表）
```

### Windows + VMware 冲突

如果 VMware 使用了 WSL2 后端，Docker Desktop 可能无法启动。解决：

```powershell
# 检查 WSL 状态
wsl --list --verbose

# 如果 Docker Desktop 的 distro 未运行
wsl --shutdown
# 然后重新启动 Docker Desktop
```

### 测试失败

```bash
# 确保依赖完整
pip install -r requirements.txt

# 如果 Neo4j/PostgreSQL 未运行，部分测试会跳过（pytest.mark.skipif）
# 仅运行不依赖数据库的测试
pytest -k "not db"
```
