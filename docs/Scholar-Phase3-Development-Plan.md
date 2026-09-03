# Scholar 论文数据库 × DSH 学者模式：第三阶段综合分析

## 一、结论

第三阶段不应该先增加更多 Skill、聊天入口或管理界面，而应建设 **Research Evidence Foundation（研究证据基础层）**。

当前项目已经具备较宽的功能面：

- arXiv 搜索、下载和批量入库；
- TeX 解析；
- 关键词、论文向量、段落向量和 hybrid 检索；
- 引用图、概念图、时间线；
- 自动笔记、分类和质量评分；
- 研究方向同步；
- 综述、精读、推荐、研究空白、复现和写作 Skill；
- 固定 16 个 Scholar MCP tools。

但这些能力主要围绕 `output/parsed/*.json`、sidecar 文件、启发式提取和 Skill 编排展开，尚未形成统一的论文事实、版本、原文位置和派生证据模型。因此 DSH 已经能够“执行研究流程”，但还不能稳定保证每个研究结论都可以回溯、复算和验证。

建议将产品边界固定为：

```text
DSH Scholar Mode
├─ 识别研究意图
├─ 选择 Skill / Workflow
├─ 管理 session、plan、todo、subagent 和恢复
├─ 组织研究过程和写作产物
└─ 通过 MCP 读取 Scholar 证据

Scholar
├─ canonical paper identity
├─ source / version / asset
├─ document block 与原文 locator
├─ metadata、citation、entity、experiment
├─ lexical / vector / hybrid index
├─ graph 与 evidence lineage
├─ reading / research state
└─ recommendation / gap evidence
```

核心原则：

```text
DSH = 研究任务执行环境
Scholar = 学术事实与证据数据面
MCP = 稳定的模型工具契约
output/ = 研究产物层
PostgreSQL + versioned JSON = 事实存储及兼容投影
```

---

## 二、当前能力的可信度分层

### 1. 已由代码实现

- 固定 16 个 MCP tools 及“搜索 → 摘要/目录 → 章节 → 段落”的阅读阶梯；
- TeX archive 和目录解析，提取 metadata、sections、formulas、citations、bibliography；
- PostgreSQL 的 papers、sections、formulas、citations、concepts、chunks 等基础表；
- paper-level vector、passage vector、BM25 和 RRF hybrid；
- 内存引用/概念图、lineage、hub、concept timeline；
- arXiv metadata enrichment 和引用消歧；
- 自动笔记、规则分类、启发式质量评分；
- 研究兴趣文件、方向同步、arXiv 下载和 batch ingest；
- 实验模板、运行、日志指标提取和结果比较等 CLI 骨架。

### 2. 已有流程，但底层证据不足

- 综述：能检索、分类、按年份组织论文，但没有检索快照、纳入/排除记录、claim-evidence 关系；
- 精读：能读摘要、目录、章节和公式，但没有页码、段落、公式位置和稳定 block ID；
- 引用脉络：能建立 library-internal 引用边，但缺引用出现位置、上下文、意图、候选和置信度；
- 自动笔记：能生成 Markdown，但笔记结论没有逐条 evidence locator；
- 质量评分：能产生分数，但大量维度来自字段存在性和关键词启发式，不能视为论文事实；
- 实验复现：能生成工程模板和运行脚本，但模板仍含大量 TODO，并默认使用 synthetic data，不能等同于完成复现；
- 持续同步：能重复搜索和下载，但没有 cursor、seen-version、change event、checkpoint 和 durable retry。

### 3. 主要由 Skill 文档承诺，数据库尚未承载

- 个性化论文推荐；
- 可验证的研究空白发现；
- 方法、任务、数据集、指标和实验结果的关系推理；
- 系统化综述证据矩阵；
- claim-level 学术写作和审稿核查；
- 可恢复、可审计的真实论文复现；
- 跨 session 的阅读历史、收藏、反馈和研究进展。

### 4. 当前不能声称的质量结论

当前 checkout 中：

```text
parsed papers = 0
paper directories = 0
experiment directories = 0
```

因此不能基于当前环境声称解析覆盖率、RAG 召回率、图谱质量、推荐质量、gap 质量或真实复现成功率。第三阶段应先建立可复现 fixture corpus 和评测集，再讨论这些质量指标。

---

## 三、parsed 论文专项审计

### 1. 总体结论

当前 parser 确实有清洗和基础提取能力，但其产物不是严格论文事实模型。更准确的定位是：

```text
当前 parsed JSON
= 启发式 metadata
+ 清洗后 section 检索文本
+ 部分 display formula
+ citation key 集合
+ bibliography 候选
+ 后续写回的 tags / quality 等派生字段
```

它适合初步全文搜索、基础 section 浏览、粗粒度 RAG、公式和引用候选收集，以及单用户本地研究原型。

它不适合单独承担严格学术引用、定理/证明/算法/图表核查、citation context evidence、公式精确身份验证、paper version/source reproducibility，以及 DSH 学者模式中的 claim-level 可追溯结论。

因此，“清洗 + 整理 + 结构化”不是第三阶段的普通增强项，而应占据 P0 的主要范围。

### 2. 入口与原始资料处理

| 能力 | 当前实现 | 判断 |
|---|---|---|
| `source.tar.gz` / `.tgz` / `.tar` / `.zip` | 支持 | 可用，但没有 artifact hash、版本和 acquisition provenance |
| 直接 `.tex` directory | 支持 | 可用 |
| PDF-only | 不支持 | 阻断大量无 TeX source 的论文 |
| archive 安全 | tar 使用 data filter；zip 检查目标路径 | 基础防穿越已实现 |
| 主 TeX 发现 | 从含 `\documentclass` 的候选中按 input 数量、文件长度选择 | 可能误选 supplement、response 或独立 appendix，且不记录候选和选择理由 |
| `\input` / `\include` | 递归展开；visited 防循环 | 展开后丢失文件边界和 locator；同一子文件多次合法引用也会被全局去重 |
| 缺失 input | 插入 `% [MISSING INPUT: ...]` | 后续 comment 清洗会删除标记，最终结果看不出缺失内容 |
| 编码失败 | `errors="ignore"` | 无报告地丢弃无法解码字节 |
| `meta.json` | 下载时生成，但 parser 不读取 | 已验证：canonical metadata 不会自动进入 parsed result |
| source/PDF 对齐 | 无 | 不能提供 page/bbox 或双源验证 |

### 3. 清洗规则的保真度

当前 `_clean_tex()` 会删除 comments、macro definitions 和排版命令，并尽量保留常见 formatting command 的参数文本。此方向适合生成检索文本，但 `_extract_sections()` 还执行了更强的内容删除：

```text
整段删除：
figure / table / algorithm / algorithmic / tabular
theorem / lemma / proposition / corollary
proof / definition / example / remark / note
code / minted / verbatim / quote 等环境

占位替换：
display math → [formula]
inline math → [math]
citations → [cite]
cross references → [ref]

硬截断：
每个 section 最多保留 10,000 字符
```

隔离行为实验确认：

