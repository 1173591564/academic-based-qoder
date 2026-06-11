---
name: research-gap
description: "Discover research gaps through cross-paper limitation analysis"
---

## 触发
当用户说"找研究方向"、"有什么 gap"、"还有什么没做的"、"研究空白"、"future work"时执行此流程。

## 前置条件
本地知识库已有一定量的解析数据（建议 >100 篇）。

## 流程

### Step 1: 确定分析范围
与用户确认：
- 关注的研究领域/子方向
- 是否基于某篇特定论文展开
- 偏好：理论缺口、方法缺口、还是应用缺口

### Step 2: 收集论文的局限性声明
对目标方向的论文，利用预生成数据快速提取：
```bash
python -m scholar search "<方向>"
python -m scholar classify <ULID>  # 确认论文所属方向
```
读取每篇相关论文的 `output/parsed/` JSON 和 `output/notes/<ULID>.md`，重点关注：
- 预生成笔记中的“Core Contributions”部分（反向推断局限性）
- Conclusion 章节中的 "limitations" 和 "future work"
- Abstract 中提到的未解决问题
- Introduction 中提到的现有方法的不足

### Step 3: 交叉分析缺口
对比多篇论文的局限性声明，识别：
- **共识缺口**：多篇论文都提到但未解决的问题
- **矛盾缺口**：A 论文声称解决了 X，但 B 论文指出 X 仍有问题
- **盲区缺口**：没有任何论文提到但逻辑上应该存在的方向

### Step 4: 引用网络辅助分析
如果 Neo4j 可用：
```bash
python -m scholar graph-query <概念>
python -m scholar cite-network
```
分析：
- 哪些概念的研究论文最少？（可能是冷门但有潜力的方向）
- 哪些概念之间的关联最弱？（可能需要桥接研究）
- 哪些引用链断裂了？（A→B 缺少中间环节）

### Step 5: 概念演化分析
检查 Neo4j 中的替代关系：
```bash
python -m scholar graph-stats
```
查询 REPLACES 边：`MATCH (a)-[:REPLACES]->(b) RETURN a.id, b.id`
已知的替代模式（如 Transformer replaces RNN）暗示：
- 被替代技术中哪些方面仍未被充分解决？
- 当前技术（如 Transformer）自身的局限性是什么？
- 下一个替代者可能是什么方向？

### Step 6: arXiv 最新动态验证
```bash
python -m scholar arxiv-search "<缺口相关关键词>" --max 20
```
确认发现的缺口是否已被最新工作填补：
- 如果 arXiv 上已有相关工作，调整缺口描述
- 如果完全没有相关工作，可能是一个真正的研究空白

### Step 7: 输出
输出到 `output/drafts/research-gaps-<topic>.md`：

```markdown
## 研究缺口分析: <topic>

### 高置信度缺口 (N个)
**缺口 1: <标题>**
- 证据: <哪些论文的局限性提到了这个问题>
- 当前状态: <现有方法能做到什么程度>
- 潜在方向: <可能的解决思路>
- 难度评估: 高/中/低

### 中等置信度缺口 (N个)
...

### 探索性方向 (N个)
...

### 参考文献
<所有分析涉及的论文>
```

## 注意事项
- 缺口发现要基于论文的实际内容，不要凭空臆想
- 每个缺口都要有证据支撑（哪些论文提到了相关问题）
- 区分"真正没人做"和"我们库里没有但别人已经做了"

## Next Steps

发现研究空白后，自然的后续动作：

- **`/paper-recommendation`** — 推荐可能填补这些空白的论文（包括库外论文）
- **`/cold-start`** — 如果空白涉及陌生方向，先用冷启动建立知识地图
- **`/research-survey`** — 对某个具体空白做深入调研

> 传递数据：空白列表中的「方向描述」和「相关论文」可直接传给 paper-recommendation。
