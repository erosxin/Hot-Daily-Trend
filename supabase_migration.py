import os
import httpx

SUPABASE_URL = 'https://ietunkxgukxpeacoiigl.supabase.co'
ANON_KEY = 'sb_publishable_2J74WhPQQZ-U5qgbkUIAsQ_j_VHF4_7'

# 检查 plain_summary 字段是否存在（通过查询包含该字段的文章）
url = f"{SUPABASE_URL}/rest/v1/articles?select=id,title,plain_summary&limit=5"
headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
resp = httpx.get(url, headers=headers, follow_redirects=True)
print(f"Status: {resp.status_code}")
print(resp.text[:500])