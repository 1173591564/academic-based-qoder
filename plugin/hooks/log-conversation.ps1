# Scholar Studio - 对话日志采集（硬约束）
# Hook event: Stop
# 每次 Agent 响应结束时，自动记录用户消息到周日志文件
# 按周轮转: output/logs/week-YYYY-WNN.jsonl

param()

# 安全包装：任何异常都不阻断 Stop 事件
try {
    # 1. 从 stdin 读取 JSON 上下文
    #    Stop 事件 stdin 字段: session_id, cwd, hook_event_name,
    #    transcript_path, stop_hook_active, last_assistant_message
    $input_json = [Console]::In.ReadToEnd()
    if (-not $input_json) { exit 0 }
    $ctx = $input_json | ConvertFrom-Json -ErrorAction Stop

    # 2. 提取用户消息
    $user_text = ""

    # 优先从 transcript_path 读取 JSONL 提取 user 消息
    if ($ctx.transcript_path -and (Test-Path $ctx.transcript_path)) {
        try {
            $lines = [System.IO.File]::ReadAllLines($ctx.transcript_path, [System.Text.Encoding]::UTF8)
            $user_msgs = @()
            foreach ($line in $lines) {
                if (-not $line.Trim()) { continue }
                try {
                    $msg = $line | ConvertFrom-Json
                    if ($msg.role -eq "user" -or $msg.type -eq "user") {
                        $content = if ($msg.content) { $msg.content }
                                   elseif ($msg.message) { $msg.message }
                                   elseif ($msg.text) { $msg.text }
                                   else { "" }
                        if ($content) { $user_msgs += $content }
                    }
                } catch { }
            }
            $user_text = ($user_msgs -join " | ")
        } catch { }
    }

    # 兜底：使用 last_assistant_message 作为交互记录
    if ((-not $user_text -or $user_text.Trim() -eq "") -and $ctx.last_assistant_message) {
        $user_text = "[agent-response] $($ctx.last_assistant_message)"
    }

    if (-not $user_text -or $user_text.Trim() -eq "") { exit 0 }
    if ($user_text.Length -gt 500) { $user_text = $user_text.Substring(0, 500) }
    # 清理控制字符（PowerShell 5.1 ConvertTo-Json 不转义控制字符）
    $user_text = $user_text -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
    $user_text = $user_text.Replace('\', '\\').Replace('"', '\"')

    # 3. 计算当前 ISO 周编号（修正 ISO 年份边界）
    $now = Get-Date
    $weekNum = [System.Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear(
        $now, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday
    )
    # ISO 年份修正：12 月底可能属于下一年 W01，1 月初可能属于上一年 W52/53
    $isoYear = $now.Year
    if ($weekNum -gt 50 -and $now.Month -eq 1) { $isoYear-- }
    elseif ($weekNum -eq 1 -and $now.Month -eq 12) { $isoYear++ }
    $weekId = "{0}-W{1:D2}" -f $isoYear, $weekNum
    $ts = $now.ToString("yyyy-MM-ddTHH:mm:ss")

    # 4. 构建日志条目 JSON
    $entry = @{
        ts      = $ts
        week    = $weekId
        session = if ($ctx.session_id) { $ctx.session_id } else { "unknown" }
        text    = $user_text
    } | ConvertTo-Json -Compress

    # 5. 确保目录存在并追加写入
    # .qoder/hooks/ → .qoder/ → project root = 2 levels
    # plugin/hooks/ → plugin/ → project root = 2 levels
    # 注意: PS 5.1 Join-Path 不支持多参数，用字符串格式化代替
    $projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $logDir = "{0}\output\logs" -f $projectRoot
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    $logFile = "{0}\week-{1}.jsonl" -f $logDir, $weekId
    # UTF-8 无 BOM 追加
    [System.IO.File]::AppendAllText($logFile, "$entry`n", [System.Text.UTF8Encoding]::new($false))
}
catch {
    # 静默失败，不影响 Stop 事件
}

exit 0
