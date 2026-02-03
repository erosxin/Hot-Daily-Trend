#!/usr/bin/env python3
with open(r"C:\AIwork\Daily hot news report system\docs\favorite.html", "r", encoding="utf-8") as f:
    content = f.read()
    
# 检查是否包含 api_key 参数
if "api_key" in content:
    print("[OK] favorite.html 包含 api_key 参数")
else:
    print("[ERROR] favorite.html 缺少 api_key 参数")
    
# 检查 supabaseUrl
if "supabaseUrl" in content:
    print("[OK] favorite.html 包含 supabaseUrl")
else:
    print("[ERROR] favorite.html 缺少 supabaseUrl")
