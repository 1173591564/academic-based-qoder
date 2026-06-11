---
name: research-survey
description: "Conduct comprehensive literature surveys on any research topic"
---

## 触发
当用户说"调研 XX 方向"、"survey XX"、"帮我了解 XX 领域"时执行此流程。

## 流程

### Step 0: 预检查
```bash
python -m scholar stats
```
确认知识库状态。如果解析论文数为 0，先执行 `parse-all`。
检查是否有预生成的分类标签：`python -m scholar classify --list-tags`

### Step 1: 本地知识库搜索（双路搜索）
```bash
python -m scholar search "<关键词>"
python -m scholar rag-search "<关键词>" --hybrid
```
- 关键词搜索：精确匹配标题/摘要
- RAG 混合搜索：语义相似度 + BM25 关键词融合，发现语义相关但关键词不同的论文
读取相关论文的 `output/parsed/<ULID>.json`，同时检查是否有预生成笔记：`output/notes/<ULID>.md`

### Step 2: arXiv 外部搜索
```bash
python -m scholar arxiv-search "<关键词>" --max 15
```
补充本地库可能缺失的最新论文。

### Step 3: 关键词扩展
根据 Step 1-2 的结果，识别相关子主题和近义词，再次搜索。例如用户说"MoE"，你应同时搜索 "Mixture of Experts", "sparse experts", "routing algorithm" 等。

### Step 4: 深度阅读关键论文
对搜索结果中最重要的 5-10 篇论文，先检查预生成数据：
- 阅读笔记：`output/notes/<ULID>.md`（已提取摘要、贡献、公式）
- 质量评分：`output/notes/<ULID>-quality.json`（7 维度评分）
- 分类标签：读取 `output/parsed/<ULID>.json` 的 `tags` 字段
如果预生成笔记已存在，直接基于笔记快速分析；否则读取完整 JSON 做深度阅读。

### Step 5: 概念图谱分析
```bash
python -m scholar graph-query <概念ID>
```
从已读论文和 Neo4j 概念图谱中提取：
- 核心概念和方法（利用 `classify --list-tags` 获取标签体系）
- 概念之间的 REPLACES 关系（技术演化证据）
- 时间脉络（按年份排列发展线索）

### Step 6: 生成调研报告
输出到 `output/drafts/survey-<topic>.md`，结构如下：

```markdown
## <Topic> 研究调研

### 研究脉络
按时间线梳理关键发展节点。

### 核心方法分析
分类介绍主要方法/流派，每类引用代表性论文。

### 关键论文详析
选取 3-5 篇最重要的论文做深度分析。

### 方法对比
用表格对比不同方法的优缺点。

### 开放问题与未来方向
识别尚未解决的问题和潜在研究方向。

### 参考文献
列出所有引用论文的 paper_id。
```

## 注意事项
- 始终优先使用本地知识库中的数据，它包含 TeX 源码级的精确信息
- 引用论文时使用 paper_id 格式，便于追溯
- 如果某方向本地库完全没有论文，明确告知用户并建议从 arXiv 补充
