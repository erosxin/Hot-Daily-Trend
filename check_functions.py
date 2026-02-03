#!/usr/bin/env python3
import requests

headers = {'Authorization': 'Bearer sbp_e59e98da75a23001df362e744263214481761d50'}
r = requests.get('https://api.supabase.com/v1/projects/ietunkxgukxpeacoiigl/functions', headers=headers)
print(f"Status: {r.status_code}")
funcs = r.json()
for f in funcs:
    print(f"{f['slug']}: version={f['version']}, status={f['status']}")
