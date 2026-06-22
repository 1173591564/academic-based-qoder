"""
Scholar Studio — Build Script

一键构建 scholar.exe（需要 PyInstaller）。

Usage:
    python build_exe.py            # 构建 onedir 模式（推荐）
    python build_exe.py --onefile  # 构建单文件模式
    python build_exe.py --install  # pip install -e . 后全局可用
"""
import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def check_pyinstaller():
    """检查 PyInstaller 是否已安装。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"[OK] PyInstaller {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("[!] PyInstaller 未安装。正在安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    return True


def build_exe(onefile: bool = False):
    """执行 PyInstaller 构建。"""
    spec_file = PROJECT_ROOT / "scholar.spec"
    entry_point = PROJECT_ROOT / "scholar_cli.py"
    if not spec_file.exists():
        print(f"[ERROR] 找不到 {spec_file}")
        sys.exit(1)

    if onefile:
        # onefile 模式：不用 spec 文件（spec 硬编码了 onedir），直接用命令行参数
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", "scholar",
            "--noconfirm",
            "--clean",
            str(entry_point),
        ]
        # 添加 hidden imports（与 spec 文件保持一致）
        hidden_imports = [
            "scholar", "scholar.cli", "scholar._shared", "scholar.config",
            "scholar.db", "scholar.graph_db", "scholar.rag", "scholar.tex_parser",
            "scholar.auto_notes", "scholar.classify", "scholar.quality",
            "scholar.metadata_enrich", "scholar.year_fix", "scholar.cite_resolve",
            "scholar.kb_update", "scholar.research_loop", "scholar.id_resolver",
            "scholar.commands", "scholar.commands.core_ops", "scholar.commands.paper_ops",
            "scholar.commands.metadata_ops", "scholar.commands.graph_ops",
            "scholar.commands.rag_ops", "scholar.commands.batch_ops",
            "scholar.commands.research_ops", "scholar.commands.execution_ops",
            "scholar.commands.external_ops",
            "psycopg2", "psycopg2.extras", "neo4j", "dotenv", "typer", "rich",
            "rich.console", "rich.panel", "rich.table", "rich.progress", "fitz",
        ]
        for hi in hidden_imports:
            cmd.extend(["--hidden-import", hi])
        # 添加 excludes
        for ex in ["matplotlib", "numpy", "scipy", "pandas", "PIL", "torch",
                    "tensorflow", "IPython", "jupyter", "notebook", "pytest"]:
            cmd.extend(["--exclude-module", ex])
    else:
        # onedir 模式：使用 spec 文件
        cmd = [
            sys.executable, "-m", "PyInstaller",
            str(spec_file),
            "--noconfirm",
            "--clean",
        ]

    print(f"\n{'='*60}")
    print(f"Building Scholar Studio .exe")
    print(f"Mode: {'onefile' if onefile else 'onedir'}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"\n[ERROR] 构建失败 (exit code {result.returncode})")
        sys.exit(1)

    # 报告产物
    dist_dir = PROJECT_ROOT / "dist"
    if onefile:
        exe_path = dist_dir / "scholar.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n{'='*60}")
            print(f"[OK] 构建成功!")
            print(f"  产物: {exe_path}")
            print(f"  大小: {size_mb:.1f} MB")
            print(f"\n使用方式:")
            print(f"  {exe_path} stats")
            print(f"  {exe_path} search \"transformer\"")
            print(f"\n可选: 将 dist/ 加入 PATH 以全局使用")
            print(f"  $env:Path += ';{dist_dir}'")
    else:
        exe_dir = dist_dir / "scholar"
        exe_path = exe_dir / "scholar.exe"
        if exe_path.exists():
            total_size = sum(f.stat().st_size for f in exe_dir.rglob("*") if f.is_file())
            size_mb = total_size / (1024 * 1024)
            print(f"\n{'='*60}")
            print(f"[OK] 构建成功!")
            print(f"  目录: {exe_dir}")
            print(f"  入口: {exe_path}")
            print(f"  总大小: {size_mb:.1f} MB")
            print(f"\n使用方式:")
            print(f"  {exe_path} stats")
            print(f"  {exe_path} search \"transformer\"")
            print(f"\n可选: 将目录加入 PATH 以全局使用")
            print(f"  $env:Path += ';{exe_dir}'")

    print(f"\n首次使用请先初始化知识库:")
    print(f"  scholar init")
    print(f"{'='*60}")


def pip_install():
    """pip install -e . 使 scholar 命令全局可用。"""
    print("\n[INFO] 正在以开发模式安装 Scholar Studio...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(PROJECT_ROOT)],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode == 0:
        print(f"\n[OK] 安装完成! 现在可以在任意目录使用 'scholar' 命令:")
        print(f"  scholar stats")
        print(f"  scholar search \"transformer\"")
        print(f"  scholar init          # 初始化全局知识库")
    else:
        print(f"\n[ERROR] 安装失败")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scholar Studio Build Tool")
    parser.add_argument("--onefile", action="store_true", help="Build single-file .exe")
    parser.add_argument("--install", action="store_true", help="pip install -e . for global usage")
    args = parser.parse_args()

    if args.install:
        pip_install()
    else:
        check_pyinstaller()
        build_exe(onefile=args.onefile)
