# Scholar Studio — 双 IDE 分发配置

Scholar Studio 同时支持两种 AI IDE 后端：

## 1. Qoder IDE

- **配置目录**: `.qoder/` (项目根)
- **插件定义**: `plugin/.qoder-plugin/plugin.json`
- **启动方式**: 用户在 Qoder IDE 中安装 `plugin/` 目录
- **CLI**: `qoder` (IDE) / `qodercli` (CLI Agent)
- **Skills 位置**: `.qoder/skills/`
- **Rules 位置**: `.qoder/rules/`
- **Commands**: `.qoder/commands/`
- **Hooks**: `.qoder/hooks/`
- **MCP**: `.qoder/mcp.json`

## 2. Claude Code

- **配置目录**: `.claude/` (项目根)
- **插件定义**: `plugin/.claude-plugin/plugin.json` (Claude 官方约定)
- **启动方式**: Claude Code 自动发现项目根的 `.claude/`
- **CLI**: `claude` (Anthropic 官方)
- **Skills 位置**: `.claude/skills/`
- **Rules 位置**: `.claude/rules/` (Claude Code 自动加载为 system prompt)
- **Commands**: `.claude/commands/`
- **Hooks**: `.claude/hooks/`
- **MCP**: `.claude/mcp.json`
- **CLAUDE.md**: `.claude/CLAUDE.md` (Claude Code 自动发现)

## 双目录同步策略

`.qoder/` 和 `.claude/` 内容 99% 相同，仅根目录文件略有差异：
- `.qoder/` 含 `mcp.json` + `settings.json` (Qoder IDE 配置)
- `.claude/` 含 `CLAUDE.md` + `mcp.json` + `settings.json` (Claude Code 配置)

**桌面 EXE 行为**: `build_system_prompt()` 自动合并两目录的 rules 和 skills 去重，确保两个 IDE 启动时都获得完整上下文。

## 安装指南

### Qoder IDE

```bash
# 在 Qoder IDE 中: Plugin → Install from Local → 选择 plugin/ 目录
```

### Claude Code

```bash
# Claude Code 自动发现项目根的 .claude/，无需额外操作
# 或手动: cp -r .claude/* ~/.claude/  (全局安装)
```

## 双平台支持的代价

- 同时支持 `claude` 和 `qodercli` 两个 CLI
- MCP 配置可共用一份 (mcp.json 内容相同)

## 未来扩展

- 复制规则时可使用符号链接 (symlink) 避免重复
- 或使用单一 source-of-truth + 生成脚本 (如 `scripts/sync_dotfiles.py`)
