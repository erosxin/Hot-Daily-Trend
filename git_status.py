import subprocess
import os

git_path = r"C:\Program Files\Git\bin\git.exe"
repo_path = r"C:\AIwork\Daily hot news report system"

# 配置 git
subprocess.run([git_path, "config", "--global", "user.name", "Eros"], check=False)
subprocess.run([git_path, "config", "--global", "user.email", "eros@cleversports.asia"], check=False)

# 切换到仓库目录
os.chdir(repo_path)

# 检查状态
result = subprocess.run([git_path, "status"], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
