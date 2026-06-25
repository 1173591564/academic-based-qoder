---
name: citation-network
description: "分析引用网络，识别关键论文和桥接节点"
output_contract:
  path: output/drafts/
  format: markdown
  required_fields:
    - network
    - key_papers
    - bridges
  citation_check: true
---

## 触发
当用户说"分析引用网络"、"引用关系"、"领域脉络"、"谁引用了谁"、"桥接论文"时执行此流程。

## 前置条件
Neo4j 已启动：`cd infra && docker compose up -d neo4j`
引用网络已构建：`python -m scholar graph-build`

## 流程

### Step 1: 全局网络统计
```bash
python -m scholar graph-stats
python -m scholar cite-network
```
获取引用网络的全局概览：
- Paper/Innovation 节点数
- CITES/HAS_CONCEPT/REPLACES/RELATED_TO 边数
- 已解析 vs 未解析引用数
- 孤立节点数
- Top 10 被引论文 + Top 10 桥接论文（基于 centrality 计算）

### Step 2: 单论文引用分析
对用户关心的论文：
```bash
python -m scholar cite-network <ULID>
```
分析：
- **后向引用**（backward）：这篇论文引用了哪些工作？→ 理解其知识基础
- **前向引用**（forward）：哪些论文引用了这篇？→ 追踪其学术影响
- **引用深度**：最长引用链有多长？

### Step 3: 概念关联分析
如果 Neo4j 概念图谱已构建：
```bash
python -m scholar graph-query <概念ID>
```
查看：
- 该概念关联了哪些论文？
- 与该概念共现的其他概念有哪些？
- 概念的时间分布（哪年最活跃）

### Step 4: 识别关键节点
利用 `graph-stats` 已计算的中心度数据：
- **高入度论文**：被引最多的经典工作（`in_degree`）
- **高出度论文**：综述性工作（`out_degree`）
- **桥接论文**：`bridge_score = in_deg * out_deg / (in_deg + out_deg)` 最高的论文
- **引用路径**：两篇论文之间的最短引用路径

### Step 5: 时间线构建
结合论文的年份信息：
```bash
python -m scholar list-papers --year <Y>
```
按年份梳理引用关系，构建领域发展时间线：
- 哪些年份是关键突破期？
- 哪些论文标志着新方向的开始？
- 哪些概念在哪个时期最活跃？

### Step 6: 输出
输出到 `output/drafts/citation-network-<topic>.md`：

```markdown
## 引用网络分析: <topic>

### 网络概览
- 节点: N 篇论文
- 边: M 条引用关系
- ...

### 关键论文
| 论文 | 年份 | 入度(被引) | 出度(引用) | 角色 |
|------|------|-----------|-----------|------|
| ...  | ...  | ...       | ...       | 经典/桥接/综述 |

### 发展时间线
<按年份梳理的关键事件>

### 子领域结构
<识别出的子领域及其关联>
```

## 注意事项
- 引用网络的质量取决于解析的 citations 字段覆盖率
- 部分论文引用的是库外论文（to_paper 为 null），需结合 arXiv 补充
- 如果 Neo4j 未启动，可以用 `citations` 字段手动分析，但功能受限

## Next Steps

引用网络分析完成后，自然的后续动作：

- **`/paper-deep-dive`** — 基于桥接论文和 REPLACES 关系，深入分析概念演化
- **`/paper-recommendation`** — 基于引用网络发现应该读但还没读的论文
- **`/research-gap`** — 从网络结构中的「断裂带」发现研究空白

> 传递数据：关键论文列表和桥接论文可直接传给 `/paper-deep-dive` 或 `/paper-recommendation`。
