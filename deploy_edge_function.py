#!/usr/bin/env python3
"""
Deploy Supabase Edge Function using the Management API
"""
import os
import requests
import zipfile
import io

PROJECT_REF = "ietunkxgukxpeacoiigl"
FUNCTION_NAME = "process-favorite"
EDGE_FUNCTION_PATH = r"C:\AIwork\.openclaw\workspace\supabase\functions\process-favorite"

# Get token from environment
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not SUPABASE_ACCESS_TOKEN:
    print("Supabase Access Token is required.")
    print("Get it from: https://supabase.com/dashboard/account/tokens")
    SUPABASE_ACCESS_TOKEN = input("Enter Supabase Access Token: ").strip()

# Read the function file (binary mode)
index_path = os.path.join(EDGE_FUNCTION_PATH, "index.ts")
with open(index_path, "rb") as f:
    entrypoint = f.read()

# Create ZIP file
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("index.ts", entrypoint)
    # Add import map if exists
    import_map_path = os.path.join(EDGE_FUNCTION_PATH, "import_map.json")
    if os.path.exists(import_map_path):
        with open(import_map_path, "rb") as f:
            zf.writestr("import_map.json", f.read())

zip_content = zip_buffer.getvalue()

# Upload endpoint
url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/functions/{FUNCTION_NAME}/upload"

headers = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/zip"
}

print(f"Deploying {FUNCTION_NAME} to {PROJECT_REF}...")

response = requests.post(url, headers=headers, data=zip_content)

if response.status_code in [200, 201]:
    print("[OK] Deployment successful!")
    print(response.json())
else:
    print(f"[ERROR] Deployment failed: {response.status_code}")
    print(response.text)
