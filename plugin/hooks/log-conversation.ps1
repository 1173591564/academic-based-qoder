# Scholar Studio - 对话日志采集（硬约束）
# Hook event: Stop

param()

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logDir = "{0}\output\logs" -f $projectRoot
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$diagFile = "{0}\hook-diag.log" -f $logDir
function Diag($msg) {
    try { [System.IO.File]::AppendAllText($diagFile, ("[{0}] {1}`n" -f (Get-Date -Format 'HH:mm:ss'), $msg), [System.Text.Encoding]::UTF8) } catch {}
}

Diag "=== HOOK FIRED ==="

try {
    $raw = [Console]::In.ReadToEnd()
    Diag ("stdin len={0}" -f $raw.Length)
    if (-not $raw) { Diag "EXIT: empty stdin"; exit 0 }

    # Parse JSON
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
        Diag "JSON parsed (System.Text.Json)"
    } catch {
        Diag ("System.Text.Json failed: {0}" -f $_.Exception.Message)
        try { $ctx = $raw | ConvertFrom-Json; Diag "JSON parsed (ConvertFrom-Json)" } catch { Diag ("ConvertFrom-Json failed: {0}" -f $_.Exception.Message); exit 0 }
    }
    if (-not $ctx) { Diag "EXIT: null ctx"; exit 0 }

    if ($ctx.stop_hook_active -eq $true) { Diag "EXIT: stop_hook_active"; exit 0 }

    Diag ("session_id={0}" -f $ctx.session_id)
    Diag ("cwd={0}" -f $ctx.cwd)

    # Locate transcript
    $transcriptPath = ""
    if ($ctx.transcript_path -and $ctx.transcript_path.Trim() -ne "" -and (Test-Path $ctx.transcript_path)) {
        $transcriptPath = $ctx.transcript_path
        Diag "using Qoder transcript_path"
    }

    if (-not $transcriptPath -and $ctx.session_id -and $ctx.cwd) {
        $sid8 = $ctx.session_id.Substring(0, [Math]::Min(8, $ctx.session_id.Length))
        $cacheBase = "{0}\.qoder\cache\projects" -f $env:USERPROFILE
        $projName = Split-Path -Leaf $ctx.cwd
        $projDirs = Get-ChildItem $cacheBase -Directory -Filter "$projName-*" -ErrorAction SilentlyContinue
        if ($projDirs -and $projDirs.Count -gt 0) {
            $candidate = "{0}\conversation-history\{1}\{1}.jsonl" -f $projDirs[0].FullName, $sid8
            Diag ("candidate: {0}" -f $candidate)
            if (Test-Path $candidate) {
                $transcriptPath = $candidate
                Diag "transcript found via self-build"
            } else {
                Diag "transcript NOT found via self-build"
            }
        } else {
            Diag ("no project dir matching: {0}-*" -f $projName)
        }
    }

    # Extract last user message
    $user_text = ""
    if ($transcriptPath) {
        try {
            $lines = [System.IO.File]::ReadAllLines($transcriptPath, [System.Text.Encoding]::UTF8)
            Diag ("transcript lines: {0}" -f $lines.Count)
            $user_msgs = @()
            $parseErrors = 0
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
                } catch { $parseErrors++ }
            }
            Diag ("user_msgs={0}, parse_errors={1}" -f $user_msgs.Count, $parseErrors)
            if ($user_msgs.Count -gt 0) {
                $user_text = $user_msgs[-1]
                Diag ("last user_text len={0}" -f $user_text.Length)
            }
        } catch {
            Diag ("transcript read error: {0}" -f $_.Exception.Message)
        }
    } else {
        Diag "no transcript path available"
    }

    # Fallback
    if (-not $user_text -or $user_text.Trim() -eq "") {
        if ($ctx.last_assistant_message) {
            $user_text = "[agent-response] $($ctx.last_assistant_message)"
            Diag "FALLBACK: agent response"
        } else {
            Diag "EXIT: no text at all"
            exit 0
        }
    }

    # Strip <user_query> tags
    $realUserText = ""
    if ($user_text -match '(?s)<user_query>(.*?)</user_query>') {
        $realUserText = $Matches[1].Trim()
        Diag "extracted from user_query tags"
    }
    if (-not $realUserText) {
        $realUserText = ($user_text -replace '<[^>]+>', ' ').Trim()
        $realUserText = ($realUserText -replace '\s+', ' ').Trim()
        Diag "stripped all tags"
    }
    if (-not $realUserText) { Diag "EXIT: empty after strip"; exit 0 }

    Diag ("realUserText (before clean): {0}" -f $realUserText.Substring(0, [Math]::Min(100, $realUserText.Length)))

    # Truncate + clean
    if ($realUserText.Length -gt 500) { $realUserText = $realUserText.Substring(0, 500) }
    $realUserText = $realUserText -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
    # 不手动转义 \ 和 " — ConvertTo-Json 会自动处理

    # ISO week
    $now = Get-Date
    $weekNum = [System.Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear(
        $now, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday
    )
    $isoYear = $now.Year
    if ($weekNum -gt 50 -and $now.Month -eq 1) { $isoYear-- }
    elseif ($weekNum -eq 1 -and $now.Month -eq 12) { $isoYear++ }
    $weekId = "{0}-W{1:D2}" -f $isoYear, $weekNum
    $ts = $now.ToString("yyyy-MM-ddTHH:mm:ss")

    # Write
    $entry = @{
        ts      = $ts
        week    = $weekId
        session = if ($ctx.session_id) { $ctx.session_id } else { "unknown" }
        text    = $realUserText
    } | ConvertTo-Json -Compress

    $logFile = "{0}\week-{1}.jsonl" -f $logDir, $weekId
    [System.IO.File]::AppendAllText($logFile, "$entry`n", [System.Text.UTF8Encoding]::new($false))
    Diag "WROTE log entry"

} catch {
    Diag ("FATAL: {0}" -f $_.Exception.Message)
}

exit 0
