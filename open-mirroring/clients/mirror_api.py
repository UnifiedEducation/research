"""Fabric REST API helpers for the Mirrored Database item lifecycle.

Covers: create item, get item, start mirroring, stop mirroring, get status.
Long-running operations are polled via the `operationId` Location header.
"""

import base64
import json
import time

import requests

from auth import fabric_headers
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID


def _items_url(workspace_id: str) -> str:
    return f"{FABRIC_API_BASE}/workspaces/{workspace_id}/mirroredDatabases"


def open_mirror_definition(default_schema: str = "dbo") -> dict:
    """Minimal mirroring.json for an open ('GenericMirror') mirrored database.

    A create body without this definition results in an item that cannot
    start - startMirroring returns MirroringDefinitionMissing.
    """
    mirroring_json = {
        "properties": {
            "source": {
                "type": "GenericMirror",
                "typeProperties": {},
            },
            "target": {
                "type": "MountedRelationalDatabase",
                "typeProperties": {
                    "defaultSchema": default_schema,
                    "format": "Delta",
                },
            },
        }
    }
    payload_b64 = base64.b64encode(
        json.dumps(mirroring_json).encode("utf-8")
    ).decode("ascii")
    return {
        "parts": [
            {"path": "mirroring.json", "payload": payload_b64, "payloadType": "InlineBase64"}
        ]
    }


def create_mirrored_database(display_name: str, description: str = "",
                             workspace_id: str = FABRIC_WORKSPACE_ID,
                             definition: dict | None = None) -> dict:
    body = {
        "displayName": display_name,
        "description": description,
        "definition": definition or open_mirror_definition(),
    }
    r = requests.post(_items_url(workspace_id), headers=fabric_headers(), json=body)
    r.raise_for_status()
    return r.json()


def get_mirrored_database(mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID) -> dict:
    r = requests.get(f"{_items_url(workspace_id)}/{mirror_id}", headers=fabric_headers())
    r.raise_for_status()
    return r.json()


def start_mirroring(mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID) -> int:
    url = f"{_items_url(workspace_id)}/{mirror_id}/startMirroring"
    r = requests.post(url, headers=fabric_headers())
    r.raise_for_status()
    return r.status_code


def stop_mirroring(mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID) -> int:
    url = f"{_items_url(workspace_id)}/{mirror_id}/stopMirroring"
    r = requests.post(url, headers=fabric_headers())
    r.raise_for_status()
    return r.status_code


def get_mirroring_status(mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID) -> dict:
    url = f"{_items_url(workspace_id)}/{mirror_id}/getMirroringStatus"
    r = requests.post(url, headers=fabric_headers())
    r.raise_for_status()
    return r.json()


def get_table_status(mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID) -> dict:
    url = f"{_items_url(workspace_id)}/{mirror_id}/getTablesMirroringStatus"
    r = requests.post(url, headers=fabric_headers())
    r.raise_for_status()
    return r.json()


def wait_for_running(mirror_id: str, timeout_s: int = 300,
                     workspace_id: str = FABRIC_WORKSPACE_ID) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        last = get_mirroring_status(mirror_id, workspace_id)
        state = (last.get("status") or last.get("state") or "").lower()
        if state == "running":
            return last
        time.sleep(5)
    raise TimeoutError(f"Mirror did not reach Running within {timeout_s}s. Last status: {last}")
