# Scholar Studio — PreToolUse Hook: Block Dangerous Commands
# Prevents destructive shell commands from executing
# Exit code 1 = block, 0 = allow
$ErrorActionPreference = "SilentlyContinue"

# Read stdin for tool context
$context = $input | Out-String

# Dangerous command patterns
$dangerousPatterns = @(
    "rm\s+-rf\s+/",
    "rm\s+-rf\s+~",
    "rm\s+-rf\s+\*",
    "del\s+/[fsq]\s+/[fsq]",
    "format\s+[c-z]:",
    "mkfs\.\w+",
    "dd\s+.*of=/dev/",
    ":\(\)\s*\{\s*:\|:&\s*\}\s*;:",  # fork bomb
    "Remove-Item\s+.*-Recurse\s+.*-Force\s+.*C:\\",
    "Remove-Item\s+.*-Recurse\s+.*-Force\s+.*~/",
    "git\s+push\s+.*--force\s+.*main",
    "git\s+push\s+.*--force\s+.*master",
    "git\s+reset\s+--hard\s+HEAD~",
    "docker\s+(rm|rmi)\s+.*--force\s+.*-f",
    "chmod\s+-R\s+777\s+/"
)

foreach ($pattern in $dangerousPatterns) {
    if ($context -match $pattern) {
        Write-Output "BLOCKED: Dangerous command pattern detected."
        Write-Output "Pattern: $pattern"
        Write-Output "If this is intentional, bypass with --no-verify or ask the user."
        exit 1
    }
}

exit 0
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
