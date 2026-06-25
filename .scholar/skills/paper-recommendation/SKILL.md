---
name: paper-recommendation
description: "基于引用网络、研究方向或阅读缺口推荐论文"
output_contract:
  path: output/drafts/
  format: markdown
  required_fields:
    - recommendations
    - reasons
  citation_check: true
---

## 触发
当用户说"推荐论文"、"有什么值得读的"、"下一篇读什么"、"推荐相关论文"时执行此流程。

## 流程

### Step 1: 理解推荐需求
与用户确认推荐场景：
- 基于某篇论文的延伸阅读？→ 进入 Step 2a
- 基于某研究方向的入门推荐？→ 进入 Step 2b
- 基于已读论文的缺口补充？→ 进入 Step 2c

### Step 2a: 基于引用关系的推荐
找到用户指定的论文，分析其引用网络：
```bash
python -m scholar cite-network <ULID>
python -m scholar graph-stats
```
利用 centrality 数据（in_degree, out_degree, bridge_score）推荐：
- **前向引用**：这篇论文引用了哪些重要工作？（必须读的前置知识）
- **后向引用**：哪些后续论文引用了这篇？（追踪最新进展）
- **桥接论文**：连接不同子领域的关键论文（扩展视野）

如果 Neo4j 已启动，使用图谱查询：
```bash
python -m scholar graph-query <概念>
```

### Step 2b: 基于方向的推荐
```bash
python -m scholar search "<方向关键词>"
python -m scholar rag-search "<方向关键词>" --hybrid
python -m scholar classify --list-tags
python -m scholar arxiv-search "<方向关键词>" --max 15
```
利用分类标签和 RAG 混合搜索从搜索结果中筛选：
- 高引用量的经典论文（通过 centrality 数据）
- 最近 2 年的最新工作
- 覆盖不同子方向的多样性推荐（用 `tags.domains` 过滤）

### Step 2c: 基于阅读缺口的推荐
```bash
python -m scholar list-papers
```
查看已读论文列表，识别：
- 某个引用链中的缺失环节（A 引用了 C，但没读中间的 B）
- 某概念图谱中未覆盖的重要节点
- 时间线上的空白年份

### Step 3: 排序与说明
对推荐论文按以下维度排序：
- **必读**：对理解目标方向不可或缺
- **推荐**：有重要参考价值
- **可选**：拓展视野

每篇推荐附上：
- 一句话说明为什么推荐
- 与用户已读/目标论文的关系
- 预计阅读难度（基于公式密度和方法复杂度）

### Step 4: 输出
输出到 `output/notes/recommendations-<topic>.md`：

```markdown
## 论文推荐: <topic>

### 必读 (N篇)
1. **<Title>** (<Year>) — <推荐理由>
   - Paper ID: <ULID>
   - 关联: <与目标的关系>

### 推荐 (N篇)
...

### 可选 (N篇)
...
```

## 注意事项
- 推荐要基于实际数据（引用关系、概念图谱），不要凭印象推荐
- 如果推荐了本地库没有的论文，明确标注并提供 arXiv 链接
- 考虑用户已有的阅读进度（notes/ 目录下的阅读笔记）

## Next Steps

推荐完成后，自然的后续动作：

- **`/paper-deep-dive`** — 对推荐的 Top 论文逐一精读
- **`/cold-start`** — 如果推荐涉及陌生领域，先用冷启动建立知识地图

> 传递数据：推荐列表中的论文 ULID 和推荐理由可直接传给 `/paper-deep-dive`。
