"""Study-01 / Q2: Service-principal smoke upload.

Proves: with SP credentials only, we can create a table folder, drop a
parquet file, and see it replicate into the mirrored DB's Delta tables.

Pre-reqs:
- BRONZE_MIRROR_ID in .env (run poc_create_mirror.py first, or paste from portal)
- Workspace role granted to the SP (Contributor on FABRIC_WORKSPACE_ID)
- Mirroring started on the item (portal Start button, or mirror_api.start_mirroring)
"""

import io
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import BRONZE_MIRROR_ID
from openmirroring import MirrorClient, TableRef
from mirror_api import get_mirroring_status, get_table_status


TABLE = TableRef(table="smoke_test")


def build_sample_parquet() -> Path:
    data = {
        "id": ["s001", "s002", "s003"],
        "payload": ["hello", "world", "fabric"],
        "created_at": ["2026-04-20T10:00:00", "2026-04-20T10:00:01", "2026-04-20T10:00:02"],
    }
    table = pa.table(data)
    tmp = Path(__file__).parent / "_tmp_smoke.parquet"
    pq.write_table(table, tmp)
    return tmp


def main() -> None:
    if not BRONZE_MIRROR_ID:
        raise SystemExit("BRONZE_MIRROR_ID not set in .env")

    print(f"Mirror: {BRONZE_MIRROR_ID}")
    print(f"Table: {TABLE.table} (no schema)")

    client = MirrorClient(mirror_id=BRONZE_MIRROR_ID)
    client.ensure_table(TABLE, key_columns=["id"])
    print("Created table folder + _metadata.json")

    local = build_sample_parquet()
    print(f"Wrote local parquet: {local}")

    remote = client.upload_data_file(TABLE, local)
    print(f"Uploaded -> {remote}")

    local.unlink()

    print()
    print("Polling mirroring status...")
    status = get_mirroring_status(BRONZE_MIRROR_ID)
    print(f"Mirror status: {status}")
    tables = get_table_status(BRONZE_MIRROR_ID)
    print(f"Table statuses: {tables}")


if __name__ == "__main__":
    main()
