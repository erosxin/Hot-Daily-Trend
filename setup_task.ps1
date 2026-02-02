# Daily AI News - Windows 任务计划设置脚本
# 以管理员身份运行 PowerShell，然后运行此脚本

$taskName = "Daily AI News"
$scriptPath = "C:\AIwork\Daily hot news report system\daily_task.py"
$pythonPath = "C:\AIwork\Python314\python.exe"
$time = "08:00"

Write-Host "Creating Windows Task: $taskName" -ForegroundColor Green
Write-Host "Script: $scriptPath" -ForegroundColor Green
Write-Host "Time: $time daily" -ForegroundColor Green
Write-Host ""

# 创建 Action
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`""

# 创建 Trigger (每天 8:00)
$trigger = New-ScheduledTaskTrigger -Daily -At $time

# 设置任务为最高权限运行
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 注册任务
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force

Write-Host ""
Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host "You can verify in Task Scheduler (taskschd.msc)" -ForegroundColor Yellow

# 可选：立即运行一次测试
Write-Host ""
Read-Host "Run task now for testing? (y/n)" -ForegroundColor Yellow
if ($ans -eq "y") {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Task started!" -ForegroundColor Green
}
