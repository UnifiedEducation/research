import requests
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient

from config import AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, ONELAKE_DFS_HOST

FABRIC_TOKEN_SCOPE = "https://api.fabric.microsoft.com/.default"
STORAGE_TOKEN_SCOPE = "https://storage.azure.com/.default"
TOKEN_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"


def get_fabric_token() -> str:
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope": FABRIC_TOKEN_SCOPE,
    })
    r.raise_for_status()
    return r.json()["access_token"]


def fabric_headers() -> dict:
    return {"Authorization": f"Bearer {get_fabric_token()}"}


def get_credential() -> ClientSecretCredential:
    return ClientSecretCredential(
        tenant_id=AZURE_TENANT_ID,
        client_id=AZURE_CLIENT_ID,
        client_secret=AZURE_CLIENT_SECRET,
    )


def get_datalake_client() -> DataLakeServiceClient:
    return DataLakeServiceClient(account_url=ONELAKE_DFS_HOST, credential=get_credential())


if __name__ == "__main__":
    t = get_fabric_token()
    print(f"Fabric token acquired ({len(t)} chars)")
    cred = get_credential()
    storage_token = cred.get_token(STORAGE_TOKEN_SCOPE).token
    print(f"Storage token acquired ({len(storage_token)} chars)")
