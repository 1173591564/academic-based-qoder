# 重构Skills体系为6个核心工作流

_来源：35a8f17 → b3b1a40 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
原有22个Skills（18原子+4组合）过于碎片化，导致AI代理在执行复杂任务时调度困难，且降低了用户的可理解性。用户明确要求精简技能体系以提升可用性。

## 决策驱动
- 降低认知负荷
- 提升AI代理执行连贯性
- 端到端任务覆盖

## 备选方案
- **保留所有23个Skills并仅新增执行层** _（已否决）_ — 优点：无需重构现有逻辑；缺点：碎片化问题依旧，用户明确要求精简，长尾Skills利用率低
- **合并为6个高层工作流（Workflows）** — 优点：覆盖调研、精读、写作、复现、创意、维护全生命周期；结构清晰；缺点：需要重新定义SKILL.md并删除12个冗余原子Skill

## 决策
将原有的22个Skills重组为6个核心工作流：`research-survey`, `paper-deep-dive`, `writing-pipeline`, `reproduce-paper`, `idea-to-paper`, `kb-management`。删除 `deep-read`, `quality-check` 等12个原子Skill，将其逻辑内聚到工作流步骤中。更新 `.qoder/rules/pipelines.md` 以反映新的路由规则。

## 影响
简化了AI代理的决策空间，提升了复杂任务的执行成功率。旧有的原子Skill不再直接暴露，需通过工作流触发。