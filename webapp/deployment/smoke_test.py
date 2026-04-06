"""Post-deployment smoke tests for BMAD Web App.

Validates that a deployed instance is serving the frontend and API correctly.
Does NOT test authenticated flows (no user token in CI).

Usage:
    python smoke_test.py https://your-app.azurecontainerapps.io
"""
import argparse
import sys

import requests


def test_health(base_url: str) -> bool:
    """API health endpoint responds with status ok."""
    resp = requests.get(f"{base_url}/api/health", timeout=10)
    data = resp.json()
    ok = resp.status_code == 200 and data.get("status") == "ok" and "graphql_api_id" in data
    print(f"  Health endpoint: {'PASS' if ok else 'FAIL'} ({resp.status_code}, {data})")
    return ok


def test_frontend_served(base_url: str) -> bool:
    """Root URL serves the Next.js frontend HTML."""
    resp = requests.get(base_url, timeout=10)
    ok = resp.status_code == 200 and "<!DOCTYPE html>" in resp.text
    print(f"  Frontend served: {'PASS' if ok else 'FAIL'} ({resp.status_code}, {len(resp.text)} bytes)")
    return ok


def test_redirect_page(base_url: str) -> bool:
    """MSAL redirect.html is accessible."""
    resp = requests.get(f"{base_url}/redirect.html", timeout=10)
    ok = resp.status_code == 200 and "<html>" in resp.text
    print(f"  Redirect page:  {'PASS' if ok else 'FAIL'} ({resp.status_code})")
    return ok


def test_static_assets(base_url: str) -> bool:
    """Next.js static assets (_next/) are served."""
    resp = requests.get(base_url, timeout=10)
    # Check that the HTML references _next/ assets
    ok = resp.status_code == 200 and "_next/" in resp.text
    print(f"  Static assets:  {'PASS' if ok else 'FAIL'}")
    return ok


def test_graphql_requires_auth(base_url: str) -> bool:
    """GraphQL endpoint rejects unauthenticated requests with 401."""
    resp = requests.post(
        f"{base_url}/api/graphql",
        json={"query": "{ films { items { title } } }"},
        timeout=10,
    )
    ok = resp.status_code == 401
    print(f"  Auth required:  {'PASS' if ok else 'FAIL'} ({resp.status_code})")
    return ok


def run_smoke_tests(base_url: str) -> bool:
    base_url = base_url.rstrip("/")
    print(f"Running smoke tests against {base_url}")
    print()

    results = [
        test_health(base_url),
        test_frontend_served(base_url),
        test_redirect_page(base_url),
        test_static_assets(base_url),
        test_graphql_requires_auth(base_url),
    ]

    passed = sum(results)
    total = len(results)
    print()
    print(f"Results: {passed}/{total} passed")
    return all(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test a deployed BMAD Web App")
    parser.add_argument("url", help="Base URL of the deployed app")
    args = parser.parse_args()

    if not run_smoke_tests(args.url):
        sys.exit(1)
