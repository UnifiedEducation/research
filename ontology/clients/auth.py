import requests
from config import AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET

TOKEN_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
SCOPE = "https://api.fabric.microsoft.com/.default"


def get_token() -> str:
    response = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope": SCOPE,
    })
    response.raise_for_status()
    return response.json()["access_token"]


def get_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}


if __name__ == "__main__":
    token = get_token()
    print(f"Token acquired ({len(token)} chars)")
    print(f"First 20 chars: {token[:20]}...")
