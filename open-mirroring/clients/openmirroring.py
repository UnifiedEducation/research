"""Minimal Open Mirroring landing-zone client.

Wraps the ADLS Gen2 calls needed to push data into a Fabric Open Mirrored
Database. Intentionally thin - the landing zone protocol is the source of
truth; this module just saves the caller from writing boilerplate.

Protocol reference: feasibility/open-mirroring/docs/landing-zone-format.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from azure.storage.filedatalake import DataLakeServiceClient, FileSystemClient

from auth import get_datalake_client
from config import FABRIC_WORKSPACE_ID


@dataclass(frozen=True)
class TableRef:
    table: str
    schema: str | None = None

    def folder_path(self, mirror_id: str) -> str:
        prefix = f"{mirror_id}/Files/LandingZone"
        if self.schema:
            return f"{prefix}/{self.schema}.schema/{self.table}"
        return f"{prefix}/{self.table}"


class MirrorClient:
    """Client scoped to a single Mirrored Database item."""

    def __init__(self, mirror_id: str, workspace_id: str = FABRIC_WORKSPACE_ID,
                 dls: DataLakeServiceClient | None = None) -> None:
        self.mirror_id = mirror_id
        self.workspace_id = workspace_id
        self._dls = dls or get_datalake_client()
        self._fs: FileSystemClient = self._dls.get_file_system_client(workspace_id)

    def ensure_table(self, table: TableRef, key_columns: list[str],
                     upsert_by_default: bool = False,
                     detect_by_last_update: bool = False) -> None:
        folder = table.folder_path(self.mirror_id)
        dir_client = self._fs.get_directory_client(folder)
        if not dir_client.exists():
            dir_client.create_directory()
        meta: dict = {"keyColumns": key_columns}
        if upsert_by_default:
            meta["isUpsertDefaultRowMarker"] = True
        if detect_by_last_update:
            meta["fileDetectionStrategy"] = "LastUpdateTimeFileDetection"
        meta_path = f"{folder}/_metadata.json"
        file_client = self._fs.get_file_client(meta_path)
        payload = json.dumps(meta, indent=2).encode("utf-8")
        file_client.upload_data(payload, overwrite=True)

    def next_data_filename(self, table: TableRef, extension: str = "parquet") -> str:
        folder = table.folder_path(self.mirror_id)
        max_num = 0
        for p in self._fs.get_paths(path=folder, recursive=False):
            name = Path(p.name).name
            stem = name.split(".")[0]
            if stem.isdigit() and len(stem) == 20:
                max_num = max(max_num, int(stem))
        return f"{(max_num + 1):020d}.{extension}"

    def upload_data_file(self, table: TableRef, local_path: str | Path,
                         remote_filename: str | None = None) -> str:
        folder = table.folder_path(self.mirror_id)
        filename = remote_filename or self.next_data_filename(
            table, extension=Path(local_path).suffix.lstrip(".") or "parquet"
        )
        remote_path = f"{folder}/{filename}"
        file_client = self._fs.get_file_client(remote_path)
        with open(local_path, "rb") as fh:
            data = fh.read()
        file_client.upload_data(data, overwrite=True)
        return remote_path

    def list_processed(self, table: TableRef) -> list[str]:
        folder = table.folder_path(self.mirror_id)
        return [p.name for p in self._fs.get_paths(path=f"{folder}/_ProcessedFiles",
                                                    recursive=False)] \
            if self._fs.get_directory_client(f"{folder}/_ProcessedFiles").exists() else []
