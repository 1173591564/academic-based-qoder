---
kind: design
name: 采用 PyInstaller 打包为单文件 .exe 并分离全局知识库
source: session
category: adr
---

# 采用 PyInstaller 打包为单文件 .exe 并分离全局知识库

_来源：a14a57f → bc6e785 提交周期内记录的编码计划——内容为规划时意图，实现可能滞后或有出入。_

**状态：** accepted

## 背景
为了将 Scholar Studio 分发给非技术用户或实现全局可用，需要摆脱对本地 Python 环境的依赖。同时，应用数据（论文、笔记）不应随代码打包或存储在源码目录中，以便在升级或重装时保留用户数据。

## 决策驱动
- 无需安装 Python 环境即可运行
- 用户数据与应用程序二进制文件解耦
- 支持通过环境变量自定义数据存储路径

## 备选方案
- **PyInstaller 单文件打包 + 全局知识库 (~/.scholar-studio/)** — 优点：分发简单（单个 .exe），用户数据持久化且独立于程序版本，支持多位置部署；缺点：启动速度略慢（解压开销），需处理 frozen 模式下的路径逻辑
- **传统 pip 安装包 (setup.py/pyproject.toml)** _（已否决）_ — 优点：标准的 Python 分发方式，易于开发调试；缺点：要求用户预先安装 Python 和管理依赖，配置复杂度高
- **数据存储在源码目录** _（已否决）_ — 优点：开发模式下路径直观；缺点：打包后无法写入（权限问题），升级时会丢失用户数据

## 决策
使用 PyInstaller 将应用打包为 scholar.exe。在 config.py 中引入运行时检测：若处于 frozen 模式，则将 SCHOLAR_HOME 指向 ~/.scholar-studio/（可通过环境变量覆盖）；否则指向源码根目录。所有数据子目录（data/, output/）均基于 SCHOLAR_HOME 构建。

## 影响
生成了约 50-80MB 的可执行文件。用户需在首次运行时初始化全局目录。Docker 数据库和 LaTeX 编译器仍需作为外部依赖单独安装。