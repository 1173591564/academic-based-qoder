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

try {
    # 1. 读取 stdin
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }

    # 2. 解析 JSON（ConvertFrom-Json 兜底，System.Text.Json 在某些 PS5.1 环境不可用）
    $ctx = $null
    try {
        Add-Type -AssemblyName System.Text.Json -ErrorAction SilentlyContinue
        $jsonDoc = [System.Text.Json.JsonDocument]::Parse($raw)
        $root = $jsonDoc.RootElement
        $ctx = New-Object PSObject
        foreach ($prop in $root.EnumerateObject()) {
            $val = $prop.Value
            if ($val.ValueKind -eq "String") { $val = $val.GetString() }
            elseif ($val.ValueKind -eq "Number") { $val = [double]$val.GetRawText() }
            elseif ($val.ValueKind -eq "True") { $val = $true }
            elseif ($val.ValueKind -eq "False") { $val = $false }
            elseif ($val.ValueKind -eq "Null") { $val = $null }
            $ctx | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $val -Force
        }
        $jsonDoc.Dispose()
    } catch {
        try { $ctx = $raw | ConvertFrom-Json } catch { exit 0 }
    }
    if (-not $ctx) { exit 0 }

    # 官方要求: Stop hook 必须检查 stop_hook_active
    if ($ctx.stop_hook_active -eq $true) { exit 0 }

    # 3. 定位 transcript 文件
    $transcriptPath = ""

    # 优先用 transcript_path（如果 Qoder 提供了非空值）
    if ($ctx.transcript_path -and $ctx.transcript_path.Trim() -ne "" -and (Test-Path $ctx.transcript_path)) {
        $transcriptPath = $ctx.transcript_path
    }

    # 自行构建: ~/.qoder/cache/projects/<project>-<hash>/conversation-history/<sid8>/<sid8>.jsonl
    if (-not $transcriptPath -and $ctx.session_id -and $ctx.cwd) {
        $sid8 = $ctx.session_id.Substring(0, [Math]::Min(8, $ctx.session_id.Length))
        $cacheBase = "{0}\.qoder\cache\projects" -f $env:USERPROFILE
        $projName = Split-Path -Leaf $ctx.cwd
        # 用通配符匹配项目目录
        $projDirs = Get-ChildItem $cacheBase -Directory -Filter "$projName-*" -ErrorAction SilentlyContinue
        if ($projDirs -and $projDirs.Count -gt 0) {
            $candidate = "{0}\conversation-history\{1}\{1}.jsonl" -f $projDirs[0].FullName, $sid8
            if (Test-Path $candidate) {
                $transcriptPath = $candidate
            }
        }
    }

    # 4. 从 transcript 提取最后一条用户消息
    $user_text = ""
    if ($transcriptPath) {
        try {
            $lines = [System.IO.File]::ReadAllLines($transcriptPath, [System.Text.Encoding]::UTF8)
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

    # 兜底：记录 agent 回答（标记来源）
    if (-not $user_text -or $user_text.Trim() -eq "") {
        if ($ctx.last_assistant_message) {
            $user_text = "[agent-response] $($ctx.last_assistant_message)"
        } else {
            exit 0
        }
    }

    # 5. 剥离 <user_query> 标签，只保留用户真实输入
    $realUserText = ""
    if ($user_text -match '(?s)<user_query>(.*?)</user_query>') {
        $realUserText = $Matches[1].Trim()
    }
    if (-not $realUserText) {
        $realUserText = ($user_text -replace '<[^>]+>', ' ').Trim()
        $realUserText = ($realUserText -replace '\s+', ' ').Trim()
    }
    if (-not $realUserText) { exit 0 }

    # 6. 截断 + 清理控制字符
    if ($realUserText.Length -gt 500) { $realUserText = $realUserText.Substring(0, 500) }
    $realUserText = $realUserText -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
    $realUserText = $realUserText.Replace('\', '\\').Replace('"', '\"')

    # 7. 计算 ISO 周
    $now = Get-Date
    $weekNum = [System.Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear(
        $now, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday
    )
    $isoYear = $now.Year
    if ($weekNum -gt 50 -and $now.Month -eq 1) { $isoYear-- }
    elseif ($weekNum -eq 1 -and $now.Month -eq 12) { $isoYear++ }
    $weekId = "{0}-W{1:D2}" -f $isoYear, $weekNum
    $ts = $now.ToString("yyyy-MM-ddTHH:mm:ss")

    # 8. 写入日志
    $entry = @{
        ts      = $ts
        week    = $weekId
        session = if ($ctx.session_id) { $ctx.session_id } else { "unknown" }
        text    = $realUserText
    } | ConvertTo-Json -Compress

    $logFile = "{0}\week-{1}.jsonl" -f $logDir, $weekId
    [System.IO.File]::AppendAllText($logFile, "$entry`n", [System.Text.UTF8Encoding]::new($false))

} catch {
    # 静默失败
}

exit 0