- theorem、proof 和 table 内容从 section text 中消失；
- citation key、inline math 和 cross-reference target 被占位符替代；
- 超长 section 被截断并追加 `... [truncated]`；
- 两个前 100 字符相同、尾部不同的公式会被错误去重为一个；
- bibliography 中未在正文出现的 `\bibitem` 也会进入 `citations`；
- BibTeX 的 `Vaswani, Ashish and Shazeer, Noam` 被拆成四个“作者”；
- 同目录 `meta.json` 中的 title/authors/year/arXiv ID 不会被 parser 合并。

这些行为不是单纯格式清理，而是有损转换。如果保留原 source artifact 和 locator，它们可以作为派生 search view；当前系统却把有损结果当作核心数据源，因此 trust boundary 不成立。

### 4. 当前结构化字段评估

| 字段 | 当前结构 | 可以如何理解 | 缺失 |
|---|---|---|---|
| `paper_id` | 外部传入字符串 | 本地记录 ID | canonical work、version、identifier provenance |
| title/authors/year/venue/arXiv ID | parser regex/heuristic | extracted metadata candidate | source、confidence、候选冲突、assertion history |
| abstract | 清洗后字符串 | extracted text | locator、原文、language、loss report |
| sections | heading、level、content、position | 有损 search/read projection | stable ID、parent、paragraph、source span、PDF page |
| formulas | latex、label、env_type | display formula candidate | stable ID、section/context/locator/hash；inline math |
| citations | 去重后的 ref key 字符串 | reference-key candidate 集合 | mention、count、context、locator、intent |
| bibliography | ref_key/title/authors/year/DOI | reference-entry candidate | stable ID、source、完整作者、resolver provenance |
| `tex_file_count` / `main_tex_file` | 计数和 basename | parser diagnostic | relative path、候选、选择原因、source hash |
| `tags` | 分类器写回 | derived classification | extractor/taxonomy version、confidence |
| `quality` | 评分器写回 | heuristic derived score | rule version、evidence、独立 artifact |

严格来说，parsed JSON 中几乎所有字段都是 extracted/derived fact，而不是不可争议的 source fact。原始 TeX/PDF 才是 source fact；但 parsed result 没有指向它们的稳定 lineage。

### 5. JSON、PostgreSQL 和派生索引的一致性

当前 `output/parsed/*.json` 被代码和文档视为 source of truth，PostgreSQL 是关系镜像，graph/RAG/notes 等再从 JSON 派生。主要问题是：

1. `save_parsed()` 直接覆盖同名 JSON；没有 schema validation、schema/parser version、source hash、run ID 或 immutable revision。
2. 单篇和批量 parse 都先保存 JSON，再在内存中添加 `parsed_path` 和 section/formula/citation counts 后写 PostgreSQL；这些字段通常不回写 JSON。
3. 后续 `scholar sync` 从缺少 counts 的 JSON 再次 upsert `papers`，可能把 paper-level counts 重置为 0，同时 child tables 仍有数据。
4. `upsert_sections/formulas/citations` 采用整篇 delete-and-reinsert；`SERIAL` ID 会变化，历史和外部引用失效。
5. bibliography 完全没有 PostgreSQL projection；tags/quality 与 PG 的语义也不一致。
6. PG `formulas.context` 字段存在，但 parser 不生成 formula context。
7. `citations UNIQUE(from_paper, to_ref)` 只能保存 paper-level key，无法保存同一引用的多次 mention。
8. graph cache 用文件路径、mtime 和 size 做 source fingerprint；sync state 也按 mtime 增量，不是 source/parser/content lineage。
9. paper vectors 主要基于 title + abstract；passage chunks 基于已丢失内容的 cleaned sections，且均没有 parser/chunker/model/index version。
10. quality 和 classification 会修改 parsed JSON，导致 parser 重跑、分类重跑和索引刷新之间不存在稳定 artifact identity。

文件模式与 PostgreSQL 模式不是同一语义模型，只是部分字段重叠的两套投影。

### 6. citation graph 的额外风险

当前 citation 提取、解析和 graph projection 还有两个会直接影响研究结论的问题：

1. `_extract_citations()` 把正文 `\cite` 和所有 `\bibitem` 合并，所以“列在 bibliography 中”会被误当成“正文实际引用”。
2. `refs-resolved.json` 和内存 graph 使用全局 `ref_key → paper_id`。但 `smith2020` 之类 key 只在单篇 TeX/BibTeX 文档内部有意义；不同论文可以用同一 key 指向不同工作。正确 identity 至少应是 `(from_paper_version, ref_key)`，最终边则由 citation mention/reference entry 产生。

这意味着现有 citation graph 可以用于探索，但不能作为严格 citation evidence graph。

### 7. 测试覆盖结论

`tests/test_tex_parser.py` 当前仅收集 9 个测试，集中在基础 BibTeX/bibitem、DOI、citation key、title 和简单 macro。它没有直接测试完整 `parse_archive()` 或 `parse_directory()`，仓库中也没有 TeX/PDF fixture corpus。

缺少 archive、多 main document、nested/missing/cyclic input、malformed TeX、PDF-only、figure/table/algorithm/theorem/proof、stable ID、source locator、loss report、多语言、公式碰撞、citation mention、metadata provenance、determinism/versioning/idempotence、JSON schema 和真实 PostgreSQL ingestion 等覆盖。

已有相关基础测试通过，证明当前已声明的 helper 和文件保存行为可运行；它们不能证明解析保真度或真实 corpus 质量。数据库测试甚至明确断言同名 parsed JSON 会被覆盖，这验证了当前行为，而非版本化事实模型。

### 8. 面向 DSH Scholar Mode 的差距

现有 16 个 MCP tools 已经形成合理的阅读阶梯，但返回的是 section index、heading、清洗文本和相似度，缺少：

```text
paper_version
block_id / mention_id / formula_id
TeX file + line/byte span
PDF page + bbox
source artifact hash
parser / chunker / index version
evidence kind
confidence
loss or warning status
```

所以 DSH 可以记录“模型读到了一段什么文本”，却无法可靠记录“这段文本来自哪个版本、哪处原文、经过了哪些有损处理”。session replay 能重放工具输出，但不能完成论文证据复核。

---

## 四、九个 DSH 学者旅程映射

