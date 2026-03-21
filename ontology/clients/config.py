import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

AZURE_TENANT_ID = os.environ["AZURE_TENANT_ID"]
AZURE_CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
AZURE_CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]
FABRIC_WORKSPACE_ID = os.environ["FABRIC_WORKSPACE_ID"]

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
