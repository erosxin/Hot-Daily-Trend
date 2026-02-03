#!/usr/bin/env python3
with open(r"C:\AIwork\Daily hot news report system\src\display_module.py", "r", encoding="utf-8") as f:
    content = f.read()
    if "api_key=default-api-key" in content:
        print("[OK] display_module.py 包含 api_key 修复")
    else:
        print("[ERROR] display_module.py 缺少 api_key 修复")
        # 检查旧代码
        if "signInAnonymously" in content:
            print("  -> 发现旧代码 signInAnonymously，需要重新推送")
