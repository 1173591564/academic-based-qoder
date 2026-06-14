# Scholar Studio - 对话日志采集（硬约束）
# Hook event: Stop
# 每次 Agent 响应结束时，自动记录用户消息到周日志文件
# 按周轮转: output/logs/week-YYYY-WNN.jsonl

param()

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = "{0}\output\logs" -f $projectRoot
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# 1. 读取 stdin
$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }

# 2. 解析 JSON
# 优先用 System.Text.Json（.NET，更宽松，能处理未转义反斜杠）
# 失败兜底用 PowerShell 的 ConvertFrom-Json
$ctx = $null
try {
    Add-Type -AssemblyName System.Text.Json -ErrorAction SilentlyContinue
    $jsonDoc = [System.Text.Json.JsonDocument]::Parse($raw)
    $root = $jsonDoc.RootElement

    # 构造 PSObject
    $ctx = New-Object PSObject
    foreach ($prop in $root.EnumerateObject()) {
        $val = $prop.Value
        # JsonElement 转简单类型
        if ($val.ValueKind -eq "String") { $val = $val.GetString() }
        elseif ($val.ValueKind -eq "Number") { $val = [double]$val.GetRawText() }
        elseif ($val.ValueKind -eq "True") { $val = $true }
        elseif ($val.ValueKind -eq "False") { $val = $false }
        elseif ($val.ValueKind -eq "Null") { $val = $null }
        $ctx | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $val -Force
    }
    $jsonDoc.Dispose()
} catch {
    # 兜底：PowerShell ConvertFrom-Json
    try { $ctx = $raw | ConvertFrom-Json } catch { exit 0 }
}
if (-not $ctx) { exit 0 }

# 官方要求: Stop hook 必须检查 stop_hook_active
if ($ctx.stop_hook_active -eq $true) { exit 0 }

# 3. 提取用户消息
$user_text = ""

# 优先从 transcript_path 读取 JSONL
if ($ctx.transcript_path -and (Test-Path $ctx.transcript_path)) {
    try {
        $lines = [System.IO.File]::ReadAllLines($ctx.transcript_path, [System.Text.Encoding]::UTF8)
        $user_msgs = @()
        foreach ($line in $lines) {
            if (-not $line.Trim()) { continue }
            try {
                $msg = $line | ConvertFrom-Json
                if ($msg.role -ne "user") { continue }
                $texts = @()
                if ($msg.message -and $msg.message.content) {
                    foreach ($part in $msg.message.content) {
                        if ($part.type -eq "text" -and $part.text) {
                            $texts += $part.text
                        }
                    }
                }
                $combined = ($texts -join " ").Trim()
                if ($combined) { $user_msgs += $combined }
            } catch { }
        }
        if ($user_msgs.Count -gt 0) {
            $user_text = $user_msgs[-1]
        }
    } catch { }
}

# 兜底
if ((-not $user_text -or $user_text.Trim() -eq "") -and $ctx.last_assistant_message) {
    $user_text = "[agent-response] $($ctx.last_assistant_message)"
}

if (-not $user_text -or $user_text.Trim() -eq "") { exit 0 }

# 4. 关键：剥离所有 Qoder 注入的 <...> 标签，只保留 <user_query>...</user_query>
$realUserText = ""
if ($user_text -match '(?s)<user_query>(.*?)</user_query>') {
    $realUserText = $Matches[1].Trim()
}
if (-not $realUserText) {
    $realUserText = ($user_text -replace '<[^>]+>', ' ').Trim()
    $realUserText = ($realUserText -replace '\s+', ' ').Trim()
}
if (-not $realUserText) { exit 0 }

# 5. 截断 + 清理
if ($realUserText.Length -gt 500) { $realUserText = $realUserText.Substring(0, 500) }
$realUserText = $realUserText -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
$realUserText = $realUserText.Replace('\', '\\').Replace('"', '\"')

# 6. 计算 ISO 周
$now = Get-Date
$weekNum = [System.Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear(
    $now, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday
)
$isoYear = $now.Year
if ($weekNum -gt 50 -and $now.Month -eq 1) { $isoYear-- }
elseif ($weekNum -eq 1 -and $now.Month -eq 12) { $isoYear++ }
$weekId = "{0}-W{1:D2}" -f $isoYear, $weekNum
$ts = $now.ToString("yyyy-MM-ddTHH:mm:ss")

# 7. 写入日志
$entry = @{
    ts      = $ts
    week    = $weekId
    session = if ($ctx.session_id) { $ctx.session_id } else { "unknown" }
    text    = $realUserText
} | ConvertTo-Json -Compress

$logFile = "{0}\week-{1}.jsonl" -f $logDir, $weekId
[System.IO.File]::AppendAllText($logFile, "$entry`n", [System.Text.UTF8Encoding]::new($false))

exit 0
