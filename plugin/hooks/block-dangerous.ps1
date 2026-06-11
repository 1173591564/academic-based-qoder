# Scholar Studio - 拦截危险命令
# Hook event: PreToolUse, matcher: Bash
# 阻止 DROP TABLE、TRUNCATE 等危险 SQL 和 Docker 操作

param()
$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json

$command = $input_json.tool_input.command
if (-not $command) { exit 0 }

# 危险 SQL 操作
if ($command -match '(?i)(DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE\s+(papers|sections|formulas|citations|chunks))') {
    [Console]::Error.WriteLine("Scholar Studio: 危险 SQL 操作被拦截 - $command")
    exit 2
}

# 危险的 Docker/系统操作
if ($command -match '(?i)(docker\s+(rm|volume\s+rm|system\s+prune)|rm\s+-rf)') {
    [Console]::Error.WriteLine("Scholar Studio: 危险系统操作被拦截 - $command")
    exit 2
}

exit 0