| 研究旅程 | DSH 编排 | 主要 Skill | 可复用 MCP tools | Scholar 当前支持 | 核心缺口 | 当前判断 |
|---|---|---|---|---|---|---|
| 1. 冷启动研究方向 | session + plan/todo；必要时分解子任务；workspace 保存方向产物 | `cold-start`、`adaptive-research`、`kb-management` | `scholar_list_papers`、`scholar_search`、`scholar_arxiv_search`、`scholar_graph_stats`、`scholar_interests` | interest 文件、日志关键词提取、arXiv 搜索、方向同步 | 没有正式 ResearchDirection、query version、cursor、seen registry、覆盖度和来源记录 | 局部可用 |
| 2. 搜索与筛选 | 识别主题/问题，生成检索计划，并行查本地库、语义索引和 arXiv | `research-survey`、`paper-recommendation` | `scholar_search`、`scholar_vec_search`、`scholar_passages`、`scholar_info`、`scholar_arxiv_search` | lexical、paper vector、passage vector、BM25/RRF | identity/version 不稳；结果无 index version、score explanation、locator；hybrid 按 paper 去重丢失 passage 证据 | 局部可用 |
| 3. 论文深度阅读 | 先摘要/目录，再选择章节；todo 记录阅读问题；workspace 生成笔记 | `paper-deep-dive`、`math-verification`、`review-report` | `scholar_info`、`scholar_section`、`scholar_passages`、`read_parsed_paper`、`scholar_auto_notes` | sections、formulas、章节读取、笔记和质量评分 | 只支持 TeX；没有 PDF fallback；无 paragraph/page/bbox/char span；figure/table/algorithm 未结构化 | 局部可用 |
| 4. 引用与概念关系 | 从目标论文横向展开 lineage、hub 和 concept，再回读原文 | `citation-network`、`research-gap` | `scholar_cite_network`、`scholar_graph_query`、`scholar_lineage`、`scholar_graph_stats` | citation graph、concept co-occurrence、timeline | graph edge 无 citation mention、上下文、位置、解析置信度；概念主要来自词表和标签；无 method/task/dataset 实体 | 局部可用 |
| 5. 形成研究综述 | DSH plan 定义问题和章节；subagent 可分主题收集证据；workspace 合并草稿 | `research-survey`、`writing-pipeline` | 搜索、info、section、passages、graph、output reader | CLI survey、timeline、分类、质量分布 | 没有查询快照、纳排标准、证据表、冲突事实和 claim-citation registry | 弱支撑 |
| 6. 发现研究空白 | DSH 先定义“空白”判据，再对任务×方法×数据集×指标矩阵做证据检查 | `research-gap`、`idea-to-paper` | search、passages、graph、lineage、section | 可用检索与图谱辅助人工推理 | 无 GapHypothesis、coverage matrix、negative-evidence 边界和 supporting/contradicting evidence | 主要是 Skill 推理 |
| 7. 推荐下一篇论文 | 根据研究方向、已读内容和当前任务生成候选与理由 | `paper-recommendation`、`adaptive-research` | search、vec-search、graph、list、info | semantic similarity、graph proximity、interest keywords | 无阅读事件、反馈、候选池、reranking、diversity、新颖性和 recommendation reason/evidence | 主要是 Skill 推理 |
| 8. 复现论文实验 | DSH plan/todo 管理步骤；subagent 可分代码、数据、指标；workspace 保存运行产物 | `reproduce-paper`、`experiment-code`、`math-verification` | info、section、passages、read parsed、read output | 实验模板、dataset 命令、run/compare/debug 骨架、指标正则提取 | 无结构化 experiment spec、dataset/version、代码 commit、环境、seed、run lineage；模板仍有 TODO/synthetic data | 工程脚手架 |
| 9. 持续同步方向 | durable session/automation 触发；每次同步产生 bounded result 和后续 todo | `adaptive-research`、`kb-management`、`cold-start` | `scholar_arxiv_search`、`scholar_interests`、list/search/info | research-sync、download、batch-ingest、digest | 无 cursor、源版本变化、幂等 run、checkpoint/retry、提醒理由；remote MCP 模式不能执行大量本地 CLI 步骤 | local 模式局部可用 |

### DSH 在这些旅程中的正确职责

- 用规则和 Skill 识别“调研、精读、复现、写作、空白发现”等意图；
- 用 plan/todo 将长研究任务拆成可恢复步骤；
- 用 subagent 并行处理独立论文或子主题；
- 将模型可见的 Scholar 工具结果写入 session log；
- 把综述、笔记、审稿、实验报告等产物写到 workspace；
- 不自行充当论文事实数据库。

DSH 的关键约束是：

> Model-visible means logged.

所以 Scholar 返回的证据必须足以在 session replay、resume 和 fork 后重建结论来源，而不能只返回一段不可定位的自然语言。

### 当前 DSH 接入现实

上表中的 DSH 编排是目标运行方式，不代表所有环节已经由真实 DSH workflow 实现。当前状态还包括：

- Scholar 主要分发 `SKILL.md` 指令资源，并不是一套已经持久化的 DSH workflow 定义；
- Skill 大量直接调用本地 `python -m scholar ...`，部分内容仍写的是 Qoder Work 定时任务；
- DSH 的 session、plan、todo、subagent 和 workflow 能力可以承载这些流程，但当前 Scholar 数据层没有对应的 operation/evidence 状态与其对齐；
- `scholar init-dsh` 生成的配置引用 `@deepseek-ai/dsh-scholar-native`，但当前 DSH workspace 和 npm 中都无法解析该 package；
- 现有测试主要检查配置文本，没有通过真实 Loader 和应用进程验证 scholar mode composition。

因此近期不能把“存在 Scholar Skill”直接等同于“DSH 学者模式已经端到端可运行”。前置 PR 应先建立真实 Loader composition test，再将九个旅程逐步升级为可恢复、可验证的 DSH workflow。

---

## 五、最重要的数据缺口

### P0：论文事实基础

#### 1. Canonical identity 与版本

当前 ULID 是本地目录标识，`arxiv_id`、DOI、slug 通过扫描 parsed JSON 建立内存 alias。缺少：

- canonical work；
- identifier normalization 和唯一约束；
- arXiv version；
- DOI manifestation；
- source acquisition；
- source/PDF/TeX asset hash；
- duplicate candidate、merge decision 和 redirect；
- metadata value 的来源与置信度。

建议至少引入：

```text
papers
paper_identifiers
paper_versions
source_assets
metadata_assertions
paper_aliases
duplicate_candidates
```

#### 2. Document block 与原文定位

当前 section、formula 和 chunk 没有统一 stable ID，也没有可靠的原文位置。递归合并 TeX include 后还会削弱原文件来源关系。

建议统一：

```text
document
└─ block
   ├─ heading
   ├─ paragraph
   ├─ equation
   ├─ figure / caption
   ├─ table / cell / caption
   ├─ algorithm
   ├─ list
   └─ footnote
```

每个 block 至少包含：

```text
block_id
paper_version_id
parent_block_id
block_type
ordinal
text / structured_payload
tex_file + start_line/end_line + byte span
pdf_page + bbox
extractor + extractor_version
content_hash
```

`output/parsed/*.json` 应变成此模型的兼容投影，而不是与 PostgreSQL 竞争的第二套事实源。

#### 3. PDF-only 论文

下载流程会保存 PDF，但 `parse_paper()` 只接受 source archive 或 `.tex`。所以没有 TeX source 的论文无法进入当前结构化语料库。第三阶段需要：

- TeX 优先；
- PDF layout-aware fallback；
- OCR 作为可选后备；
- TeX/PDF 对齐；
- 同一 block 的多 source locator。

### P0：派生物一致性

当前 parsed JSON、PG tables、paper_vectors、chunks、BM25 memory、graph cache、refs sidecar、notes、quality 和 tags 有不同刷新方式。

建议引入：

```text
operation_runs
operation_items
artifacts
artifact_dependencies
index_manifests
extractor_manifests
```

每个 artifact 必须声明：

```text
输入 paper_version / block hashes
生成器及版本
配置 hash
开始/结束时间
状态和失败原因
输出 hash
被哪个后续 artifact 消费
```

