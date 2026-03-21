"""
Wrapper over the Fabric Graph Model REST API.

API reference: https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items

Endpoints:
  - List Graph Models:           https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/list-graph-models
  - Create Graph Model:          https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/create-graph-model
  - Get Graph Model:             https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/get-graph-model
  - Update Graph Model:          https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/update-graph-model
  - Delete Graph Model:          https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/delete-graph-model
  - Get Graph Model Definition:  https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/get-graph-model-definition
  - Update Graph Model Definition: https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/update-graph-model-definition
  - Execute Query (beta):        https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/execute-query(beta)
  - Get Queryable Graph Type (beta): https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/items/get-queryable-graph-type(beta)
"""
import base64
import json
import time
import requests
from auth import get_headers
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID


class GraphClient:

    def __init__(self, workspace_id: str = FABRIC_WORKSPACE_ID):
        self.workspace_id = workspace_id
        self.base_url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/graphModels"

    def _headers(self) -> dict:
        return {**get_headers(), "Content-Type": "application/json"}

    def _url(self, graph_id: str = None, action: str = None) -> str:
        url = self.base_url
        if graph_id:
            url = f"{url}/{graph_id}"
        if action:
            url = f"{url}/{action}"
        return url

    def _handle_lro(self, response: requests.Response, poll_interval: int = 5) -> dict | None:
        """Poll a long-running operation until complete, then fetch the result."""
        if response.status_code != 202:
            return None
        operation_url = response.headers.get("Location")
        retry_after = int(response.headers.get("Retry-After", poll_interval))
        print(f"  LRO accepted - polling {operation_url}")
        while True:
            time.sleep(retry_after)
            poll = requests.get(operation_url, headers=get_headers())
            poll.raise_for_status()
            body = poll.json()
            status = body.get("status", "Unknown")
            print(f"  LRO status: {status}")
            if status == "Succeeded":
                result_resp = requests.get(f"{operation_url}/result", headers=get_headers())
                if result_resp.status_code == 200:
                    return result_resp.json()
                return body
            if status in ("Failed", "Cancelled"):
                error = body.get("error", {})
                raise RuntimeError(
                    f"LRO {status}: {error.get('errorCode', 'unknown')} - "
                    f"{error.get('message', body)}"
                )

    # -- List Graph Models -----------------------------------------------------
    # GET /v1/workspaces/{workspaceId}/graphModels

    def list_graph_models(self) -> list[dict]:
        """List all graph models in the workspace."""
        results = []
        url = self._url()
        params = {}
        while url:
            response = requests.get(url, headers=get_headers(), params=params)
            response.raise_for_status()
            body = response.json()
            results.extend(body.get("value", []))
            url = body.get("continuationUri")
            params = {}
        return results

    # -- Get Graph Model -------------------------------------------------------
    # GET /v1/workspaces/{workspaceId}/graphModels/{graphModelId}

    def get_graph_model(self, graph_id: str) -> dict:
        """Get properties of a specific graph model."""
        response = requests.get(self._url(graph_id), headers=get_headers())
        response.raise_for_status()
        return response.json()

    # -- Get Graph Model Definition --------------------------------------------
    # POST /v1/workspaces/{workspaceId}/graphModels/{graphModelId}/getDefinition

    def get_definition(self, graph_id: str) -> dict:
        """Get the graph model definition. Supports LRO."""
        response = requests.post(
            self._url(graph_id, "getDefinition"),
            headers=self._headers(),
        )
        if response.status_code == 202:
            return self._handle_lro(response)
        response.raise_for_status()
        return response.json()

    def get_definition_decoded(self, graph_id: str) -> dict:
        """Get the graph model definition with base64 payloads decoded."""
        raw = self.get_definition(graph_id)
        parts = raw.get("definition", {}).get("parts", [])
        decoded = {}
        for part in parts:
            payload = part.get("payload", "")
            try:
                decoded[part["path"]] = json.loads(base64.b64decode(payload))
            except (json.JSONDecodeError, Exception):
                decoded[part["path"]] = base64.b64decode(payload).decode("utf-8", errors="replace")
        return decoded

    # -- Execute Query (beta) --------------------------------------------------
    # POST /v1/workspaces/{workspaceId}/graphModels/{graphModelId}/executeQuery?beta=true

    def execute_query(self, graph_id: str, query: str) -> dict:
        """Execute a GQL query against the graph model. Returns the full response."""
        response = requests.post(
            self._url(graph_id, "executeQuery"),
            headers=self._headers(),
            params={"beta": "true"},
            json={"query": query},
        )
        response.raise_for_status()
        return response.json()

    # -- Get Queryable Graph Type (beta) ---------------------------------------
    # GET /v1/workspaces/{workspaceId}/graphModels/{graphModelId}/getQueryableGraphType?beta=true

    def get_queryable_graph_type(self, graph_id: str) -> dict:
        """Get the graph schema (node types and edge types)."""
        response = requests.get(
            self._url(graph_id, "getQueryableGraphType"),
            headers=get_headers(),
            params={"beta": "true"},
        )
        response.raise_for_status()
        return response.json()

    # -- Refresh Graph (Background Job) ----------------------------------------
    # POST /v1/workspaces/{workspaceId}/graphModels/{graphModelId}/jobs/refreshGraph/instances
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/graphmodel/background-jobs/run-on-demand-refresh-graph

    def refresh(self, graph_id: str, wait: bool = True, poll_interval: int = 15) -> dict:
        """Trigger an on-demand graph refresh. If wait=True, polls until complete."""
        url = self._url(graph_id, "jobs/refreshGraph/instances")
        response = requests.post(url, headers=self._headers())
        if response.status_code == 200:
            print("  Refresh completed immediately.")
            return {"status": "Completed"}
        if response.status_code == 202:
            location = response.headers.get("Location")
            retry_after = int(response.headers.get("Retry-After", poll_interval))
            print(f"  Refresh job accepted (polling every {retry_after}s)...")
            if not wait:
                return {"status": "Accepted", "location": location}
            while True:
                time.sleep(retry_after)
                poll = requests.get(location, headers=get_headers())
                poll.raise_for_status()
                body = poll.json()
                status = body.get("status", "Unknown")
                print(f"  Refresh status: {status}")
                if status in ("Completed", "Failed", "Cancelled"):
                    if body.get("failureReason"):
                        raise RuntimeError(
                            f"Refresh {status}: {body['failureReason'].get('message', body['failureReason'])}"
                        )
                    return body
                retry_after = min(retry_after, 15)
        response.raise_for_status()

    # -- Delete Graph Model ----------------------------------------------------
    # DELETE /v1/workspaces/{workspaceId}/graphModels/{graphModelId}

    def delete_graph_model(self, graph_id: str) -> int:
        """Delete a graph model. Returns HTTP status code."""
        response = requests.delete(self._url(graph_id), headers=get_headers())
        response.raise_for_status()
        return response.status_code


