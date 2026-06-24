---
description: 恢复中断的学术写作/调研流程
---
恢复上次中断的调研、写作或分析流程，从断点继续执行。

## 执行步骤
1. 检查 TodoWrite 中是否有未完成的 skill 步骤（非 COMPLETE 状态）
2. 扫描 `output/drafts/` 中的中间产物：
   - `*-outline.md` — 骨架文件，说明大纲阶段已完成
   - `*-review.md` — 质量门控结果，说明初稿已完成
   - 已有的 `.md` 或 `.tex` 文件 — 检查内容完成度（哪些 section 已写入）
3. 扫描 `output/notes/` 中的中间产物：
   - `*-deep-dive.md` — 深度分析报告
   - `*-quality.json` — 质量评分
4. 综合判断当前阶段：
   - 仅有 outline → 从"逐节撰写"步骤恢复
   - 有 outline + 部分 section → 从未完成的 section 继续
   - 有 draft + review → 从"定向修订"步骤恢复
   - 有 review 且全部 PASS → 从"终稿输出"步骤恢复
5. 加载对应的 SKILL.md，从断点步骤开始执行，跳过已完成的步骤
6. 更新 TodoWrite，将已完成的步骤标记为 COMPLETE