这样 DSH 的长任务才能支持 operation ID、checkpoint、retry、resume 和逐篇失败报告。

### P1：检索证据

当前 chunk 只有 paper、section、content、embedding，固定 1024 维；paper vector 和 chunk vector 没有统一 model/index manifest。

需要：

- stable chunk ID；
- chunk → block/span；
- lexical index version；
- embedding provider/model/version/dimension；
- chunker version/config；
- vector index version；
- passage-level hybrid fusion，不应先按 paper 去重；
- score breakdown、rank trace 和 dedup reason；
- query normalization 和 filter snapshot；
- retrieved evidence 的 immutable locator。

静态检查还发现一个应先修复的基线问题：带 `paper_id`/`section` filter 的 passage vector SQL，其参数顺序与 SQL placeholder 顺序不一致；当前 fake test 反而固定了错误顺序。该路径应增加真实 PostgreSQL 集成测试。

### P1：研究实体与关系

目前 tags 和 concepts 主要是关键词/词表结果。要支撑 gap、recommendation、survey 和 reproduction，需要：

```text
authors / affiliations
tasks
methods
models
datasets + dataset_versions
metrics
benchmarks
experiments
experimental_conditions
reported_results
code_resources
claims
entity_mentions
relations
```

每个实体和关系必须绑定 evidence span、extractor、version、confidence，并允许人工确认或修订。

### P1：引用证据

应将“引用边”拆成：

```text
reference_entry
citation_mention
resolution_candidate
resolution_decision
citation_relation
```

其中 citation mention 包括：

- 出现在哪个 block；
- 原文上下文；
- 页码/TeX span；
- citation intent；
- 支持、比较、沿用、反驳等关系；
- resolution method 和 confidence。

图谱中的每条边必须能返回至少一个 citation mention ID。

### P2：用户研究状态

数据库虽然有 `read_status` 字段，但未发现完整的状态变更路径。需要：

```text
research_directions
research_queries
reading_events
paper_state
collections
annotations
note_revisions
feedback_events
```

如果 Scholar 是远程多租户服务，这些状态还必须带 tenant/user/workspace scope；如果是本地单用户，也应保留 workspace/session 来源。

### P2：Recommendation 与 Gap

它们应是派生结论，不是模型直接生成的“感觉”：

```text
recommendation
├─ candidate paper/version
├─ target direction/task
├─ novelty / relevance / graph / unread / diversity features
├─ reason codes
├─ supporting evidence
└─ user feedback

gap_hypothesis
├─ scope and definition
├─ corpus/query/index snapshot
├─ task × method × dataset × metric coverage
├─ supporting evidence
├─ contradicting evidence
├─ uncertainty
└─ validation status
```

“没有搜到”不能直接等同于“研究空白”；必须明确 corpus、query、时间和索引边界。

---

## 六、统一 Evidence 模型

建议所有 Scholar 结论都经过统一 evidence record：

```text
evidence_id
subject_type / subject_id
predicate
value
evidence_kind:
  source_fact | extracted_fact | derived_fact |
  model_inference | user_note | external_candidate
paper_id
paper_version_id
block_id
source_locator
extractor_or_model
extractor_or_model_version
confidence
parent_evidence_ids
created_at
```

理想回溯链：

```text
DSH conclusion
→ evidence_id
→ claim / relation / result
→ block_id + span
→ paper_version_id
→ source asset hash
→ TeX file/line or PDF page/bbox
```

应明确区分：

- 原文明确陈述；
- parser/extractor 推导；
- graph/index 派生；
- LLM 推断；
- 用户笔记；
- 自动质量评分；
- 外部 arXiv 候选。

自动笔记、分类和质量分数都不能覆盖原始事实，只能新增带 provenance 的派生记录。

---

## 七、保持固定 16 个 MCP tools 不变

第三阶段暂时不需要增加 MCP tool。现有工具可以继续承担交互层，只需在兼容范围内增强返回内容。

### 继续由 MCP 提供

| MCP 工具组 | 新模型中的职责 |
|---|---|
| `scholar_search` | lexical paper/passages，返回 paper version、命中 block 和查询快照 |
| `scholar_vec_search` | paper-level semantic retrieval，返回 index/model version |
| `scholar_info` | canonical identity、source/version、metadata provenance、TOC block IDs |
| `scholar_section` | section block 及其 source locator |
| `scholar_passages` | chunk/block/span、score breakdown、index ID |
| citation/graph/lineage/stats | 返回 edge/relation evidence IDs 和覆盖范围 |
| list/arxiv search | 区分 local canonical paper 与 external candidate |
| parsed/output reader | 继续作为兼容读取和产物读取 |
| `scholar_auto_notes` | 生成带 evidence footnotes 的 versioned note |
| `scholar_interests` | 维护 research direction / preference state |

工具名称、参数数量和外部语义不变。例如 `scholar_passages` 仍然是“定位段落”，但每个结果可附加：

```text
paper_id
paper_version
block_id
source_locator
chunk_id
index_id
score/vector_rank/bm25_rank
```

这属于结果可验证性的增强，不是 API 语义变化。

### 继续由 CLI / 后台 pipeline 提供

- 下载、去重和 source acquisition；
- parse、PDF fallback、metadata enrichment；
- citation/entity/experiment extraction；
- graph、lexical、vector index build；
- notes/classification/quality rebuild；
- direction sync、change detection 和通知；
- recommender/gap batch computation；
- dataset acquisition 和 experiment execution；
- migration、repair、audit 和 benchmark。

### DSH local / remote 模式

当前 Skill 大量直接执行 `python -m scholar ...`：

- local stdio 模式可以工作；
- remote MCP 模式下，这些命令可能访问本地空 corpus，而不是远端 Scholar。

在不增加 16 个 MCP tools 的前提下，建议：

1. Skill 明确标记 `local-maintenance` 与 `remote-research` capability；
2. remote 模式只通过固定 MCP tools 执行研究读取和 workspace 写入；
3. 远端 ingestion/index/sync 由服务器 scheduler/operator API 执行；
4. 如需用户触发，提供独立的 remote admin CLI client，而不是让 Skill 假设本地 corpus 存在。

---

## 八、建议的第三阶段 PR 拆分

### 前置 PR A：Parser Contract、Fixture Corpus 与基线缺陷

**范围**

- 定义 parsed vNext schema 和旧 JSON 兼容 projection；
- 建立小型、可提交、许可清晰的 TeX/PDF fixture corpus；
- 覆盖 nested input、多主文件、缺失 input、malformed TeX、多语言、公式冲突和 uncited bibliography；
- 增加 parser determinism、loss report、schema validation 和 golden artifact；
- 修复 citation/bibliography 混淆、公式前 100 字符碰撞和 BibTeX author 拆分；
- 旧 search projection 可以有损，但每项删除、替换和截断必须可检测。

**验收**

- 每个 fixture 都有 golden source facts 和预期 warning/loss；
- 同一 source/parser/config 重跑结果和 stable IDs 一致；
- malformed/unsupported 内容产生结构化失败或 warning，不静默吞掉；
- 旧 MCP 仍可读取兼容 projection。

### 前置 PR B：DSH 接入与检索基线可信性

**目标**

