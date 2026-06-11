---
name: kb-maintenance
description: "Knowledge base health checks, data cleanup, and incremental updates"
---

## 触发
当用户说"维护知识库"、"清理数据"、"更新解析"、"知识库健康检查"、"修复解析"时执行此流程。

## 流程

### Step 1: 知识库健康检查
```bash
python -m scholar stats
```
检查关键指标：
- 总论文数 vs 已解析数
- 各字段的覆盖率（标题/作者/年份/摘要/章节/公式/引用）
- 解析失败的论文列表

### Step 2: 扫描一致性
```bash
python -m scholar scan
```
对比 `data/papers/` 和 `output/parsed/` 目录：
- 有无新增的论文目录未解析？
- 有无孤立的 JSON 文件（对应论文目录已删除）？

### Step 3: 补全缺失字段

**元数据补全**：
```bash
python -m scholar year-fix --apply
python -m scholar author-fix --apply
```
利用 Lean4 Database.lean + arXiv API 交叉引用补全年份和作者。

**低质量解析修复**：
对字段覆盖率低的论文（如标题为 null、作者为空），逐一处理：
1. 重新解析：`python -m scholar parse <ULID>`
2. 如果仍然失败，手动读取 TeX 源码修复
3. 对于只有 PDF 的论文，用 PyMuPDF 提取元数据

### Step 4: 引用解析
检查 citations 中的引用是否已解析为库内论文：
```bash
python -m scholar cite-resolve --apply
```
自动匹配库内论文 + arXiv API 查询 + 创建 Neo4j ExternalPaper 节点。

### Step 5: Neo4j 图谱同步
如果 Neo4j 已启动：
```bash
python -m scholar graph-build
```
重新构建引用网络和概念图谱，确保与最新解析数据一致。

### Step 5.5: 批量预处理同步
```bash
python -m scholar auto-notes          # 重新生成阅读笔记
python -m scholar quality-score --all # 重新评分
python -m scholar classify --all      # 重新分类
```
确保预生成数据与最新解析数据一致。

### Step 6: RAG 索引同步
如果 RAG 服务可用：
```bash
python -m scholar rag-index
```
重建向量索引，确保新增论文可被语义检索。

### Step 7: 输出维护报告
输出到 `output/notes/maintenance-report-<date>.md`：

```markdown
## 知识库维护报告: <date>

### 数据概览
- 论文总数: N
- 已解析: N (XX%)
- 字段覆盖率: 标题 XX%, 作者 XX%, 年份 XX%, ...

### 本次操作
- 新解析: N 篇
- 年份补全: N 篇
- 重新解析: N 篇
- 引用匹配: N 条

### 待处理问题
- 解析失败: N 篇 (列出 ULID 和原因)
- 缺失 TeX 源码: N 篇
- 未匹配引用: N 条

### 建议
- ...
```

## 定期维护建议
- 每次新增论文后执行 Step 1-3
- 每月执行一次完整检查（Step 1-7）
- 季度性重新全量解析（解析器升级后质量会提升）

## 注意事项
- 维护操作不要删除任何已有数据，只做增量更新
- 如果全量重新解析，先备份旧的 parsed/ 目录
- 对于持续解析失败的论文，记录失败原因并标记为"需人工处理"
