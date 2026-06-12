# Scholar Studio - Agent 任务完成通知
# Hook event: Stop
# 当 Agent 完成响应后弹出 Windows 通知

param()
$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json

$message = $input_json.last_assistant_message
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

exit 0
