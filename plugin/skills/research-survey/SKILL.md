---
name: research-survey
description: "对任意研究主题进行全面文献调研"
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

### Step 6: 生成报告骨架
基于 Step 1-5 收集的数据，先构建报告结构骨架：
- 确定各 section 标题和预计篇幅
- 为每个 section 标注将引用的 paper_id 列表
- 识别数据缺口（哪些 section 论据不足，需要补充搜索）
- 输出骨架到 `output/drafts/survey-<topic>-outline.md`

### Step 7: 增量撰写初稿
按 section 逐步填充，**每写完一个 section 后回顾已写内容确保一致性**：

1. **研究脉络**：按时间线叙事，每个节点标注 paper_id 和年份
2. **核心方法分析**：分类介绍方法/流派，每类引用 2-3 篇代表论文
3. **关键论文详析**：3-5 篇最重要论文的深度分析（优先使用预生成笔记）
4. **方法对比**：表格对比不同方法的优缺点、适用场景
5. **开放问题与未来方向**：基于前述分析推导，不凭空臆想

每个 section 写完后检查：引用的 paper_id 是否都存在于知识库？论证是否与前文一致？

### Step 8: 质量门控
对初稿执行质量检查：
- **覆盖率**：搜索结果中的核心论文/方法是否都被涵盖？
- **引用一致性**：所有 paper_id 引用是否准确、存在于知识库？
- **篇幅均衡**：各 section 是否有明显的详略失当？
- **时间线完整**：是否遗漏重要发展阶段或子方向？

根据检查结果生成修改清单 `output/drafts/survey-<topic>-review.md`：
- `[PASS]` 通过的 section → 保留
- `[REVISE]` 需要修改的 section → 列出具体问题（如"缺少 XX 方法的对比"）
- `[MISSING]` 缺失内容 → 需要补充搜索或重写

### Step 9: 定向修订
根据质量门控的 `[REVISE]` 和 `[MISSING]` 项，执行定向修改：
- 对 `[MISSING]` 项：先 `python -m scholar search` 补充数据，再写入
- 对 `[REVISE]` 项：针对性修改，不重写整个 section
- **最多 2 轮修订**，避免无限循环
- 每轮修订后重新检查该项是否通过

### Step 10: 终稿输出
质量门控全部通过（或 2 轮修订后强制通过），生成最终报告：
输出到 `output/drafts/survey-<topic>.md`

## 迭代写入原则
- 先骨架后填充，避免一次性生成失控
- 每个 section 写完后回顾前文，确保逻辑连贯
- 质量门控要客观量化，`[REVISE]` 必须说明具体缺失项
- 增量写入时，后续 section 可以引用前文已建立的论述和对比

## 注意事项
- 始终优先使用本地知识库中的数据，它包含 TeX 源码级的精确信息
- 引用论文时使用 paper_id 格式，便于追溯
- 如果某方向本地库完全没有论文，明确告知用户并建议从 arXiv 补充

## Next Steps

调研完成后，自然的后续动作：

- **`/paper-deep-dive`** — 对调研中发现的 Top 5 关键论文逐一精读，产出结构化笔记
- **`/citation-network`** — 分析这些论文的引用网络，发现桥接论文和隐藏关系
- **`/research-gap`** — 基于调研结果，识别该方向的研究空白和未来方向

> 传递数据：调研报告中的「关键论文详析」和「参考文献」列表可直接作为后续 skill 的输入。
