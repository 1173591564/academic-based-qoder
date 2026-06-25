---
name: experiment-code
description: "根据论文方法与公式生成 PyTorch 实验代码"
output_contract:
  path: output/experiments/
  format: python
  required_fields:
    - paper_id
    - code
    - readme
  citation_check: false
---

## 触发
当用户说"复现实验"、"生成代码"、"写实验脚本"、"实现这个方法"、"跑一下这个实验"时执行此流程。

## 流程

### Step 1: 深度阅读论文方法
先检查预生成数据，再深度阅读：
```bash
python -m scholar info <ULID>
```
- 阅读笔记：`output/notes/<ULID>.md`（已提取的方法概述和公式）
- 质量评分：`output/notes/<ULID>-quality.json`（reproducibility 维度）
- 完整 JSON：`output/parsed/<ULID>.json`（formulas 字段 + sections）

重点提取：
- 核心算法的伪代码或算法描述
- 关键公式（从 formulas 字段提取）
- 实验设置（数据集、超参数、评估指标）
- 模型架构描述

### Step 2: 提取算法要素
从 `output/parsed/` JSON 中提取，同时利用 `rag-search` 查找相关实现：
```bash
python -m scholar rag-search "<方法名> PyTorch implementation" --hybrid
```
- **输入/输出**：算法的输入是什么？输出是什么？
- **核心循环**：训练循环、推理过程
- **损失函数**：从 formulas 中找到 loss 的表达式
- **优化目标**：最小化/最大化什么

### Step 3: 确定技术栈
与用户确认：
- 框架偏好：PyTorch / TensorFlow / JAX
- 是否使用现有库（如 Hugging Face Transformers）
- 运行环境（GPU 型号、内存限制）

### Step 4: 生成代码结构
创建实验目录 `output/experiments/<paper_id>/`：
```
experiments/<paper_id>/
  ├── model.py          # 模型定义
  ├── data.py           # 数据加载
  ├── train.py          # 训练脚本
  ├── evaluate.py       # 评估脚本
  ├── config.yaml       # 超参数配置
  ├── requirements.txt  # 依赖
  └── README.md         # 运行说明
```

### Step 5: 逐步实现
按以下顺序生成代码：
1. **config.yaml**: 从论文实验部分提取超参数
2. **model.py**: 核心模型架构，公式直接对应论文中的 formulas
3. **data.py**: 数据加载和预处理
4. **train.py**: 训练循环，包含 loss 计算
5. **evaluate.py**: 评估指标计算

每个文件中添加注释，说明对应论文的哪个章节/公式。

### Step 6: 验证代码
- 检查代码中的公式是否与论文一致
- 检查维度是否匹配
- 尝试用小数据集做一次 dry run

### Step 7: 生成说明文档
在 `output/experiments/<paper_id>/README.md` 中：
```markdown
## <paper_id> 实验复现

### 对应论文
- **Title:** ...
- **Paper ID:** <ULID>

### 文件说明
- model.py: 对应论文 Section X 的模型架构
- train.py: 对应论文 Algorithm 1

### 运行方式
\`\`\`bash
pip install -r requirements.txt
python train.py --config config.yaml
\`\`\`

### 与论文的差异
- <如有无法完全复现的部分，说明原因>

### 已知问题
- ...
```

## 注意事项
- 代码中的每个关键公式都要注释对应论文中的编号
- 如果论文的方法描述有歧义，选择最合理的解释并标注
- 不要声称"完全复现"除非实际运行结果与论文一致
- 对于依赖特定硬件/数据的方法，说明限制条件
- 生成的代码是起点而非终点，用户可能需要进一步调试

## Next Steps

实验代码生成后，自然的后续动作：

- **`/paper-deep-dive`** — 回读论文确认代码实现的细节是否一致
- **`/reproduce-paper`** — 运行生成的实验代码，对比不同方法的效果

> 传递数据：生成的代码 `output/experiments/<paper>.py` 可作为复现和扩展的基线。
