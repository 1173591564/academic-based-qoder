---
name: paper-ingestion
description: "Scan, parse, and import papers into the knowledge base"
---

## 触发
当用户说"入库"、"解析论文"、"导入新论文"、"扫描论文库"时执行此流程。

## 流程

### Step 1: 扫描论文目录
```bash
python -m scholar scan
```
查看所有论文的解析状态：已解析 / 未解析 / 解析失败。

### Step 2: 批量解析未解析论文
```bash
python -m scholar parse-all
```
逐篇解析所有未处理的论文。解析过程会：
- 解压 `source.tar.gz`，自动找到主 `.tex` 文件
- 递归解析 `\input{}` 引用的子文件
- 提取标题、作者、年份、摘要、章节、公式、引用
- 保存为 `output/parsed/<ULID>.json`

### Step 3: 处理解析失败
对于解析失败的论文，逐一诊断：
```bash
python -m scholar info <ULID>
```
常见失败原因：
- 缺少 `source.tar.gz`（只有 PDF）→ 用 PyMuPDF 从 PDF 提取元数据
- `.tar.gz` 实际是 PDF → 同上
- TeX 格式过于特殊 → 手动调整解析策略或标记为需人工处理

### Step 4: 补全缺失元数据
```bash
python -m scholar year-fix --apply
python -m scholar author-fix --apply
```
交叉引用 Lean4 Database.lean 和 arXiv API 补全缺失的年份和作者。

### Step 5: 批量预处理
```bash
python -m scholar auto-notes          # 生成阅读笔记
python -m scholar quality-score --all # 7 维度质量评分
python -m scholar classify --all      # 分类标签
```
为所有论文生成预计算数据，供 skill 执行时使用。

### Step 6: 检查统计
```bash
python -m scholar stats
```
确认入库数量、元数据覆盖率（year/authors/abstract/venue）、字段覆盖率。

### Step 7: 单篇验证
随机抽取几篇论文，检查解析质量：
```bash
python -m scholar info <ULID>
```
重点验证：标题是否准确、作者列表是否完整、章节结构是否合理。

## 增量入库
当用户下载了新论文到 `data/papers/<新ULID>/` 目录时：
1. 执行 `python -m scholar scan` 确认新论文出现
2. 执行 `python -m scholar parse <ULID>` 解析单篇
3. 执行 `python -m scholar stats` 更新统计

## 注意事项
- 批量解析时逐篇处理，失败的跳过不影响整体
- 如果 Neo4j 和 PostgreSQL 已启动（`cd infra && docker compose up -d`），解析结果会同时写入数据库
- 缺少 TeX 源码（只有 PDF）的论文无法解析，跳过即可

## Next Steps

论文导入完成后，自然的后续动作：

- **`/research-survey`** — 新论文入库后，重新调研可能发现新关联
- **`/reading-progress`** — 更新阅读进度，标记新导入的论文
- **`/quality-check`** — 对新导入的论文做质量评分

> 传递数据：新论文的 ULID 和解析结果已自动进入知识库，后续 skill 可直接使用。
