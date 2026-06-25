# Scholar Studio - 对话日志采集（硬约束）
# Hook event: Stop
# IDE-agnostic: searches both .qoder and .claude cache directories

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

    # Derive project name from cwd (last path segment, sanitized)
    $projLogDir = $logDir
    if ($ctx.cwd -and $ctx.cwd.Trim() -ne "") {
        $rawProjName = Split-Path -Leaf $ctx.cwd
        $safeName = ($rawProjName -replace '[^\p{L}\p{N}_\-]', '_') -replace '_+', '_'
        $safeName = $safeName.Trim('_')
        if (-not $safeName) { $safeName = "default" }
        if ($safeName.Length -gt 50) { $safeName = $safeName.Substring(0, 50) }
        $projLogDir = "{0}\{1}" -f $logDir, $safeName
        if (-not (Test-Path $projLogDir)) {
            New-Item -ItemType Directory -Path $projLogDir -Force | Out-Null
        }
        Diag "project log dir: $projLogDir"
    } else {
        # Fallback: use 'unknown' project
        $projLogDir = "{0}\unknown" -f $logDir
        if (-not (Test-Path $projLogDir)) {
            New-Item -ItemType Directory -Path $projLogDir -Force | Out-Null
        }
        Diag "no cwd, using 'unknown' project"
    }

    # Locate transcript — search ALL project directories across IDEs
    $transcriptPath = ""
    if ($ctx.transcript_path -and $ctx.transcript_path.Trim() -ne "" -and (Test-Path $ctx.transcript_path)) {
        $transcriptPath = $ctx.transcript_path
        Diag "using transcript_path from hook context"
    }

    if (-not $transcriptPath -and $ctx.session_id) {
        $sid8 = $ctx.session_id.Substring(0, [Math]::Min(8, $ctx.session_id.Length))
        # Search both .qoder and .claude cache directories (IDE-agnostic)
        $cacheDirs = @(
            "{0}\.qoder\cache\projects" -f $env:USERPROFILE,
            "{0}\.claude\cache\projects" -f $env:USERPROFILE
        )
        foreach ($cacheBase in $cacheDirs) {
            if (-not (Test-Path $cacheBase)) { continue }
            Diag "searching cache: $cacheBase"
            $projDirs = Get-ChildItem $cacheBase -Directory -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending
            if ($projDirs -and $projDirs.Count -gt 0) {
                foreach ($pd in $projDirs) {
                    $candidate = "{0}\conversation-history\{1}\{1}.jsonl" -f $pd.FullName, $sid8
                    Diag ("candidate: {0}" -f $candidate)
                    if (Test-Path $candidate) {
                        $transcriptPath = $candidate
                        Diag "transcript found in: $($pd.FullName)"
                        break
                    }
                }
            }
            if ($transcriptPath) { break }
        }
        if (-not $transcriptPath) { Diag "transcript NOT found in any IDE cache" }
    }

    # Helper: extract clean text from a transcript message line
    function Extract-CleanText($msg) {
        $texts = @()
        if ($msg.message -and $msg.message.content) {
            foreach ($part in $msg.message.content) {
                if ($part.type -eq "text" -and $part.text) {
                    $texts += $part.text
                }
            }
        }
        $combined = ($texts -join " ").Trim()
        if (-not $combined) { return "" }

        # Extract user_query content or strip all tags
        $clean = ""
        if ($combined -match '(?s)<user_query>(.*?)</user_query>') {
            $clean = $Matches[1].Trim()
        }
        if (-not $clean) {
            $clean = ($combined -replace '<[^>]+>', ' ').Trim()
            $clean = ($clean -replace '\s+', ' ').Trim()
        }
        # Remove control characters
        $clean = $clean -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
        return $clean
    }

    # Extract ALL user + assistant messages (with retry for race condition)
    $turns = @()
    if ($transcriptPath) {
        $maxRetries = 3
        for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
            try {
                $lines = [System.IO.File]::ReadAllLines($transcriptPath, [System.Text.Encoding]::UTF8)
                Diag ("attempt {0}: transcript lines={1}" -f $attempt, $lines.Count)
                $parseErrors = 0
                foreach ($line in $lines) {
                    if (-not $line.Trim()) { continue }
                    try {
                        $msg = $line | ConvertFrom-Json
                        $role = $msg.role
                        if ($role -ne "user" -and $role -ne "assistant") { continue }
                        $clean = Extract-CleanText $msg
                        if (-not $clean) { continue }
                        # Truncate: user 500 chars, assistant 2000 chars
                        $maxLen = if ($role -eq "user") { 500 } else { 2000 }
                        if ($clean.Length -gt $maxLen) { $clean = $clean.Substring(0, $maxLen) }
                        $turns += @{ role = $role; text = $clean }
                    } catch { $parseErrors++ }
                }
                Diag ("turns={0}, parse_errors={1}" -f $turns.Count, $parseErrors)
                if ($turns.Count -gt 0) {
                    Diag "extracted $($turns.Count) turns"
                    break  # found, exit retry
                } else {
                    if ($attempt -lt $maxRetries) {
                        Diag ("no turns yet, retrying in 800ms...")
                        Start-Sleep -Milliseconds 800
                    }
                }
            } catch {
                Diag ("transcript read error (attempt {0}): {1}" -f $attempt, $_.Exception.Message)
                if ($attempt -lt $maxRetries) { Start-Sleep -Milliseconds 800 }
            }
        }
    } else {
        Diag "no transcript path available"
    }

    # Fallback: use last_assistant_message from hook context
    if ($turns.Count -eq 0) {
        if ($ctx.last_assistant_message) {
            $fb = "$($ctx.last_assistant_message)" -replace '[\x00-\x08\x0B\x0C\x0E-\x1F]', ' '
            if ($fb.Length -gt 2000) { $fb = $fb.Substring(0, 2000) }
            $turns += @{ role = "assistant"; text = $fb }
            Diag "FALLBACK: agent response"
        } else {
            Diag "EXIT: no turns at all"
            exit 0
        }
    }

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
    $logFile = "{0}\week-{1}.jsonl" -f $projLogDir, $weekId
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    $sessionId = if ($ctx.session_id) { $ctx.session_id } else { "unknown" }

    # Write each turn as a separate log entry (deduplicate against existing)
    $writtenCount = 0

    # Count already-logged turns for this session to avoid duplicates
    $existingCount = 0
    if (Test-Path $logFile) {
        try {
            $existingLines = [System.IO.File]::ReadAllLines($logFile, [System.Text.Encoding]::UTF8)
            foreach ($el in $existingLines) {
                if (-not $el.Trim()) { continue }
                try {
                    $e = $el | ConvertFrom-Json
                    if ($e.session -eq $sessionId) { $existingCount++ }
                } catch {}
            }
        } catch {}
    }
    Diag "existing entries for session: $existingCount"

    # Skip already-logged turns, write only new ones
    for ($i = $existingCount; $i -lt $turns.Count; $i++) {
        $turn = $turns[$i]
        $entry = @{
            ts      = $ts
            week    = $weekId
            session = $sessionId
            role    = $turn.role
            text    = $turn.text
        } | ConvertTo-Json -Compress

        [System.IO.File]::AppendAllText($logFile, "$entry`n", $utf8NoBom)
        $writtenCount++
    }
    Diag "WROTE $writtenCount new entries (skipped $existingCount existing, total turns=$($turns.Count))"

} catch {
    Diag ("FATAL: {0}" -f $_.Exception.Message)
}

exit 0
