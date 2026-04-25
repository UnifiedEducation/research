"""Study-03: Prove DuckDB delta_scan can read the mirror's Tables/ path.

This is the exact pattern the extended read_delta() macro generates for
the `fabric` target. If this works, the macro works.

Uses DuckDB 1.4.4 (pinned to match the existing dbt study), the azure
extension for ABFSS access, and the delta extension for Delta Lake
readback. Authenticates with the project SP.
"""

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import (
    AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET,
    AZURE_TENANT_ID,
    BRONZE_MIRROR_ID,
    FABRIC_WORKSPACE_ID,
    tables_abfss_root,
)

TABLES = [
    ("(no schema)", "smoke_test"),
    ("youtube", "videos"),
    ("skool", "members"),
    ("test", "row_marker_demo"),
]


def main() -> None:
    con = duckdb.connect()
    con.execute("INSTALL azure; LOAD azure;")
    con.execute("INSTALL delta; LOAD delta;")
    con.execute(f"""
        CREATE OR REPLACE SECRET (
            TYPE AZURE,
            PROVIDER SERVICE_PRINCIPAL,
            TENANT_ID '{AZURE_TENANT_ID}',
            CLIENT_ID '{AZURE_CLIENT_ID}',
            CLIENT_SECRET '{AZURE_CLIENT_SECRET}',
            ACCOUNT_NAME 'onelake'
        );
    """)

    root = tables_abfss_root()
    print(f"Mirror Tables root: {root}")
    print()

    for schema, table in TABLES:
        path = f"{root}/{schema}/{table}" if schema != "(no schema)" else f"{root}/{table}"
        print(f"--- {schema}.{table} at {path}")
        try:
            rows = con.execute(f"SELECT * FROM delta_scan('{path}')").fetchall()
            cols = [d[0] for d in con.description]
            print(f"  columns: {cols}")
            print(f"  rows: {len(rows)}")
            for r in rows:
                print(f"    {r}")
        except Exception as e:
            print(f"  ERROR: {e}")
        print()


if __name__ == "__main__":
    main()
