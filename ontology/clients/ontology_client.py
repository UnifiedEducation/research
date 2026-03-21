"""
Wrapper over the Fabric Ontology REST API.

API reference: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items

Endpoints:
  - List Ontologies:        https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/list-ontologies
  - Create Ontology:        https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/create-ontology
  - Get Ontology:           https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/get-ontology
  - Update Ontology:        https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/update-ontology
  - Delete Ontology:        https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/delete-ontology
  - Get Ontology Definition:    https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/get-ontology-definition
  - Update Ontology Definition: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/update-ontology-definition
"""
import base64
import json
import time
import requests
from auth import get_headers
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID


class OntologyClient:

    def __init__(self, workspace_id: str = FABRIC_WORKSPACE_ID):
        self.workspace_id = workspace_id
        self.base_url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/ontologies"

    def _headers(self) -> dict:
        return {**get_headers(), "Content-Type": "application/json"}

    def _url(self, ontology_id: str = None, action: str = None) -> str:
        url = self.base_url
        if ontology_id:
            url = f"{url}/{ontology_id}"
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
                # Fetch the actual result from the /result endpoint
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

    # ── List Ontologies ─────────────────────────────────────────────
    # GET /v1/workspaces/{workspaceId}/ontologies
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/list-ontologies

    def list_ontologies(self, *, recursive: bool = None, root_folder_id: str = None) -> list[dict]:
        """List all ontologies in the workspace. Handles pagination automatically."""
        params = {}
        if recursive is not None:
            params["recursive"] = str(recursive).lower()
        if root_folder_id:
            params["rootFolderId"] = root_folder_id

        results = []
        url = self._url()
        while url:
            response = requests.get(url, headers=get_headers(), params=params)
            response.raise_for_status()
            body = response.json()
            results.extend(body.get("value", []))
            url = body.get("continuationUri")
            params = {}  # continuation URI includes params
        return results

    # ── Create Ontology ─────────────────────────────────────────────
    # POST /v1/workspaces/{workspaceId}/ontologies
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/create-ontology

    def create_ontology(self, display_name: str, *, description: str = None,
                        definition: dict = None) -> dict:
        """Create a new ontology. Supports LRO."""
        body = {"displayName": display_name}
        if description:
            body["description"] = description
        if definition:
            body["definition"] = definition
        response = requests.post(self._url(), headers=self._headers(), json=body)
        if response.status_code == 202:
            self._handle_lro(response)
            # Fetch the created ontology by listing and matching name
            return {"status": "created_async", "displayName": display_name}
        response.raise_for_status()
        return response.json()

    # ── Get Ontology ────────────────────────────────────────────────
    # GET /v1/workspaces/{workspaceId}/ontologies/{ontologyId}
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/get-ontology

    def get_ontology(self, ontology_id: str) -> dict:
        """Get properties of a specific ontology."""
        response = requests.get(self._url(ontology_id), headers=get_headers())
        response.raise_for_status()
        return response.json()

    # ── Update Ontology ─────────────────────────────────────────────
    # PATCH /v1/workspaces/{workspaceId}/ontologies/{ontologyId}
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/update-ontology

    def update_ontology(self, ontology_id: str, *, display_name: str = None,
                        description: str = None) -> dict:
        """Update ontology properties (name and/or description)."""
        body = {}
        if display_name:
            body["displayName"] = display_name
        if description is not None:
            body["description"] = description
        response = requests.patch(self._url(ontology_id), headers=self._headers(), json=body)
        response.raise_for_status()
        return response.json()

    # ── Delete Ontology ─────────────────────────────────────────────
    # DELETE /v1/workspaces/{workspaceId}/ontologies/{ontologyId}
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/delete-ontology

    def delete_ontology(self, ontology_id: str, *, hard_delete: bool = False) -> int:
        """Delete an ontology. Returns the HTTP status code."""
        params = {}
        if hard_delete:
            params["hardDelete"] = "True"
        response = requests.delete(self._url(ontology_id), headers=get_headers(), params=params)
        response.raise_for_status()
        return response.status_code

    # ── Get Ontology Definition ─────────────────────────────────────
    # POST /v1/workspaces/{workspaceId}/ontologies/{ontologyId}/getDefinition
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/get-ontology-definition

    def get_definition(self, ontology_id: str, *, format: str = None) -> dict:
        """Get the ontology definition. Supports LRO. Returns raw definition with base64 payloads."""
        params = {}
        if format:
            params["format"] = format
        response = requests.post(
            self._url(ontology_id, "getDefinition"),
            headers=self._headers(),
            params=params,
        )
        if response.status_code == 202:
            lro_result = self._handle_lro(response)
            return lro_result
        response.raise_for_status()
        return response.json()

    def get_definition_decoded(self, ontology_id: str) -> dict:
        """Get the ontology definition with base64 payloads decoded to dicts."""
        raw = self.get_definition(ontology_id)
        parts = raw.get("definition", {}).get("parts", [])
        decoded = {}
        for part in parts:
            payload = part.get("payload", "")
            try:
                decoded[part["path"]] = json.loads(base64.b64decode(payload))
            except (json.JSONDecodeError, Exception):
                decoded[part["path"]] = base64.b64decode(payload).decode("utf-8", errors="replace")
        return decoded

    # ── Update Ontology Definition ──────────────────────────────────
    # POST /v1/workspaces/{workspaceId}/ontologies/{ontologyId}/updateDefinition
    # Docs: https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/update-ontology-definition

    def update_definition(self, ontology_id: str, definition: dict,
                          *, update_metadata: bool = None) -> int:
        """Update (overwrite) the ontology definition. Supports LRO. Returns HTTP status code."""
        params = {}
        if update_metadata is not None:
            params["updateMetadata"] = str(update_metadata)
        body = {"definition": definition}
        response = requests.post(
            self._url(ontology_id, "updateDefinition"),
            headers=self._headers(),
            json=body,
            params=params,
        )
        if response.status_code == 202:
            self._handle_lro(response)
            return 202
        response.raise_for_status()
        return response.status_code

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def encode_part(path: str, content: dict | str) -> dict:
        """Encode a definition part for create/update calls."""
        if isinstance(content, dict):
            content = json.dumps(content)
        payload = base64.b64encode(content.encode("utf-8")).decode("ascii")
        return {"path": path, "payload": payload, "payloadType": "InlineBase64"}


if __name__ == "__main__":
    client = OntologyClient()

    print("=== List Ontologies ===")
    ontologies = client.list_ontologies()
    print(json.dumps(ontologies, indent=2))

    if ontologies:
        ont_id = ontologies[0]["id"]
        print(f"\n=== Get Ontology: {ont_id} ===")
        print(json.dumps(client.get_ontology(ont_id), indent=2))

        print(f"\n=== Get Definition (decoded) ===")
        decoded = client.get_definition_decoded(ont_id)
        print(json.dumps(decoded, indent=2, default=str))
