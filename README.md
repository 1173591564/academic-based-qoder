# Scholar Studio — AI 学术研究助手

基于 Qoder IDE 的学术研究引擎，管理 **440 篇 AI 演化方向论文**，提供 RAG 语义检索、Neo4j 引用图谱、22 个学术 skills（18 原子 + 4 组合 workflow）和 Lean4 形式化验证。

## 快速开始（3 步）

### 1. 启动数据库

```powershell
.\startup.ps1
```

自动拉起 Docker 容器：
- **PostgreSQL 16 + pgvector**（端口 5433）— 结构化数据 + 向量索引
- **Neo4j 5 Community**（端口 7474/7687）— 概念图谱 + 引用网络

### 2. 在 Qoder 中打开项目

Qoder 自动读取 `.qoder/mcp.json`，后台启动 **Scholar MCP Server**（29 个工具），无需手动操作。

### 3. 对话即可使用

```
你：调研 Transformer 的注意力机制演进
你：精读 01KT6MTBBH03MN0Z6PK902XKC2
你：写 Attention 方向的 Related Work
```

### 一键开始（Deeplinks）

点击链接直接唤起 Qoder 并开始任务：

| 任务 | 说明 |
|------|------|
| [调研 Transformer](qoder://aicoding.aicoding-deeplink/chat?text=%E8%B0%83%E7%A0%94+Transformer+%E6%B3%A8%E6%84%8F%E5%8A%9B%E6%9C%BA%E5%88%B6%E7%9A%84%E5%8F%91%E5%B1%95%E5%8E%86%E7%A8%8B%EF%BC%8C%E6%8C%89%E6%97%B6%E9%97%B4%E7%BA%BF%E6%95%B4%E7%90%86%E5%85%B3%E9%94%AE%E8%AE%BA%E6%96%87&mode=agent) | 按时间线整理注意力机制关键论文 |
| [精读 Attention Is All You Need](qoder://aicoding.aicoding-deeplink/chat?text=%E7%B2%BE%E8%AF%BB%E8%AE%BA%E6%96%87+01KT6MTBBH03MN0Z6PK902XKC2+%28Attention+Is+All+You+Need%29%EF%BC%8C%E8%BE%93%E5%87%BA%E7%BB%93%E6%9E%84%E5%8C%96%E5%88%86%E6%9E%90&mode=agent) | 结构化分析经典论文 |
| [RLHF 研究空白](qoder://aicoding.aicoding-deeplink/chat?text=%E5%88%86%E6%9E%90+RLHF+%E5%92%8C+DPO+%E6%96%B9%E5%90%91%E7%9A%84%E7%A0%94%E7%A9%B6%E7%A9%BA%E7%99%BD%E5%92%8C%E6%9C%AA%E6%9D%A5%E6%96%B9%E5%90%91&mode=agent) | 分析 RLHF/DPO 的研究缺口 |
| [入门 State Space Model](qoder://aicoding.aicoding-deeplink/chat?text=%E5%85%A5%E9%97%A8+State+Space+Model%EF%BC%8C%E5%BB%BA%E7%AB%8B%E7%9F%A5%E8%AF%86%E5%9B%BE%E8%B0%B1%E5%92%8C%E5%AD%A6%E4%B9%A0%E8%B7%AF%E5%BE%84&mode=agent) | 建立知识图谱和学习路径 |

## 18 个原子 Skills + 4 个组合 Workflow

在 Qoder 对话中直接使用，或输入 `/skill-name` 触发：

### 原子 Skills

| 类别 | Skill | 用法示例 |
|------|-------|--------|
| **研究与阅读** | `research-survey` | "调研 Diffusion Model 的发展历程" |
| | `deep-read` | "精读这篇论文" + 指定 ULID |
| | `paper-compare` | "对比 BERT 和 GPT" |
| | `paper-recommendation` | "推荐接下来该读什么" |
| | `cold-start` | "入门 State Space Model" |
| **分析与写作** | `related-work` | "写 Transformer 的 Related Work" |
| | `citation-network` | "分析 NLP 领域的引用网络" |
| | `research-gap` | "找 RLHF 方向的研究空白" |
| | `concept-evolution` | "追踪 CNN → Transformer 的概念演化" |
| **数学与验证** | `formula-derivation` | "推导 VAE 的 ELBO" |
| | `math-verification` | "用 Lean4 验证这个定理" |
| | `experiment-code` | "复现 LoRA 的实验代码" |
| **质量与评审** | `quality-check` | "检查这篇论文的质量" |
| | `review-report` | "写一篇审稿报告" |
| **管理与维护** | `paper-ingestion` | "导入新论文" |
| | `bibtex-management` | "导出 BibTeX" |
| | `kb-maintenance` | "知识库健康检查" |
| | `reading-progress` | "查看阅读进度" |

### 组合 Workflow

每个 workflow 串联多个原子 skill，自动传递数据，一键完成完整研究流程：

| Workflow | 链路 | 用法示例 |
|----------|------|--------|
| `full-research` | survey → deep-read → compare → related-work | "全面调研 Transformer" |
| `gap-analysis-flow` | citation-network → concept-evolution → research-gap → recommend | "找 RLHF 的研究空白" |
| `paper-analysis-flow` | deep-read → quality-check → formula-derivation → experiment-code | "深度分析 Attention Is All You Need" |
| `writing-flow` | survey → compare → related-work → bibtex → review | "帮我写论文的 Related Work" |

## CLI 命令参考

```bash
# 论文库
python -m scholar stats                     # 知识库统计
python -m scholar search "attention"        # 全文搜索
python -m scholar list-papers --year 2024   # 按年份列出
python -m scholar info <ULID>               # 论文详情
python -m scholar export-bib                # 导出 BibTeX

# 图谱查询
python -m scholar graph-stats               # 图谱统计
python -m scholar graph-query "attention"   # 概念查询
python -m scholar cite-network              # 全局引用网络
python -m scholar cite-network <ULID>       # 单篇前后向引用

# 语义搜索
python -m scholar rag-search "query"        # 向量搜索
python -m scholar rag-search "q" --hybrid   # 混合搜索（向量+BM25+RRF）

# 批处理
python -m scholar auto-notes                # 生成全部阅读笔记
python -m scholar quality-score --all       # 7 维度评分（A-F）
python -m scholar classify --all            # 领域/子领域/方法分类

# 编排
python -m scholar bootstrap                 # 全量初始化（首次部署）
python -m scholar ingest <ULID>             # 增量导入单篇

# 外部
python -m scholar arxiv-search "query"      # 搜索 arXiv
```

## 项目结构

```
.qoder/
  rules/           Agent 规则（onboarding, identity, pipelines, tools, academic）
  skills/          22 个学术 skills（18 原子 + 4 workflow，每个含 Next Steps 引导）
  mcp.json         MCP Server 配置（Qoder 自动读取）

data/papers/       445 篇论文（每篇：paper.pdf + source.tar.gz）
output/
  parsed/          440 篇结构化 JSON（核心数据源）
  notes/           阅读笔记 + 质量评分
  drafts/          综述、Related Work、报告
  bib/             BibTeX 文件
  experiments/     实验代码复现

LEAN/              Lean4 形式化验证（125 创新节点 + 7 定理）
scholar/           Python CLI 工具集（17+ 命令）
scholar_mcp/       MCP Server（29 tools，Qoder 桥接）
infra/             Docker 编排（PostgreSQL + Neo4j）
```

## 数据规模

| 数据层 | 数量 |
|--------|------|
| 论文 | 440 篇（TeX 源文件解析） |
| Sections | 13,719 |
| Formulas | 5,064 |
| Citations | 36,477 |
| RAG Chunks | 45,405 |
| Neo4j Nodes | 25,131 |
| Neo4j Edges | 38,485 |
| 阅读笔记 | 439 |
| 质量评分 | 423（A:93 B:262 C:59 D:9） |
| 领域分类 | 417 |

## 环境要求

- **Docker Desktop**（含 Docker Compose）
- **Python 3.10+**
- **Qoder IDE**（可选，用于 MCP 集成和 Skills）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量

在项目根目录创建 `.env`：

```env
# 智谱 embedding API（RAG 语义搜索必需）
SCHOLAR_EMBEDDING_API_KEY=your_key_here
```

> 数据库密码等变量**不需要**放在 `.env` 中，由 Docker 容器内部管理。

## 首次部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建 .env（填入智谱 API Key）
echo "SCHOLAR_EMBEDDING_API_KEY=your_key" > .env

# 3. 启动数据库
.\startup.ps1

# 4. 全量初始化（约 40 分钟，含 RAG 向量索引）
python -m scholar bootstrap
```

## 自动化 Hooks

配置在 `.qoder/settings.json`，Qoder 重启后生效：

| Hook | 事件 | 作用 |
|------|------|------|
| `task-done.ps1` | Stop | Agent 完成任务后弹出 Windows 通知 |
| `block-dangerous.ps1` | PreToolUse | 拦截 `DROP TABLE`、`docker rm` 等危险操作 |

## 快捷指令

放在 `.qoder/commands/`，在对话中输入 `/` 即可调用：

| 指令 | 用法 |
|------|------|
| `/stats` | 查看知识库状态（论文数、图谱、RAG 覆盖） |
| `/find` | 全文 + 语义混合搜索论文 |
| `/paper` | 查看单篇论文详情 + 引用关系 |
| `/health` | 知识库健康检查 + 修复建议 |
