"""Study-02 / Q3: __rowMarker__ semantics end-to-end.

Exercises all four operations:
  1. Initial load  (no __rowMarker__) -> treated as INSERT
  2. Update        (__rowMarker__=1, full row data)
  3. Delete        (__rowMarker__=2, key columns only)
  4. Upsert        (__rowMarker__=4)
  5. Key change    (DELETE old key + INSERT new key in same file)

After each step, query the SQL endpoint manually and record row state in
the README verdict section.
"""

import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import BRONZE_MIRROR_ID
from openmirroring import MirrorClient, TableRef


TABLE = TableRef(schema="test", table="row_marker_demo")

# Explicit schema - critical for incremental files. If pandas is left to
# infer types, a file with `location: [None]` alone becomes an int/null
# column and the mirror rejects it with SchemaMergeFailure against the
# existing string column. Always use an explicit pyarrow schema for
# producers that send deletes or partial rows.
SCHEMA = pa.schema([
    ("employee_id", pa.string()),
    ("location", pa.string()),
    ("__rowMarker__", pa.int32()),
])

INITIAL_SCHEMA = pa.schema([
    ("employee_id", pa.string()),
    ("location", pa.string()),
])


def parquet(rows: list[dict], path: Path, schema: pa.Schema = SCHEMA) -> Path:
    arrays = [pa.array([r.get(f.name) for r in rows], type=f.type) for f in schema]
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(table, path)
    return path


def main() -> None:
    if not BRONZE_MIRROR_ID:
        raise SystemExit("BRONZE_MIRROR_ID not set")
    client = MirrorClient(mirror_id=BRONZE_MIRROR_ID)
    client.ensure_table(TABLE, key_columns=["employee_id"])

    tmp = Path(__file__).parent / "_tmp"
    tmp.mkdir(exist_ok=True)

    print("[1] Initial load (no __rowMarker__) - whole file treated as INSERT")
    rows1 = [
        {"employee_id": "E0001", "location": "Redmond"},
        {"employee_id": "E0002", "location": "Redmond"},
        {"employee_id": "E0003", "location": "Redmond"},
    ]
    client.upload_data_file(TABLE, parquet(rows1, tmp / "01.parquet", schema=INITIAL_SCHEMA))
    time.sleep(5)

    print("[2] Update E0001 location -> Bellevue (__rowMarker__=1, full row)")
    rows2 = [{"employee_id": "E0001", "location": "Bellevue", "__rowMarker__": 1}]
    client.upload_data_file(TABLE, parquet(rows2, tmp / "02.parquet"))
    time.sleep(5)

    print("[3] Delete E0002 (__rowMarker__=2, location null)")
    rows3 = [{"employee_id": "E0002", "location": None, "__rowMarker__": 2}]
    client.upload_data_file(TABLE, parquet(rows3, tmp / "03.parquet"))
    time.sleep(5)

    print("[4] Upsert E0004 new + E0003 changed (__rowMarker__=4)")
    rows4 = [
        {"employee_id": "E0004", "location": "Seattle", "__rowMarker__": 4},
        {"employee_id": "E0003", "location": "Kirkland", "__rowMarker__": 4},
    ]
    client.upload_data_file(TABLE, parquet(rows4, tmp / "04.parquet"))
    time.sleep(5)

    print("[5] Key change: E0001 renamed to E0001_NEW (DELETE + INSERT in one file)")
    rows5 = [
        {"employee_id": "E0001", "location": None, "__rowMarker__": 2},
        {"employee_id": "E0001_NEW", "location": "Bellevue", "__rowMarker__": 0},
    ]
    client.upload_data_file(TABLE, parquet(rows5, tmp / "05.parquet"))

    print()
    print("Query the SQL endpoint and confirm final state:")
    print("  E0001_NEW | Bellevue")
    print("  E0003     | Kirkland")
    print("  E0004     | Seattle")
    print("(E0001 and E0002 should NOT be present)")


if __name__ == "__main__":
    main()
