"""Test graph refresh with beta=true query parameter."""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clients"))
import requests
from auth import get_headers
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID

GM_ID = "f8c9a893-b106-4d26-bea8-dfee710bd694"
WS_ID = FABRIC_WORKSPACE_ID

headers = {**get_headers(), "Content-Type": "application/json"}

def try_refresh(label, url, params=None):
    print(f"\n--- {label} ---")
    print(f"  POST {url}")
    if params:
        print(f"  Params: {params}")
    resp = requests.post(url, headers=headers, params=params)
    print(f"  Status: {resp.status_code}")
    for h in ["Location", "Retry-After"]:
        if h in resp.headers:
            print(f"  {h}: {resp.headers[h]}")
    if resp.text:
        try:
            print(f"  Response: {json.dumps(resp.json(), indent=2)}")
        except Exception:
            print(f"  Response: {resp.text[:500]}")
    return resp

print("=" * 60)
print("  GRAPH REFRESH - WITH beta=true")
print("=" * 60)

# graphModels endpoint with beta=true
try_refresh(
    "graphModels + refreshGraph + beta=true",
    f"{FABRIC_API_BASE}/workspaces/{WS_ID}/graphModels/{GM_ID}/jobs/refreshGraph/instances",
    params={"beta": "true"}
)

# items endpoint with beta=true
try_refresh(
    "items + refreshGraph + beta=true",
    f"{FABRIC_API_BASE}/workspaces/{WS_ID}/items/{GM_ID}/jobs/refreshGraph/instances",
    params={"beta": "true"}
)

# Also try Refresh (matching job history jobType) with beta=true
try_refresh(
    "graphModels + Refresh + beta=true",
    f"{FABRIC_API_BASE}/workspaces/{WS_ID}/graphModels/{GM_ID}/jobs/Refresh/instances",
    params={"beta": "true"}
)

try_refresh(
    "items + Refresh + beta=true",
    f"{FABRIC_API_BASE}/workspaces/{WS_ID}/items/{GM_ID}/jobs/Refresh/instances",
    params={"beta": "true"}
)

print("\n" + "=" * 60)
print("  DONE")
print("=" * 60)
