$action = New-ScheduledTaskAction -Execute "C:\AIwork\Python314\python.exe" -Argument '"C:\AIwork\Daily hot news report system\daily_task.py"'
$trigger = New-ScheduledTaskTrigger -Daily -At "07:30"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "Daily AI News" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
