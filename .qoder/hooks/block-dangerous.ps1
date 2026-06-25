# Scholar Studio — PreToolUse Hook: Block Dangerous Commands
# Prevents destructive shell commands from executing
# Merged from .qoder (SQL/Docker) and .claude (system) versions
# Exit code 2 = block, 0 = allow
$ErrorActionPreference = "SilentlyContinue"

param()

# Read stdin as JSON for precise command extraction
$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }

# Try JSON parse first, fall back to raw text matching
$command = ""
try {
    $ctx = $raw | ConvertFrom-Json
    $command = $ctx.tool_input.command
} catch {
    $command = $raw
}
if (-not $command) { exit 0 }

# All dangerous command patterns (merged from both IDE versions)
$dangerousPatterns = @(
    # SQL operations
    "(?i)DROP\s+(TABLE|DATABASE)",
    "(?i)TRUNCATE\s+TABLE\s+(papers|sections|formulas|citations|chunks)",
    # Docker operations
    "(?i)docker\s+(rm|rmi)\s+.*--force\s+.*-f",
    "(?i)docker\s+(rm|volume\s+rm|system\s+prune)",
    # System destruction
    "rm\s+-rf\s+/",
    "rm\s+-rf\s+~",
    "rm\s+-rf\s+\*",
    "rm\s+-rf",
    "del\s+/[fsq]\s+/[fsq]",
    "format\s+[c-z]:",
    "mkfs\.\w+",
    "dd\s+.*of=/dev/",
    ":\(\)\s*\{\s*:\|:&\s*\}\s*;:",  # fork bomb
    "Remove-Item\s+.*-Recurse\s+.*-Force\s+.*C:\\",
    "Remove-Item\s+.*-Recurse\s+.*-Force\s+.*~/",
    # Git destructive operations
    "git\s+push\s+.*--force\s+.*main",
    "git\s+push\s+.*--force\s+.*master",
    "git\s+reset\s+--hard\s+HEAD~",
    # Permission changes
    "chmod\s+-R\s+777\s+/"
)

foreach ($pattern in $dangerousPatterns) {
    if ($command -match $pattern) {
        [Console]::Error.WriteLine("Scholar Studio: Dangerous command blocked - $command")
        [Console]::Error.WriteLine("Pattern: $pattern")
        [Console]::Error.WriteLine("If this is intentional, bypass with --no-verify or ask the user.")
        exit 2
    }
}

exit 0
