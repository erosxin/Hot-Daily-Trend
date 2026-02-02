import subprocess
import os

task_name = "Daily AI News"
script_path = r"C:\AIwork\Daily hot news report system\daily_task.py"
python_path = r"C:\AIwork\Python314\python.exe"
time = "07:30"

# PowerShell 命令
ps_script = f'''
$action = New-ScheduledTaskAction -Execute "{python_path}" -Argument '"{script_path}"'
$trigger = New-ScheduledTaskTrigger -Daily -At {time}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "{task_name}" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
'''

# 写入临时 PowerShell 脚本
ps_file = r"C:\AIwork\Daily hot news report system\create_task.ps1"
with open(ps_file, 'w', encoding='utf-8') as f:
    f.write(ps_script)

print(f"Task: {task_name}")
print(f"Time: {time} daily")
print(f"Script: {script_path}")
print()
print("请以管理员身份运行以下命令:")
print("-" * 50)
print(f'powershell -ExecutionPolicy Bypass -File "{ps_file}"')
print("-" * 50)
