"""Deploy BMAD Web App to Azure Container Apps.

Prerequisites:
    - az CLI installed and logged in
    - .env file at project root or env vars set (CI)

Usage:
    python deploy.py dev           # Deploy to DEV
    python deploy.py prod          # Deploy to PROD
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Load .env if present (local dev)
load_dotenv(PROJECT_ROOT / ".env")


def az(*args: str, capture: bool = False) -> str:
    """Run an az CLI command. Returns stdout if capture=True."""
    cmd = ["az", *args]
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    else:
        subprocess.run(cmd, check=True)
        return ""


def deploy(target: str):
    resource_group = os.environ.get("AZURE_RESOURCE_GROUP", "bmad-webapp-rg")
    location = os.environ.get("AZURE_LOCATION", "australiaeast")
    acr_name = os.environ.get("AZURE_ACR_NAME", "bmadwebappacr")
    environment_name = "bmad-webapp-env"
    image_tag = os.environ.get("IMAGE_TAG", "latest")

    if target == "prod":
        app_name = "bmad-webapp-prod"
        workspace_id = os.environ["FABRIC_WORKSPACE_ID"]
    else:
        app_name = "bmad-webapp-dev"
        workspace_id = os.environ.get("FABRIC_DEV_WORKSPACE_ID", os.environ["FABRIC_WORKSPACE_ID"])

    print(f"=== BMAD Web App Deployment ({target}) ===")
    print(f"Resource Group: {resource_group}")
    print(f"Location:       {location}")
    print(f"ACR:            {acr_name}")
    print(f"App Name:       {app_name}")
    print(f"Workspace:      {workspace_id}")
    print()

    # Step 1: Create resource group
    print("[1/6] Creating resource group...")
    try:
        az("group", "create", "--name", resource_group, "--location", location, "--output", "none")
    except subprocess.CalledProcessError:
        pass  # Already exists

    # Step 2: Create Azure Container Registry
    print("[2/6] Creating container registry...")
    try:
        az("acr", "create", "--resource-group", resource_group, "--name", acr_name,
           "--sku", "Basic", "--admin-enabled", "true", "--output", "none")
    except subprocess.CalledProcessError:
        pass  # Already exists

    acr_login_server = az("acr", "show", "--name", acr_name, "--query", "loginServer", "-o", "tsv", capture=True)

    # Step 3: Build and push image (in ACR -- no local Docker needed)
    print("[3/6] Building and pushing Docker image...")
    az("acr", "build",
       "--registry", acr_name,
       "--image", f"{app_name}:{image_tag}",
       "--file", str(SCRIPT_DIR / "Dockerfile"),
       str(PROJECT_ROOT))

    # Step 4: Create Container Apps environment
    print("[4/6] Creating Container Apps environment...")
    try:
        az("containerapp", "env", "create",
           "--name", environment_name, "--resource-group", resource_group,
           "--location", location, "--output", "none")
    except subprocess.CalledProcessError:
        pass  # Already exists

    # Step 5: Deploy container app
    print("[5/6] Deploying container app...")
    acr_password = az("acr", "credential", "show", "--name", acr_name,
                      "--query", "passwords[0].value", "-o", "tsv", capture=True)

    env_vars = [
        f"AZURE_TENANT_ID={os.environ['AZURE_TENANT_ID']}",
        f"WEBAPP_CLIENT_ID={os.environ['WEBAPP_CLIENT_ID']}",
        f"WEBAPP_CLIENT_SECRET={os.environ['WEBAPP_CLIENT_SECRET']}",
        f"FABRIC_WORKSPACE_ID={os.environ['FABRIC_WORKSPACE_ID']}",
        f"FABRIC_DEV_WORKSPACE_ID={workspace_id}",
        f"FABRIC_GRAPHQL_API_ID={os.environ['FABRIC_GRAPHQL_API_ID']}",
        "STATIC_DIR=/app/static",
    ]

    image = f"{acr_login_server}/{app_name}:{image_tag}"

    try:
        az("containerapp", "create",
           "--name", app_name, "--resource-group", resource_group,
           "--environment", environment_name,
           "--image", image,
           "--registry-server", acr_login_server,
           "--registry-username", acr_name,
           "--registry-password", acr_password,
           "--target-port", "8000", "--ingress", "external",
           "--min-replicas", "0", "--max-replicas", "1",
           "--env-vars", *env_vars,
           "--output", "none")
    except subprocess.CalledProcessError:
        # App already exists -- update instead
        az("containerapp", "update",
           "--name", app_name, "--resource-group", resource_group,
           "--image", image,
           "--set-env-vars", *env_vars,
           "--output", "none")

    # Step 6: Get URL
    print("[6/6] Getting app URL...")
    app_url = az("containerapp", "show",
                 "--name", app_name, "--resource-group", resource_group,
                 "--query", "properties.configuration.ingress.fqdn", "-o", "tsv",
                 capture=True)

    print()
    print(f"=== Deployment complete ({target}) ===")
    print(f"App URL: https://{app_url}")
    print()
    print("IMPORTANT: Add this redirect URI to your Azure app registration (SPA platform):")
    print(f"  https://{app_url}/redirect.html")

    # Output for CI consumption
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"APP_URL=https://{app_url}\n")

    return f"https://{app_url}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy BMAD Web App")
    parser.add_argument("target", choices=["dev", "prod"], help="Deployment target")
    args = parser.parse_args()
    deploy(args.target)
