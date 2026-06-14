# Scholar Studio - Agent 任务完成通知
# Hook event: Stop
# 当 Agent 完成响应后弹出 Windows 通知

param()
try {
    $input_json = [Console]::In.ReadToEnd()
    if (-not $input_json) { exit 0 }
    $ctx = $input_json | ConvertFrom-Json -ErrorAction Stop

    # 官方要求: Stop hook 必须检查 stop_hook_active，为 true 时直接 exit 0 防止死循环
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
    # 静默失败，不阻断 Stop 事件
}

exit 0
