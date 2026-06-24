---
kind: design
name: 引用解析采用 DOI/标题多级匹配管线
source: session
category: adr
---

# 引用解析采用 DOI/标题多级匹配管线

_来源：7729a25 → 7877e84 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
原有的 cite_resolve.py 使用 ref_key（如 vaswani2017）与论文标题进行 Levenshtein 模糊匹配，由于标识符维度不同，匹配率仅 ~40%，导致引用网络严重缺失。

## 决策驱动
- 引用网络完整性
- 匹配准确率
- 执行效率

## 备选方案
- **维持原有 ref_key 模糊匹配** _（已否决）_ — 优点：无需新增依赖，实现简单；缺点：匹配率低（~40%），无法构建完整的学术引用图谱
- **基于 DOI/CrossRef 和标题的多级匹配管线** — 优点：DOI 精确匹配率高；结合 rapidfuzz 进行标题模糊匹配可覆盖无 DOI 情况；解析率预期提升至 95%+；缺点：需引入 rapidfuzz 和 bibtexparser 依赖；需处理 CrossRef API 速率限制

## 决策
重写 cite_resolve.py，实施三级匹配策略：L1 DOI 精确匹配，L2 基于 rapidfuzz 的标题模糊匹配，L3 arXiv API 回退。同时在 tex_parser.py 中增加 _extract_bibliography() 以从 .bib文件和 \bibitem 中提取结构化元数据。

## 影响
引用解析率显著提升，支持更完整的知识图谱构建；引入了对 CrossRef/Semantic Scholar API 的外部依赖，需实施磁盘缓存以应对速率限制。