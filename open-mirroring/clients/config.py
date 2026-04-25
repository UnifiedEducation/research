import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

AZURE_TENANT_ID = os.environ["AZURE_TENANT_ID"]
AZURE_CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
AZURE_CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]

FABRIC_WORKSPACE_ID = os.environ["FABRIC_DEV_WORKSPACE_ID"]

BRONZE_MIRROR_ID = os.environ.get("BRONZE_MIRROR_ID")
BRONZE_MIRROR_NAME = os.environ.get("BRONZE_MIRROR_NAME", "bronze_mirror")

ONELAKE_DFS_HOST = "https://onelake.dfs.fabric.microsoft.com"
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"


def landing_zone_url(mirror_id: str | None = None) -> str:
    mid = mirror_id or BRONZE_MIRROR_ID
    if not mid:
        raise RuntimeError("BRONZE_MIRROR_ID not set. Run study-01 poc_create_mirror.py first.")
    return f"{ONELAKE_DFS_HOST}/{FABRIC_WORKSPACE_ID}/{mid}/Files/LandingZone"


def tables_abfss_root(mirror_id: str | None = None) -> str:
    mid = mirror_id or BRONZE_MIRROR_ID
    if not mid:
        raise RuntimeError("BRONZE_MIRROR_ID not set.")
    return f"abfss://{FABRIC_WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/{mid}/Tables"
