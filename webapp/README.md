# BMAD Fabric Dashboard

A Next.js + FastAPI web application that visualizes Microsoft Fabric data through a GraphQL API, with Entra ID (Azure AD) authentication and OBO (On-Behalf-Of) token exchange.

## Architecture

```
Browser (Next.js static export)
  |-- MSAL popup login --> Entra ID
  |-- Bearer token --> FastAPI backend
                          |-- OBO exchange --> Fabric-scoped token
                          |-- Proxied GraphQL query --> Fabric GraphQL API
                          |-- JSON response back to frontend
```

Single-container deployment: FastAPI serves both the API and the static frontend from the same origin, eliminating CORS complexity.

## Prerequisites

- **Azure App Registration** with:
  - SPA redirect URI: `http://localhost:3000/redirect.html` (dev) + your production URL
  - "Expose an API" scope: `api://{client-id}/access_as_user`
  - API permissions: `https://analysis.windows.net/powerbi/api/GraphQLApi.Execute.All`
  - A client secret
- **Microsoft Fabric** workspace with a GraphQL API endpoint
- Node.js 22+, Python 3.12+

## Setup

1. Copy `.env.example` to `.env` and fill in your values
2. Copy the MSAL values to `frontend/.env.local`:
   ```
   NEXT_PUBLIC_MSAL_CLIENT_ID=your-client-id
   NEXT_PUBLIC_MSAL_TENANT_ID=your-tenant-id
   NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
   ```

### Local Development

```bash
# Frontend (terminal 1)
cd frontend
npm install
npm run dev

# Backend (terminal 2)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Docker

```bash
cd deployment
docker-compose up --build
```

### Azure Container Apps

```bash
cd deployment
python deploy.py dev    # or: python deploy.py prod
python smoke_test.py https://your-app-url.azurecontainerapps.io
```

## Project Structure

```
frontend/           Next.js 16 + React 19 + TypeScript + Tailwind + Recharts
  app/
    charts/         6 chart components (bar, scatter, pie)
    auth-config.ts  MSAL configuration
    msal-provider.tsx  Auth context (CDN-loaded MSAL v2)
    use-graphql.ts  Custom hook for authenticated GraphQL queries
backend/
  main.py           FastAPI server (OBO exchange + GraphQL proxy + static serving)
  requirements.txt  Python dependencies
deployment/
  Dockerfile        Multi-stage build (Node + Python)
  docker-compose.yml
  deploy.py         Azure Container Apps deployment script
  smoke_test.py     Post-deployment validation (5 checks)
```

## Security Notes

- All secrets loaded from environment variables (never hardcoded)
- OBO flow preserves user identity for Fabric row-level security
- GraphQL endpoint requires Bearer token authentication
- CORS disabled in production (same-origin serving)
- Static file serving validates paths to prevent directory traversal
