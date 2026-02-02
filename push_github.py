import subprocess
import os

git_path = r"C:\Program Files\Git\bin\git.exe"
repo_path = r"C:\AIwork\Daily hot news report system"
token = "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"

os.chdir(repo_path)

# 设置远程 URL
remote_url = f"https://{token}@github.com/erosxin/Hot-Daily-Trend.git"
subprocess.run([git_path, "remote", "set-url", "origin", remote_url], check=False)

# 添加 daily_task.py
subprocess.run([git_path, "add", "daily_task.py"], check=False)
subprocess.run([git_path, "add", "src/favorites_api.py"], check=False)
subprocess.run([git_path, "add", "src/email_sender.py"], check=False)
subprocess.run([git_path, "add", "src/data_models.py"], check=False)
subprocess.run([git_path, "add", "src/nlp_processor.py"], check=False)
subprocess.run([git_path, "add", "src/display_module.py"], check=False)

# 提交
subprocess.run([git_path, "commit", "-m", "Add daily task files for GitHub Actions"], check=False)

# 推送
result = subprocess.run([git_path, "push", "origin", "master"], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)

if result.returncode == 0:
    print("\n推送成功！")
else:
    print("\n推送失败")