- 修复 scoped passage SQL 参数顺序；
- 增加真实 PostgreSQL integration test；
- 解决 `@deepseek-ai/dsh-scholar-native` 无法解析的问题：提供真实可加载插件，或删除该依赖并迁移到已有 DSH extension point；
- 增加真实 DSH Loader composition test；
- 标注 local/remote Skill capability。

**验收**

- paper + section filter 在真实 PG 上返回正确结果；
- `scholar init-dsh` 生成的配置可由真实 DSH Loader 启动；
- remote 模式不会误执行本地 corpus maintenance。

### PR1：Canonical Paper Identity 与 Source Assets

**范围**

- `papers`、`paper_identifiers`、`paper_aliases`、`paper_versions`、`source_assets`；
- DOI/arXiv normalization；
- TeX/PDF/meta artifact hash、acquisition source 和 duplicate candidate；
- 旧 ULID 作为稳定内部 alias。

**验收**

- 同一 arXiv 不同版本不会生成两个 canonical work；
- DOI 与 arXiv 可指向同一 work；
- merge 可审计且保留旧 ID redirect；
- 旧 16 个 MCP tools 仍接受原有 ID。

### PR2：Durable Ingestion / Parse Runs

**范围**

- operation/run、per-paper item、stage attempt、checkpoint、artifact manifest；
- download/parse/enrich/index 的幂等状态；
- parser/config/source hashes、retry、warning、loss 和 failure reason。

**验收**

- 中断后从最后成功 stage 恢复；
- 单篇失败不阻塞其他论文；
- 重复执行不重复下载/建库；
- DSH 可得到 bounded run summary 和 operation ID。

### PR3：Lossless TeX Normalization 与 Source Map

**范围**

- 将 archive 解包、文件读取、include expansion、macro handling 和 text cleaning 拆成显式 stage；
- 保留原始文件清单、编码、relative path、byte/line spans；
- include expansion 生成 source map，不再只返回合并字符串；
- metadata assertion 合并 `meta.json`、TeX、arXiv/DOI 来源，不静默覆盖；
- clean text 作为派生 view，与 source-preserving intermediate representation 分离。

**验收**

- 任一 cleaned span 可回溯到一个或多个 source spans；
- missing input、decode loss、unknown macro、conditional content 都有 warning；
- `meta.json` 与 TeX 冲突同时保留，并按显式 policy 选择 display value；
- parser 不再依赖无来源的字符串覆盖来表达规范化。

### PR4：Document Block Hierarchy + PDF Fallback

**范围**

- 统一 document/block hierarchy；
- stable block ID；
- TeX file/line/byte locator；
- PDF page/bbox locator；
- paragraph、equation、figure、table、algorithm、caption；
- versioned parsed JSON projection。

**验收**

- TeX fixture 和 PDF-only fixture 都能入库；
- 每个 section/formula/passage 都可回溯到 source；
- 重跑相同 parser/version 时 block ID 稳定；
- parser 升级生成新 artifact，而不是静默覆盖。

### PR5：Metadata and Research Entity Extraction

**范围**

- metadata assertion provenance；
- authorship、task、method、dataset、metric、benchmark、experiment、reported result；
- mentions、relations、confidence 和人工确认状态。

**验收**

- 任一实验结果可定位到 table/paragraph；
- 分类结果携带 taxonomy/extractor version；
- 低置信度候选不会直接成为 confirmed fact。

### PR6：Citation Evidence Graph

**范围**

- reference entry、citation mention、resolution candidate/decision；
- edge evidence、intent、context；
- external paper entity；
- 增量 graph projection。

**验收**

- 每条 CITES edge 至少有一条 citation mention；
- resolution key 以 `(from_paper_version, reference_entry)` 为 scope，不使用全局 ref_key；
- 可以解释 DOI/title/arXiv 哪个规则完成解析；
- 错误候选可撤销并重建图；
- citation MCP 返回 edge evidence locator。

### PR7：Versioned Retrieval and RAG

**范围**

- block-bound chunks；
- PostgreSQL FTS 或等价稳定 lexical index；
- multi-model embedding/index manifest；
- passage-level hybrid RRF；
- rank trace、dedup、source display；
- paper/section/passage filters。

**验收**

- 同一查询记录 query/index/model/chunker version；
- 结果可定位到 block/span；
- filter 在真实 PG 工作；
- hybrid 不因 paper-level 过早去重而丢失最佳 passage；
- fixed 16 MCP tools 参数不变。

### PR8：Evidence-bound Notes and Research State

**范围**

- evidence record；
- note revision 和 claim footnote；
- reading event/read status；
- collection、annotation、research direction；
- workspace/user scope。

**验收**

- 自动笔记每个贡献/公式/方法结论带 evidence ID；
- 用户修改笔记不覆盖 auto-generated revision；
- 推荐系统能区分 unread/reading/read；
- DSH session 与 Scholar research state 的职责不混淆。

### PR9：Incremental Direction Sync

**范围**

- direction query version；
- cursor/seen registry；
- arXiv source version/change event；
- durable sync run、retry、digest reason；
- remote scheduler/operator path。

**验收**

- 连续同步只处理新增或变化版本；
- 同一论文升级 v1→v2 产生 version event；
- 失败可从 checkpoint 恢复；
- digest 说明“为什么推荐/为什么变化”。

### PR10：Recommendation and Gap Evidence

**范围**

- candidate generation、reranking、diversity、reason codes；
- feedback events；
- task×method×dataset×metric coverage matrix；
- gap hypothesis、supporting/contradicting evidence 和 uncertainty。

**验收**

- 每个推荐至少给出两类可核查理由；
- 已读/不感兴趣反馈能改变下一次排序；
- gap 输出必须带 corpus/query/index snapshot；
- “未发现证据”与“证明不存在”严格区分。

### PR11：Reproduction and Writing Evidence

**范围**

- experiment spec/run/artifact/environment/dataset/code revision；
- reported result 与 reproduced result；
- claim-citation registry；
- survey/review/writing 输出的 evidence validator。

**验收**

- 每个 reproduced metric 可回溯到 run、code、dataset、seed 和环境；
- synthetic quick run 不会被标记为 full reproduction；
- 写作草稿中的学术 claim 可检查是否有 evidence；
- DSH workspace 产物和 Scholar factual state 分层保存。

---

## 九、实施优先级

### P0：先让研究结果可信

```text
前置 PR A：Parser Contract / Fixtures
→ PR1 Identity / Source Assets
→ PR2 Durable Ingestion / Parse Runs
→ PR3 Lossless TeX Normalization / Source Map
→ PR4 Document Blocks / PDF
```

这五批共同构成“清洗 + 整理 + 结构化”的 P0，不应被压缩成一个 parser 重写 PR：

```text
清洗 = loss-aware normalization views
整理 = identity + version + source asset + operation/artifact lineage
结构化 = blocks + entities + mentions + stable locators
```

完成后，Scholar 才真正拥有稳定的“哪篇论文、哪个版本、哪段原文”，并能说明清洗过程中发生了什么。

### P1：再让检索和关系可解释

```text
PR5 Research Entities
→ PR6 Citation Evidence
→ PR7 Versioned Retrieval
→ PR8 Evidence Notes / State
```

