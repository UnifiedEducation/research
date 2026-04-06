"""FastAPI backend gateway for Fabric GraphQL API.

Receives a user token from the Next.js frontend, exchanges it via OBO
for a Fabric-scoped token, and proxies GraphQL queries to Fabric.

In production, also serves the static frontend build.

Usage (local dev):
    uvicorn main:app --reload --port 8000

Usage (production):
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import msal
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# -- Config -------------------------------------------------------------------

TENANT_ID = os.environ["AZURE_TENANT_ID"]
WEBAPP_CLIENT_ID = os.environ["WEBAPP_CLIENT_ID"]
WEBAPP_CLIENT_SECRET = os.environ["WEBAPP_CLIENT_SECRET"]
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
DEV_WORKSPACE_ID = os.environ.get("FABRIC_DEV_WORKSPACE_ID", os.environ["FABRIC_WORKSPACE_ID"])
GRAPHQL_API_ID = os.environ["FABRIC_GRAPHQL_API_ID"]

FABRIC_SCOPE = "https://analysis.windows.net/powerbi/api/GraphQLApi.Execute.All"

STATIC_DIR = Path(os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend", "out")))

# -- MSAL confidential client (for OBO) --------------------------------------

msal_app = msal.ConfidentialClientApplication(
    client_id=WEBAPP_CLIENT_ID,
    client_credential=WEBAPP_CLIENT_SECRET,
    authority=AUTHORITY,
)

# -- FastAPI app --------------------------------------------------------------

app = FastAPI(title="BMAD Fabric Gateway")

# CORS only needed for local dev (frontend on :3000, backend on :8000).
# In production, frontend is served from same origin.
if os.environ.get("CORS_ORIGIN"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ["CORS_ORIGIN"]],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class GraphQLRequest(BaseModel):
    query: str
    variables: dict | None = None


def extract_bearer_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth[7:]


def exchange_obo(user_token: str) -> str:
    """Exchange a user token for a Fabric-scoped token via OBO."""
    result = msal_app.acquire_token_on_behalf_of(
        user_assertion=user_token,
        scopes=[FABRIC_SCOPE],
    )
    if "access_token" in result:
        return result["access_token"]

    error = result.get("error", "unknown")
    desc = result.get("error_description", "")
    if error == "interaction_required":
        raise HTTPException(status_code=401, detail="Re-authentication required")
    raise HTTPException(status_code=403, detail=f"OBO failed: {error} - {desc}")


# -- API Routes ---------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "graphql_api_id": GRAPHQL_API_ID}


@app.post("/api/graphql")
async def graphql_proxy(body: GraphQLRequest, request: Request):
    """Proxy a GraphQL query to Fabric, using OBO for user identity."""
    user_token = extract_bearer_token(request)
    fabric_token = exchange_obo(user_token)

    url = f"{FABRIC_API_BASE}/workspaces/{DEV_WORKSPACE_ID}/graphQLApis/{GRAPHQL_API_ID}/graphql"
    payload = {"query": body.query}
    if body.variables:
        payload["variables"] = body.variables

    resp = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {fabric_token}",
            "Content-Type": "application/json",
        },
    )

    return resp.json()


# -- Static frontend serving --------------------------------------------------

if STATIC_DIR.is_dir():
    STATIC_DIR_RESOLVED = STATIC_DIR.resolve()

    # Serve Next.js static assets (_next/*, etc.)
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next-assets")

    # Serve specific static files (redirect.html, favicon, etc.)
    @app.get("/redirect.html")
    async def redirect_page():
        return FileResponse(STATIC_DIR / "redirect.html")

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(STATIC_DIR / "favicon.ico")

    # Catch-all: serve index.html for any non-API route (SPA fallback)
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Resolve and validate path stays within STATIC_DIR (prevent traversal)
        file_path = (STATIC_DIR / path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR_RESOLVED)):
            raise HTTPException(status_code=400, detail="Invalid path")
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA routing)
        return FileResponse(STATIC_DIR / "index.html")
