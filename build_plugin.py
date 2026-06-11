"""Build the Scholar Studio Qoder Plugin.

Copies skills and commands from the project into plugin/ directory.
Usage: python build_plugin.py
"""
import shutil
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = PROJECT_ROOT / "plugin"
SKILLS_SRC = PROJECT_ROOT / ".qoder" / "skills"
COMMANDS_SRC = PROJECT_ROOT / ".qoder" / "commands"
SKILLS_DST = PLUGIN_DIR / "skills"
COMMANDS_DST = PLUGIN_DIR / "commands"


def clean():
    """Remove old plugin build artifacts."""
    for d in [SKILLS_DST, COMMANDS_DST]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Cleaned {d}")


def copy_skills():
    """Copy all SKILL.md files (and any auxiliary files) into plugin/skills/."""
    count = 0
    for skill_dir in sorted(SKILLS_SRC.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        dst = SKILLS_DST / skill_dir.name
        dst.mkdir(parents=True, exist_ok=True)

        # Copy all files in the skill directory
        for f in skill_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)

        count += 1

    print(f"  Copied {count} skills")
    return count


def copy_commands():
    """Copy all command .md files into plugin/commands/."""
    COMMANDS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(COMMANDS_SRC.glob("*.md")):
        shutil.copy2(f, COMMANDS_DST / f.name)
        count += 1
    print(f"  Copied {count} commands")
    return count


def create_mcp_config():
    """Create .mcp.json for the plugin.

    The MCP server requires the scholar Python package.
    Users must: pip install -r requirements.txt (from the main repo)
    """
    mcp = {
        "mcpServers": {
            "scholar": {
                "command": "python",
                "args": ["-m", "scholar_mcp"],
                "env": {
                    "SCHOLAR_PG_HOST": "localhost",
                    "SCHOLAR_PG_PORT": "5433",
                    "SCHOLAR_NEO4J_URI": "bolt://localhost:7687"
                }
            }
        }
    }
    import json
    mcp_path = PLUGIN_DIR / ".mcp.json"
    mcp_path.write_text(json.dumps(mcp, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Created .mcp.json")


def create_plugin_readme():
    """Create a README for the plugin."""
    readme = """# Scholar Studio Plugin

> 需要配合主仓库使用：https://gitee.com/gu-yulong1217317/academic-based-qoder

## 包含能力

| 类型 | 数量 | 说明 |
|------|------|------|
| Skills | 22 | 18 原子 + 4 组合 Workflow |
| Commands | 4 | stats / find / paper / health |
| MCP Server | 1 | Scholar MCP（29 工具） |

## 前置要求

```bash
# 1. 克隆主仓库
git clone https://gitee.com/gu-yulong1217317/academic-based-qoder.git
cd academic-based-qoder

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动数据库
./startup.ps1

# 4. 全量初始化
python -m scholar bootstrap
```

## Skills 列表

### 原子 Skills
- `/research-survey` — 全面文献调研
- `/deep-read` — 单篇深度阅读
- `/paper-compare` — 多篇对比
- `/paper-recommendation` — 论文推荐
- `/cold-start` — 陌生领域入门
- `/related-work` — 写 Related Work
- `/citation-network` — 引用网络分析
- `/research-gap` — 研究空白发现
- `/concept-evolution` — 概念演化追踪
- `/formula-derivation` — 公式推导
- `/math-verification` — Lean4 验证
- `/experiment-code` — 实验代码生成
- `/quality-check` — 质量评分
- `/review-report` — 审稿报告
- `/paper-ingestion` — 论文导入
- `/bibtex-management` — BibTeX 管理
- `/kb-maintenance` — 知识库维护
- `/reading-progress` — 阅读进度

### 组合 Workflow
- `/full-research` — 调研 → 精读 → 对比 → Related Work
- `/gap-analysis-flow` — 引用网络 → 概念演化 → 研究缺口 → 推荐
- `/paper-analysis-flow` — 精读 → 评分 → 推导 → 代码
- `/writing-flow` — 调研 → 对比 → 写作 → BibTeX → 审稿
"""
    readme_path = PLUGIN_DIR / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    print(f"  Created README.md")


def main():
    print("=" * 50)
    print("  Scholar Studio — Plugin Builder")
    print("=" * 50)

    print("\n[1/5] Cleaning old build...")
    clean()

    print("\n[2/5] Copying skills...")
    skills = copy_skills()

    print("\n[3/5] Copying commands...")
    commands = copy_commands()

    print("\n[4/5] Creating MCP config...")
    create_mcp_config()

    print("\n[5/5] Creating plugin README...")
    create_plugin_readme()

    # Summary
    print("\n" + "=" * 50)
    print(f"  Plugin built: plugin/")
    print(f"  Skills: {skills}")
    print(f"  Commands: {commands}")
    print(f"  MCP: scholar (29 tools)")
    print("=" * 50)

    # List final structure
    print("\nPlugin structure:")
    for root, dirs, files in os.walk(PLUGIN_DIR):
        level = root.replace(str(PLUGIN_DIR), "").count(os.sep)
        indent = "  " * level
        dirname = os.path.basename(root)
        if dirname.startswith(".qoder"):
            print(f"{indent}{dirname}/")
        elif level <= 1:
            print(f"{indent}{dirname}/")

        if level <= 2:
            subindent = "  " * (level + 1)
            for f in sorted(files):
                print(f"{subindent}{f}")


if __name__ == "__main__":
    main()
