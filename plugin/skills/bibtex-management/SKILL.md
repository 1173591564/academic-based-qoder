---
name: bibtex-management
description: "导出、管理和验证 BibTeX 引用文件"
---

## 触发
当用户说"导出 BibTeX"、"整理引用"、"生成 bib 文件"、"引用格式"、"参考文献"时执行此流程。

## 流程

### Step 1: 确定范围
与用户确认：
- 导出全部论文的 BibTeX？→ 全量导出
- 导出某个主题/方向的论文？→ 按主题导出
- 导出某篇论文的引用列表？→ 按引用导出

### Step 2: 全量导出
```bash
python -m scholar export-bib
```
将所有已解析论文导出为 BibTeX，保存到 `output/bib/scholar.bib`。

### Step 3: 按主题导出
利用分类标签过滤论文：
```bash
python -m scholar classify --list-tags
python -m scholar search "<主题>"
python -m scholar list-papers --year <Y>
```
对搜索结果中的论文，从 `output/parsed/<ULID>.json` 提取元数据（包括 `tags` 字段），生成 BibTeX 条目。可以按 `tags.domains` 字段分类导出。

### Step 4: 按引用导出
读取目标论文的 citations 字段：
```bash
python -m scholar info <ULID>
```
对每个被引用的 paper_id，在本地库中查找对应的解析数据，生成 BibTeX 条目。
对于库外引用（本地无对应论文），通过 arXiv 或 Google Scholar 补全信息。

### Step 5: 质量检查
对生成的 BibTeX 进行检查：
- **必填字段**：每条是否有 title, author, year？
- **格式一致**：会议/期刊名称格式是否统一？
- **key 规范**：citation key 是否易读（如 `vaswani2017attention`）？
- **重复检测**：比较标题归一化后的相似度，发现潜在重复条目
- **编码问题**：特殊字符（如 ü, é）是否正确转义？
- **元数据补全**：对缺少 year/author 的条目，用 `python -m scholar year-fix --apply` 和 `author-fix --apply` 补全

### Step 6: 分类整理
按会议/期刊分类输出：
```bibtex
% ===== NeurIPS =====
@inproceedings{vaswani2017attention,
  title={Attention is All You Need},
  author={Vaswani, Ashish and ...},
  booktitle={NeurIPS},
  year={2017}
}

% ===== ICLR =====
@inproceedings{...}

% ===== ICML =====
@inproceedings{...}

% ===== arXiv =====
@article{...}
```

### Step 7: 输出
- 全量导出：`output/bib/scholar.bib`
- 主题导出：`output/bib/<topic>.bib`
- 引用导出：`output/bib/<paper_id>-refs.bib`

同时输出一份统计：
```
BibTeX 导出完成:
- 总条目: N
- NeurIPS: X
- ICLR: Y
- ICML: Z
- CVPR: W
- arXiv: V
- 其他: U
```

## BibTeX 格式规范
- citation key 格式：`<第一作者姓><年份><标题第一个实词>`
- 会议论文用 `@inproceedings`，期刊用 `@article`，预印本用 `@article` 并标注 `journal={arXiv}`
- 作者名用 `and` 连接，不要用逗号
- 标题保留原始大小写，用花括号保护专有名词

## 注意事项
- 不要编造 BibTeX 条目！每条都必须基于论文的 `output/parsed/` JSON 或实际检索结果
- 如果某字段缺失（如缺少页码），不要填假数据，省略该字段
- 对于 Lean4 中有条目的论文，可以在 note 字段标注 `note={Lean4 formalized}`

## Next Steps

BibTeX 导出后，自然的后续动作：

- **`/related-work`** — 如果还没写 Related Work，现在有了完整的引用列表
- **`/reading-progress`** — 检查 BibTeX 中的论文是否都已阅读

> 传递数据：导出的 `.bib` 文件可直接用于 LaTeX 论文的参考文献管理。