if __name__ == "__main__":
    client = GraphClient()

    print("=== List Graph Models ===")
    models = client.list_graph_models()
    for m in models:
        print(f"  {m['displayName']} (id: {m['id']})")

    if not models:
        print("  No graph models found.")
    else:
        gm = models[0]
        gm_id = gm["id"]

        print(f"\n=== Get Graph Model: {gm['displayName']} ===")
        print(json.dumps(client.get_graph_model(gm_id), indent=2))

        print(f"\n=== Get Queryable Graph Type ===")
        graph_type = client.get_queryable_graph_type(gm_id)
        print(f"Node types ({len(graph_type.get('nodeTypes', []))}):")
        for nt in graph_type.get("nodeTypes", []):
            props = [f"{p['name']} ({p['type']})" for p in nt.get("properties", [])]
            print(f"  {nt['labels']} - keys: {nt.get('primaryKeyProperties', [])}")
            print(f"    properties: {', '.join(props)}")
        print(f"Edge types ({len(graph_type.get('edgeTypes', []))}):")
        for et in graph_type.get("edgeTypes", []):
            print(f"  {et['labels']}: {et['sourceNodeType']['alias']} -> {et['destinationNodeType']['alias']}")

        print(f"\n=== Get Definition (decoded) ===")
        decoded = client.get_definition_decoded(gm_id)
        for path, content in decoded.items():
            print(f"\n  --- {path} ---")
            if isinstance(content, dict):
                print(json.dumps(content, indent=2, default=str))
            else:
                print(content[:500] if len(content) > 500 else content)
