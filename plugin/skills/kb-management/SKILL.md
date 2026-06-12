---
name: kb-management
description: "知识库维护与自动更新：健康检查、数据清理、kb-update 一键入库"
---

## 触发
当用户说"维护知识库"、"更新知识库"、"kb-update"、"从 arXiv 补充论文"、"知识库健康检查"时执行此流程。

## 流程

### Step 1: 知识库健康检查
```bash
python -m scholar stats
python -m scholar scan
```
检查关键指标和一致性。

### Step 2: 自动更新（如有搜索需求）
```bash
python -m scholar kb-update --query "<topic>" --max 10
```
一键执行：arXiv 搜索 → 下载 TeX → 批量入库（parse → enrich → graph → notes → quality → classify）。

如果只需处理本地未入库论文（不搜索 arXiv）：
```bash
python -m scholar batch-ingest
```

### Step 3: 元数据回填
```bash
python -m scholar metadata-enrich --apply
```
为已有论文回填 arxiv_id 和 DOI（通过 arXiv API 标题搜索）。

### Step 4: 补全缺失字段
```bash
python -m scholar year-fix --apply
python -m scholar author-fix --apply
```

### Step 5: 引用解析 + 图谱同步
```bash
python -m scholar cite-resolve --apply
python -m scholar graph-build
```

### Step 6: RAG 索引同步
```bash
python -m scholar rag-index
```

### Step 7: 输出维护报告
汇总本次操作结果。

## Next Steps

- **`/research-survey`** — 维护后重新调研，享受更完整的数据支撑
- **`/paper-deep-dive`** — 对新入库的关键论文做深度分析