完成后，DSH 才能输出可回溯的综述、精读、引用分析和研究证据。

### P2：最后做研究智能

```text
PR9 Incremental Sync
→ PR10 Recommendation / Gap
→ PR11 Reproduction / Writing
```

推荐、空白发现和自动复现必须建立在 P0/P1 之上，否则只是把启发式和 LLM 推断包装成产品能力。

---

## 十、最终建议

第三阶段应先完成 **Parser Contract / Fixture Corpus**，随后进入 **Canonical Paper Identity / Source Assets**。清洗、整理和结构化应覆盖 P0 的前五批，而不是作为推荐、Gap 或高级 RAG 后面的优化项。

不建议直接在现有 `_extract_sections()` 上继续堆更多 regex 并把结果覆盖回同一个 JSON。正确演进路径是：

```text
immutable source asset
→ source-preserving parse IR + warnings/loss
→ versioned document blocks + locators
→ compatible cleaned/search projection
→ entity/citation/index/note derived artifacts
```

DSH 和固定 16 个 MCP tools 无需先扩充工具数量；它们只需逐步返回 version、block、locator、provenance 和 index metadata。下载、parse、rebuild、migration 和 benchmark 继续属于 Scholar 后台 pipeline/CLI。

不建议第三阶段一开始就做：

- 新推荐 UI；
- 新 gap 聊天工具；
- 新 MCP tool；
- 大规模 Neo4j/多租户优化；
- 更复杂的 LLM 自动摘要；
- 直接承诺“自动复现”。

最重要的产品里程碑不是“Skill 更多”，而是：

> DSH 给出的每个学术结论，都能稳定回到某篇论文的某个版本、某个 block、某个原文位置，并说明该结论是原文事实、程序派生还是模型推断。

---

## 十一、五人团队的具体职责划分

### 1. 分工原则

五个人不能简单按“每人领几个 PR”分配。第三阶段的高风险点集中在 schema、parser、locator、artifact lineage 和 MCP compatibility；应建立五个长期责任域，每个人从设计、实现、测试、迁移到运行文档对自己的责任域负责。

共同规则：

1. 每个 PR 只有一名 owner；owner 对接口、实现、测试、迁移和文档共同负责。
2. QA 不能集中交给第五个人；每个 owner 必须提交本责任域的 unit、fixture 和 failure-path tests。
3. 第五个人负责跨模块 integration/E2E，不替其他人补基础测试。
4. schema 变更必须由人员 1 和人员 4 双重批准。
5. parser/locator 语义变更必须由人员 2 和人员 3 双重批准。
6. MCP 返回值、DSH Loader 或兼容 projection 变更必须由人员 5 批准。
7. 下游人员不得在自己的 PR 中临时修改上游 contract；发现缺口时回到上游 owner 修订。

### 2. 人员 1：论文事实模型与数据治理负责人

**最终责任**

保证系统能回答：

```text
这是哪一篇 work？
这是哪个 version？
来自哪个 source asset？
这个字段是谁、何时、通过什么规则产生的？
发生冲突、合并或 parser 升级后如何追溯？
```

**长期拥有的模型**

- canonical paper/work identity；
- DOI、arXiv、内部 ULID 和 alias normalization；
- paper version 和 manifestation；
- source asset、artifact hash 和 acquisition provenance；
- metadata assertion、confidence、conflict 和 selected display value；
- stable ID 算法规范；
- evidence、entity 和 relation 的基础类型；
- schema versioning、数据字典和 migration policy。

**主要代码与文档边界**

- PostgreSQL 核心 schema 和 migration；
- parsed vNext JSON Schema/Pydantic model；
- identity resolver 和 alias/merge service；
- metadata assertion service；
- source asset manifest；
- schema/data dictionary、ID 和 hash 规范。

**P0 具体任务**

1. 主导前置 PR A：
   - 定义 source fact、extracted fact、derived fact 和 model inference；
   - 定义 parsed vNext 顶层字段；
   - 定义 parser warning/loss/error 的统一格式；
   - 定义旧 parsed JSON 的兼容 projection；
   - 与人员 2、3 共同确定 fixture 的 golden facts。
2. 主导 PR1：
   - 实现 `papers`、`paper_identifiers`、`paper_aliases`、`paper_versions`、`source_assets`；
   - 建立 DOI/arXiv normalization 和唯一约束；
   - 设计 duplicate candidate、merge decision、redirect；
   - 保存 TeX/PDF/meta 的 hash、来源和获取时间；
   - 保证旧 ULID 和 16 个 MCP tools 仍可解析。
3. 支持 PR3/PR4：
   - 审核 block/formula/mention ID 是否稳定；
   - 审核 source locator 是否引用明确的 version 和 asset；
   - 禁止清洗结果覆盖 source fact。

**P1/P2 具体任务**

- 主导 PR5 的 entity/metadata assertion model；
- 为 PR6 提供 reference entry、resolution candidate 和 decision model；
- 为 PR8 提供 evidence/note revision 的事实边界；
- 为 PR10 提供 gap hypothesis 与 recommendation reason schema；
- 为 PR11 提供 experiment/run/artifact lineage 类型。

**必须交付**

- 数据模型图；
- migration 和 rollback；
- JSON schema 与示例；
- ID/hash 规范；
- identity merge/redirect 测试；
- metadata conflict 测试；
- 旧 ID 兼容测试。

**验收指标**

- 同一 work 的 DOI/arXiv/version 不产生错误重复；
- merge 后旧 ID 可重定向；
- 任一 parsed/derived artifact 都能指向 source asset 和 producing run；
- parser 升级不会静默覆盖旧 artifact；
- schema migration 可往返验证。

**禁止越界**

- 不直接实现 TeX regex、PDF layout 或 embedding ranking；
- 不为方便某个 extractor 随意增加无 provenance 的数据库字段；
- 不把 quality、tags、summary 写回 source-fact artifact。

### 3. 人员 2：TeX ingestion 与无损规范化负责人

**最终责任**

保证任意 TeX source 从 archive 到 normalized view 的每一步都可解释、可重复、可报告信息损失。

**长期拥有的能力**

- tar/zip 安全解包；
- source file discovery 和 main document selection；
- encoding detection/decoding；
- `\input` / `\include` expansion；
- macro、conditional 和 comment handling；
- TeX metadata/section/formula/citation/reference extraction；
- source map；
- parser warning、loss report 和 determinism。

**主要代码边界**

- `scholar/tex_parser.py` 的拆分和替代模块；
- archive/source reader；
- include resolver；
- TeX tokenizer/normalizer；
- TeX source-map builder；
- TeX fixture corpus 和 golden parser artifacts。

**P0 具体任务**

1. 参与前置 PR A：
   - 提交 nested input、cyclic input、missing input、multiple main files、malformed TeX、Unicode、多语言、unknown macro、formula collision 和 uncited bibliography fixtures；
   - 为每个 fixture 标注预期 source facts、warnings 和 losses；
   - 修复 citation/bibliography 混淆、公式前 100 字符碰撞和作者拆分。
