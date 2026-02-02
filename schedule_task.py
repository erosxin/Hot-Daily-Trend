"""
定时任务调度器
支持 Windows 和 Linux/Mac
"""
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def get_python_cmd():
    """获取 Python 命令"""
    return sys.executable

def get_project_path():
    """获取项目路径"""
    return str(Path(__file__).parent.absolute())

def setup_cron_job(time_str="08:00"):
    """
    设置定时任务 (Linux/Mac)
    
    Args:
        time_str: 每日执行时间，格式 "HH:MM"
    """
    python_cmd = get_python_cmd()
    project_path = get_project_path()
    script_path = os.path.join(project_path, "daily_task.py")
    
    # 构建 crontab 命令
    hour, minute = time_str.split(":")
    cron_entry = f"{minute} {hour} * * * {python_cmd} {script_path} >> /tmp/daily_ai_news.log 2>&1"
    
    print("请手动添加 crontab 定时任务:")
    print(f"执行: crontab -e")
    print(f"添加行: {cron_entry}")
    print()
    return cron_entry

def setup_windows_task(time_str="08:00"):
    """
    设置 Windows 任务计划
    
    Args:
        time_str: 每日执行时间，格式 "HH:MM"
    """
    python_cmd = get_python_cmd()
    project_path = get_project_path()
    script_path = os.path.join(project_path, "daily_task.py")
    
    hour, minute = time_str.split(":")
    
    # Windows schtasks 命令
    cmd = f'schtasks /create /tn "Daily AI News" /tr "\"{python_cmd}\" \\"{script_path}\\"" /sc daily /st {time_str} /f'
    
    print("Windows 定时任务命令:")
    print(cmd)
    print()
    print("或者手动创建:")
    print(f"1. 打开「任务计划程序」")
    print(f"2. 创建基本任务")
    print(f"3. 名称: Daily AI News")
    print(f"4. 触发器: 每日 {time_str}")
    print(f"5. 操作: 启动程序")
    print(f"6. 程序: {python_cmd}")
    print(f"7. 参数: {script_path}")
    print(f"8. 起始于: {project_path}")
    return cmd

def run_now():
    """立即运行一次任务"""
    python_cmd = get_python_cmd()
    script_path = os.path.join(get_project_path(), "daily_task.py")
    os.system(f'"{python_cmd}" "{script_path}"')

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="每日AI趋势简报定时任务")
    parser.add_argument("--now", action="store_true", help="立即运行一次任务")
    parser.add_argument("--time", default="08:00", help="每日执行时间，格式 HH:MM，默认 08:00")
    parser.add_argument("--windows", action="store_true", help="显示 Windows 设置命令")
    parser.add_argument("--linux", action="store_true", help="显示 Linux/Mac 设置命令")
    
    args = parser.parse_args()
    
    if args.now:
        print("立即运行任务...")
        run_now()
    elif args.windows:
        setup_windows_task(args.time)
    elif args.linux:
        setup_cron_job(args.time)
    else:
        # 默认显示 Windows 命令
        setup_windows_task(args.time)
