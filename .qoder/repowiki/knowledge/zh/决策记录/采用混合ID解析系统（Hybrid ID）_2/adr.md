# 采用混合ID解析系统（Hybrid ID）

_来源：35a8f17 → b3b1a40 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
原有系统仅支持26字符的ULID作为论文唯一标识，用户难以记忆和输入。为了提升可用性，需要支持arXiv ID、DOI或标题slug等更自然的查询方式，同时必须保持对现有ULID体系的兼容。

## 决策驱动
- 用户体验（自然查询）
- 向后兼容性
- 实现复杂度

## 备选方案
- **完全替换ULID为arXiv ID** _（已否决）_ — 优点：ID更具语义化；缺点：非arXiv论文无法覆盖；修改底层主键导致巨大的向后兼容成本和迁移风险
- **基于数据库查询的实时解析** _（已否决）_ — 优点：数据实时一致；缺点：每次查询增加DB负载，对于高频CLI调用可能产生延迟
- **内存缓存的文件索引解析器（IDResolver）** — 优点：启动时扫描JSON构建内存索引，查询极速；无需修改DB Schema；支持多格式映射；缺点：知识库更新后需刷新缓存（通过kb-update自动处理）

## 决策
新建 `scholar/id_resolver.py` 模块，实现基于内存缓存的 `IDResolver`。在CLI命令入口处统一调用 `resolve_id`，将任意格式的输入（ULID/arXiv/DOI/slug）解析为内部ULID。同时在 `scholar/db.py` 中扩展 `upsert_paper` 以持久化存储 `arxiv_id` 和 `doi`。

## 影响
用户可以使用 `python -m scholar info 2402.01680` 等自然ID查询。系统增加了元数据回填流程（`metadata_enrich.py`），需遵守arXiv API限速（3秒/次）。