"""Study-02 / Q4: Multiple schemas in a single mirrored database.

Creates four tables across two schemas in the same mirror and verifies
they land as distinct SQL-queryable schemas:

  bronze_mirror
    youtube.schema/
      videos
      channels
    skool.schema/
      communities
      members
"""

import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import BRONZE_MIRROR_ID
from openmirroring import MirrorClient, TableRef


def parquet(df: pd.DataFrame, path: Path) -> Path:
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    return path


SEEDS: list[tuple[TableRef, list[str], pd.DataFrame]] = [
    (TableRef("youtube", "videos"), ["video_id"],
     pd.DataFrame({"video_id": ["v1", "v2"], "title": ["A", "B"], "views": [100, 200]})),
    (TableRef("youtube", "channels"), ["channel_id"],
     pd.DataFrame({"channel_id": ["c1"], "name": ["Main"], "subs": [5000]})),
    (TableRef("skool", "communities"), ["community_id"],
     pd.DataFrame({"community_id": ["sk1"], "name": ["Creators"], "members": [120]})),
    (TableRef("skool", "members"), ["member_id"],
     pd.DataFrame({"member_id": ["m1", "m2"], "community": ["sk1", "sk1"], "posts": [3, 7]})),
]


def main() -> None:
    if not BRONZE_MIRROR_ID:
        raise SystemExit("BRONZE_MIRROR_ID not set")
    client = MirrorClient(mirror_id=BRONZE_MIRROR_ID)

    tmp = Path(__file__).parent / "_tmp"
    tmp.mkdir(exist_ok=True)

    for ref, keys, df in SEEDS:
        print(f"Seeding {ref.schema}.schema/{ref.table}")
        client.ensure_table(ref, key_columns=keys)
        path = parquet(df, tmp / f"{ref.schema}_{ref.table}.parquet")
        print(f"  -> {client.upload_data_file(ref, path)}")
        path.unlink()

    print()
    print("Verify in the mirrored DB SQL endpoint:")
    print("  SELECT * FROM youtube.videos;")
    print("  SELECT * FROM youtube.channels;")
    print("  SELECT * FROM skool.communities;")
    print("  SELECT * FROM skool.members;")


if __name__ == "__main__":
    main()
