---
name: reading-progress
description: "追踪阅读进度、覆盖率分析与阅读计划生成"
---

## 触发
当用户说"阅读进度"、"我读了哪些"、"阅读统计"、"读书报告"、"阅读计划"时执行此流程。

## 流程

### Step 1: 统计已读论文
扫描预生成的阅读笔记和质量评分：
```bash
python -m scholar auto-notes
python -m scholar quality-score --all
```
检查 `output/notes/` 目录下的文件：
- `<ULID>.md` — 自动生成的阅读笔记
- `<ULID>-quality.json` — 质量评分
统计：
- 已读论文总数（有笔记的论文数）
- 按年份分布
- 按会议/期刊分布

### Step 2: 与知识库对比
```bash
python -m scholar list-papers
python -m scholar stats
python -m scholar classify --list-tags
```
计算阅读覆盖率：
- 知识库总论文数 vs 已读论文数
- 按 `tags.domains` 统计各方向的阅读覆盖
- 元数据覆盖率（year/authors/abstract/venue）

### Step 3: 引用网络中的阅读覆盖
如果 Neo4j 可用：
```bash
python -m scholar graph-stats
```
利用已计算的 centrality 数据分析：
- 高入度论文（经典工作）中有多少已读？
- 重要的引用链中有没有断裂？
- 哪些桥接论文（bridge_score 高的）还没读？

### Step 4: 概念覆盖分析
检查概念图谱中各概念的阅读覆盖：
```bash
python -m scholar graph-query <概念>
```
识别：
- 已充分覆盖的概念
- 只有 1-2 篇阅读笔记的概念（需补充）
- 完全没有阅读笔记的概念（知识盲区）

### Step 5: 生成阅读报告
输出到 `output/notes/reading-progress.md`：

```markdown
## 阅读进度报告

### 总体统计
- 知识库: N 篇论文
- 已深度阅读: M 篇 (XX%)
- 本周/本月新增: K 篇

### 按子领域
| 子领域 | 总数 | 已读 | 覆盖率 |
|--------|------|------|--------|
| ...    | ...  | ...  | ...    |

### 阅读里程碑
- 经典论文覆盖: X/Y (列出未读的经典论文)
- 最新进展: <最近读的 5 篇>

### 建议下一步
1. <推荐下一篇读的论文和理由>
2. ...
```

### Step 6: 制定阅读计划（可选）
如果用户要求制定阅读计划：
- 基于引用拓扑排序（先读前置工作）
- 基于概念依赖（先读基础概念）
- 按优先级排列：必读 → 推荐 → 可选

## 注意事项
- 阅读进度仅基于 `output/notes/` 目录下的阅读笔记
- 如果用户之前有非结构化的阅读记录，帮助整理为标准格式
- 阅读计划要考虑论文的依赖关系（先读被引论文）

## Next Steps

查看阅读进度后，自然的后续动作：

- **`/paper-recommendation`** — 基于未读论文和已读论文的知识缺口，推荐下一篇
- **`/research-survey`** — 对未覆盖的方向做调研，发现更多值得读的论文
- **`/deep-read`** — 继续阅读计划中的下一篇论文

> 传递数据：阅读进度中的「未读高优先级论文」列表可直接传给 paper-recommendation。
