快速查看某篇论文的详细信息，包括元数据、关键概念、引用关系和质量评分。

## 执行步骤
1. 用 `python -m scholar info <ULID>` 获取基础信息
2. 如果存在 `output/notes/<ULID>-quality.json`，展示质量评分
3. 如果存在 `output/notes/<ULID>.md`，展示阅读笔记摘要
4. 用 `python -m scholar cite-network <ULID>` 展示引用关系（前向 + 后向各 5 篇）