2. 主导 PR3：
   - 将 archive、read、include、macro、normalize、extract 拆成显式 stage；
   - 保存每个 source file 的 relative path、encoding、hash 和 byte/line ranges；
   - include expansion 同时产生 expanded text 和 source map；
   - missing input、decode loss、unknown macro、conditional branch 产生结构化 warning；
   - clean/search text 成为派生 view，不替代 source-preserving IR；
   - 合并 `meta.json`、TeX 和外部 metadata assertions，但不静默覆盖冲突。
3. 支持 PR4：
   - 将 TeX section、paragraph、formula、theorem、proof、figure、table、algorithm 和 caption 转成统一 block input；
   - 给人员 3 提供稳定 source span。

**P1/P2 具体任务**

- 主导 PR6 中 TeX citation mention/context extraction；
- 提取 citation command、ref key、section、sentence/context 和 source locator；
- 维护 reference entry 与正文 mention 的严格区分；
- 支持 PR11 的 theorem/formula/experiment method evidence。

**必须交付**

- fixture source archive；
- golden parsed IR；
- warning/loss snapshots；
- parser stage API；
- source-map tests；
- deterministic parse tests；
- malformed source failure tests；
- parser benchmark。

**验收指标**

- 同一 source/parser/config 重跑 byte-level canonical output 一致；
- 任一 normalized span 可回溯到一个或多个 TeX source spans；
- missing/decode/unsupported 内容不静默消失；
- bibliography entry 不再自动等同 citation mention；
- theorem、proof、table、figure 和 algorithm 不再被无痕删除。

**禁止越界**

- 不定义 canonical paper identity；
- 不自行创建数据库 projection；
- 不改变 MCP 输出 contract；
- 不为了通过 fixture 将未知内容统一替换成无来源占位符。

### 4. 人员 3：文档结构、PDF 与 locator 负责人

**最终责任**

保证 TeX 和 PDF 都能形成同一套可定位的 document block hierarchy，并让 section、paragraph、formula、figure、table、algorithm 和 citation context 可以稳定引用。

**长期拥有的能力**

- document tree/block hierarchy；
- stable block、paragraph、formula、figure/table IDs；
- parent/order/heading hierarchy；
- PDF text/layout extraction；
- page、bbox 和 reading order；
- TeX/PDF cross-source alignment；
- figure/table/algorithm/caption/theorem/proof 结构；
- locator serialization 和 display。

**主要代码边界**

- document/block model builder；
- PDF parser/layout adapter；
- TeX IR → block adapter；
- block locator 和 source alignment；
- PDF fixtures、golden blocks 和 locator regression tests。

**P0 具体任务**

1. 参与前置 PR A：
   - 提交 PDF-only、multi-column、formula、figure/table、page-header/footer、多语言 fixtures；
   - 定义 golden block tree、page/bbox 和 reading order；
   - 与人员 1 定义 stable block ID；
   - 与人员 2 定义 TeX source-map 到 block locator 的接口。
2. 主导 PR4：
   - 建立统一 `document_blocks` hierarchy；
   - 支持 section、paragraph、equation、theorem、proof、definition、figure、table、algorithm、caption；
   - 实现 PDF-only fallback；
   - 保存 TeX file/line/byte 与 PDF page/bbox locator；
   - 相同 source/parser/version 重跑保持 stable IDs；
   - parser 升级产生新 block artifact version。
3. 提供 compatibility projection：
   - 从 block tree 生成旧 `sections`、`formulas` 和 cleaned text；
   - 保证旧 reader/search 可继续工作。

**P1/P2 具体任务**

- 支持 PR5 从 table/paragraph 提取 reported result；
- 为 PR6 citation mention 提供 block/sentence locator；
- 为 PR7 提供 block-bound chunk 输入；
- 主导 PR11 的 reported result ↔ reproduced result locator；
- 验证 DSH 展示的 evidence locator 可回到原文。

**必须交付**

- block type registry；
- stable ID tests；
- PDF parser/layout tests；
- TeX/PDF locator tests；
- cross-source alignment report；
- compatibility projection tests；
- PDF-only E2E fixture。

**验收指标**

- 每个可搜索 passage 都绑定 block ID；
- 每个公式、引用上下文和报告结果都能定位到 TeX 或 PDF；
- PDF 多栏顺序和 header/footer 处理有可量化 fixture 结果；
- 同一源重跑 stable IDs 不变；
- TeX 缺失时 PDF-only 论文仍可进入阅读和检索链路。

**禁止越界**

- 不维护 ingestion transaction 或 vector index；
- 不定义外部 paper identity；
- 不在 PDF adapter 中直接生成 recommendation、quality 或 summary。

### 5. 人员 4：持久化 pipeline、PostgreSQL 与检索负责人

**最终责任**

保证 download、parse、ingest、projection、chunk、embed、graph 和 sync 是幂等、可恢复、可审计且在 file-only/PostgreSQL 模式下语义一致。

**长期拥有的能力**

- operation/run/stage/item state；
- checkpoint、retry 和 failure classification；
- artifact manifest；
- PostgreSQL transaction/projection；
- JSON/PG semantic parity；
- graph/RAG incremental rebuild；
- lexical/vector/hybrid retrieval；
- chunker/embedding/index version；
- index manifest 和 rank trace。

**主要代码边界**

- `scholar/db.py`；
- `scholar/commands/paper_ops.py`；
- `scholar/kb_update.py`；
- `scholar/commands/sync_ops.py`；
- `scholar/rag.py`；
- `scholar/vecstore.py`；
- PostgreSQL integration test harness。

**P0 具体任务**

1. 参与前置 PR A：
   - 建立真实 PostgreSQL fixture；
   - 验证 JSON schema、DB constraints 和 projection parity；
   - 修复 scoped passage SQL 参数顺序。
2. 支持 PR1：
   - 实现 migration、constraints、upsert 和 rollback；
   - 保证 identity/source schema 可高效查询。
3. 主导 PR2：
   - 建立 operation、run item、stage attempt、checkpoint、artifact manifest；
   - download/parse/enrich/index 使用显式幂等键；
   - 保存 source/parser/config/artifact hashes；
   - 单篇失败不阻塞 batch；
   - 中断后从最后成功 stage 恢复；
   - 失败原因和 retry policy 可查询。
4. 支持 PR3/PR4：
   - 事务化保存 source IR、blocks、locators 和 compatibility projections；
   - 删除 delete-and-reinsert 的不稳定 child IDs；
   - 保证 file-only 与 PostgreSQL 返回同一业务语义。

**P1/P2 具体任务**

- 主导 PR7：FTS、block chunks、multi-model embeddings、hybrid RRF、rank trace 和 index manifest；
- 主导 PR9：direction cursor、seen registry、version change event 和 durable sync；
- 支持 PR6 的增量 citation graph projection；
- 为 PR10 保存 corpus/query/index snapshot；
- 为 PR11 保存 run/code/dataset/environment artifacts。

**必须交付**

- migrations/rollback；
- real PostgreSQL tests；
- transaction/failure/retry tests；
- idempotence tests；
- JSON/PG parity tests；
- index manifest；
- retrieval benchmark；
- rebuild/recovery runbook。

**验收指标**

