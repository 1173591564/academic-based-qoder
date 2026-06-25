# Scholar Studio — Stop Hook: Task Done
# Outputs completion statistics and shows Windows toast notification
# Merged from statistics output + toast notification

$ErrorActionPreference = "SilentlyContinue"

$scholarHome = $env:SCHOLAR_HOME
if (-not $scholarHome) { $scholarHome = (Get-Location).Path }

# Output completion statistics
$parsedDir = Join-Path $scholarHome "output\parsed"
$parsedCount = 0
if (Test-Path $parsedDir) {
    $parsedCount = (Get-ChildItem -Path "$parsedDir\*.json" -ErrorAction SilentlyContinue).Count
}

$notesDir = Join-Path $scholarHome "output\notes"
$notesCount = 0
if (Test-Path $notesDir) {
    $notesCount = (Get-ChildItem -Path "$notesDir\*.md" -ErrorAction SilentlyContinue).Count
}

$draftsDir = Join-Path $scholarHome "output\drafts"
$draftsCount = 0
if (Test-Path $draftsDir) {
    $draftsCount = (Get-ChildItem -Path "$draftsDir\*.md" -ErrorAction SilentlyContinue).Count
}

Write-Output " Scholar Studio task complete. KB: $parsedCount papers | $notesCount notes | $draftsCount drafts."

# Show Windows toast notification
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $ctx = $raw | ConvertFrom-Json -ErrorAction Stop

    # Check stop_hook_active to prevent infinite loop
    if ($ctx.stop_hook_active -eq $true) { exit 0 }

    $message = $ctx.last_assistant_message
    if (-not $message) { $message = "任务已完成" }
    if ($message.Length -gt 120) { $message = $message.Substring(0, 120) + "..." }

    # Windows toast notification
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.Visible = $true
    $notify.BalloonTipTitle = "Scholar Studio"
    $notify.BalloonTipText = $message
    $notify.ShowBalloonTip(5000)
    Start-Sleep -Milliseconds 200
    $notify.Dispose()
} catch {
    # Silent failure, do not block Stop event
}

exit 0
