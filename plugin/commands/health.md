---
description: 查看知识库健康状态，识别数据完整性问题
---
查看知识库健康状态，识别数据完整性问题。

## 执行步骤
1. 运行 `python -m scholar stats` 检查元数据覆盖率
2. 检查 PG 数据一致性（papers vs sections vs citations 数量是否匹配）
3. 检查 Neo4j 连通性和节点/边数量
4. 检查 RAG chunks 数量是否为 0（未索引）
5. 列出需要补全的项：缺年份、缺作者、未评分、未分类的论文数
6. 给出修复建议（如运行 year-fix、quality-score --all 等）
