---
name: reproduce-paper
description: "端到端实验复现流程：环境配置→代码生成→运行→结果对比"
---

## 触发
当用户说"复现 XX 论文"、"reproduce"、"运行实验"、"跑一下这篇论文的代码"时执行此流程。

## 流程

### Step 1: 深度阅读论文
```bash
python -m scholar info <paper_id>
```
- 重点提取：算法描述、实验设置、超参数、数据集
- 阅读预生成笔记 `output/notes/<ULID>.md` 获取摘要

### Step 2: 配置运行环境
```bash
python -m scholar exp-setup <paper_id> --conda
```
- 自动检测 requirements.txt / environment.yml
- 创建 conda 环境 `scholar-<ULID[:8]>`
- 安装依赖

### Step 3: 生成实验代码
基于论文描述的算法生成代码（如果尚未生成）：
- 主训练脚本 `main.py`
- 模型定义 `model.py`
- 数据加载 `data.py`
- 评估脚本 `evaluate.py`
- 配置文件 `config.yaml`
输出到 `output/experiments/<ULID>/`

### Step 4: 下载数据集（如需要）
```bash
python -m scholar dataset-download <dataset_name>
```
- 自动检测 HuggingFace 数据集
- 下载到 `output/datasets/<dataset_name>/`

### Step 5: 运行实验
```bash
python -m scholar exp-run <paper_id> --mode quick
```
- quick 模式：CPU + 合成数据，快速验证代码能跑
- full 模式：完整训练流程（可能需要 GPU）
- 超时保护（默认 1 小时）

### Step 6: 对比结果
```bash
python -m scholar exp-compare <paper_id>
```
- 对比实验运行结果与论文报告的 metrics
- 生成对比报告

### Step 7: 调试失败（如需要）
```bash
python -m scholar exp-debug output/experiments/<ULID>/run_log.txt
```
- 自动诊断常见错误（ModuleNotFoundError、CUDA OOM、FileNotFoundError）
- 提供修复建议

## Next Steps

- **`/writing-pipeline`** — 将复现结果写入学术论文
- **`/paper-deep-dive`** — 对论文做更深层的理论分析
- **`/idea-to-paper`** — 基于复现经验提出改进方案