- 相同幂等键重复执行不重复下载、插入或嵌入；
- 任一索引结果可追溯到 source/parser/chunker/model/index version；
- file-only 与 PG 模式返回等价字段；
- batch 单项失败可恢复；
- scoped paper/section filter 在真实 PG 工作；
- parser/index 升级按 hash 精确重建受影响 artifact。

**禁止越界**

- 不在存储层猜测 metadata 或 source locator；
- 不让 mtime 成为唯一增量依据；
- 不把模型输出直接写入 source-fact tables；
- 不修改 security/compliance 配置绕过 migration 或 CI。

### 6. 人员 5：DSH/MCP 集成、证据质量与发布负责人

**最终责任**

保证 Scholar 的新事实模型真正被 DSH 学者模式安全使用，固定 16 个 MCP tools 兼容，且每个阶段有真实集成证据而不是只有 unit tests。

**长期拥有的能力**

- `scholar_mcp` 返回 contract；
- old/new projection compatibility；
- DSH Loader composition；
- local/remote capability separation；
- evidence rendering；
- end-to-end fixture journeys；
- corpus quality benchmark；
- release gate、migration rehearsal 和 regression report。

**主要代码边界**

- `scholar_mcp/server.py`；
- DSH configuration/template/loader adapter；
- MCP contract tests；
- DSH real composition tests；
- E2E fixture runner；
- quality benchmark/reporting；
- release checklist 和 operator docs。

**P0 具体任务**

1. 主导前置 PR B：
   - 解决 `@deepseek-ai/dsh-scholar-native` 无法加载的问题；
   - 增加真实 DSH Loader composition test；
   - 定义 local-maintenance 与 remote-research capability；
   - 验证 remote Skill 不会误执行本地 corpus CLI；
   - 为固定 16 tools 建立 contract snapshots。
2. 横向支持 PR1-PR4：
   - 验证旧 paper ID、旧参数和旧读取流程兼容；
   - 逐步增加 `paper_version`、`source`、`block_id`、`locator`、`provenance`、`confidence`、`parser_version`；
   - 建立“搜索→info→section/passages→source locator”E2E；
   - 建立 TeX、PDF-only、malformed source 的 DSH journey；
   - 汇总每个 fixture 的 pass/fail/loss 指标。

**P1/P2 具体任务**

- 主导 PR8：evidence-bound notes、reading event、research state 和 workspace/user scope；
- 主导 PR10：recommendation reason、gap evidence、feedback 和 uncertainty 的 MCP/DSH presentation；
- 支持 PR11 的 claim-citation/evidence validator；
- 维护九个 Scholar Mode 用户旅程的 keyless regression；
- 执行发布前 migration、reindex、rollback 和 compatibility rehearsal。

**必须交付**

- MCP contract snapshots；
- real DSH Loader test；
- local/remote mode tests；
- nine-journey E2E matrix；
- fixture corpus quality report；
- compatibility report；
- release checklist；
- migration/reindex/rollback rehearsal report。

**验收指标**

- 固定 16 个 tools 名称和参数不变；
- 新字段对旧客户端向后兼容；
- DSH session log 能重建模型看到的 evidence；
- 每个用户旅程至少有一个 keyless fixture E2E；
- 发布前所有 migration、reindex 和 rollback 步骤可重复执行；
- 任何无法定位或发生 loss 的证据在 DSH 输出中显式标记。

**禁止越界**

- 不承担其他四人的 unit tests；
- 不在 MCP server 内复制 identity/parser/retrieval 逻辑；
- 不通过新增 MCP tool 绕过已有 contract；
- 不把“E2E 通过”当作真实 corpus 准确率证明。

### 7. PR Owner、Contributor 与 Reviewer 矩阵

| 批次 | Owner | 必须参与 | 必须批准 |
|---|---|---|---|
| 前置 PR A：Parser Contract/Fixtures | 人员 1 | 人员 2、3、4、5 | 人员 2、4 |
| 前置 PR B：DSH/检索基线 | 人员 5 | 人员 4 | 人员 1、4 |
| PR1：Identity/Source Assets | 人员 1 | 人员 4、5 | 人员 4、5 |
| PR2：Durable Runs | 人员 4 | 人员 1、5 | 人员 1、5 |
| PR3：Lossless TeX/Source Map | 人员 2 | 人员 1、3、4、5 | 人员 3、5 |
| PR4：Blocks/PDF/Locators | 人员 3 | 人员 1、2、4、5 | 人员 2、4、5 |
| PR5：Metadata/Research Entities | 人员 1 | 人员 2、3 | 人员 3、5 |
| PR6：Citation Evidence | 人员 2 | 人员 1、3、4 | 人员 1、5 |
| PR7：Versioned Retrieval/RAG | 人员 4 | 人员 3、5 | 人员 3、5 |
| PR8：Evidence Notes/State | 人员 5 | 人员 1、4 | 人员 1、4 |
| PR9：Incremental Direction Sync | 人员 4 | 人员 1、5 | 人员 1、5 |
| PR10：Recommendation/Gap | 人员 5 | 人员 1、4 | 人员 1、4 |
| PR11：Reproduction/Writing Evidence | 人员 3 | 人员 1、4、5 | 人员 4、5 |

### 8. 可并行和不可并行的工作

**第一波可以并行**

```text
人员 1：parsed vNext schema + identity/source proposal
人员 2：TeX fixture corpus + current parser failure characterization
人员 3：PDF fixture corpus + block/locator proposal
人员 4：real PostgreSQL harness + scoped query fix + run model proposal
人员 5：DSH Loader/MCP contract baseline
```

这五项产出汇入前置 PR A/B；在 contract 未冻结前，不开始大规模 parser/DB 实现。

**第二波可以部分并行**

```text
PR1 Identity/Source Assets
PR2 Durable Runs
PR3 Lossless TeX
```

但约束是：

- PR2 使用 PR1 已冻结的 source/version IDs；
- PR3 使用前置 PR A 已冻结的 warning/loss/source-map contract；
- 人员 4 不在 PR2 中自行定义 parser artifact；
- 人员 2 不在 PR3 中自行定义 database tables。

**第三波不可提前**

PR4 必须等待 PR1 和 PR3 的关键 contract 可用；否则 block IDs 和 locators 会被反复推翻。

**P1 不可提前**

PR5-PR8 只有在以下 P0 gate 全部通过后启动：

```text
identity/version/source asset 稳定
parse run 和 artifact lineage 可查询
TeX source map 可用
PDF/TeX blocks 有 stable IDs
loss/warning 可见
real PostgreSQL parity 通过
固定 16 MCP compatibility 通过
```

### 9. 每个 owner 的 Definition of Done

任何 PR 只有同时满足以下条件才算完成：

1. contract/schema 先于实现落地；
2. happy path、failure path、idempotence 和 migration tests 齐全；
3. fixture/golden artifact 可重复；
4. 新 artifact 有 producer/version/hash；
5. 新 evidence 有 source locator 或明确标记无法定位；
6. file-only 与 PostgreSQL 语义差异被消除或显式记录；
7. 旧 MCP tools compatibility 通过；
8. operator/rebuild/rollback 文档已更新；
9. owner 完成自测，指定 reviewer 完成跨责任域审查；
10. 人员 5 的 integration gate 通过，但不替代 owner tests。
