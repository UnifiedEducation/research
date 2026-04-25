"""Study-02 / Q3: JSON -> Parquet conversion with __rowMarker__.

The landing zone does not accept JSON directly. Producers must convert.
This POC takes a YouTube-like JSON payload and a Skool-like JSON payload,
flattens each, adds __rowMarker__ as the FINAL column, writes parquet,
uploads. Proves the producer side of the pipeline.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clients"))

from config import BRONZE_MIRROR_ID
from openmirroring import MirrorClient, TableRef


YOUTUBE_SAMPLE = [
    {
        "id": "abc123",
        "snippet": {
            "title": "First video",
            "channelId": "UC_channel_1",
            "publishedAt": "2026-04-01T10:00:00Z",
        },
        "statistics": {"viewCount": "100", "likeCount": "10"},
    },
    {
        "id": "def456",
        "snippet": {
            "title": "Second video",
            "channelId": "UC_channel_1",
            "publishedAt": "2026-04-02T11:00:00Z",
        },
        "statistics": {"viewCount": "250", "likeCount": "30"},
    },
]


SKOOL_SAMPLE = [
    {"member_id": "m001", "community": "creators", "joined_at": "2026-03-01", "posts": 5},
    {"member_id": "m002", "community": "creators", "joined_at": "2026-03-15", "posts": 12},
]


def flatten_youtube(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "video_id": r["id"],
            "title": r["snippet"]["title"],
            "channel_id": r["snippet"]["channelId"],
            "published_at": r["snippet"]["publishedAt"],
            "view_count": int(r["statistics"]["viewCount"]),
            "like_count": int(r["statistics"]["likeCount"]),
        }
        for r in rows
    ])


def flatten_skool(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def write_parquet_with_row_marker(df: pd.DataFrame, out: Path, marker: int = 0) -> Path:
    df = df.copy()
    df["__rowMarker__"] = marker
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out)
    return out


def main() -> None:
    if not BRONZE_MIRROR_ID:
        raise SystemExit("BRONZE_MIRROR_ID not set")

    client = MirrorClient(mirror_id=BRONZE_MIRROR_ID)
    tmp_dir = Path(__file__).parent / "_tmp"
    tmp_dir.mkdir(exist_ok=True)

    yt_table = TableRef(schema="youtube", table="videos")
    sk_table = TableRef(schema="skool", table="members")

    client.ensure_table(yt_table, key_columns=["video_id"])
    client.ensure_table(sk_table, key_columns=["member_id"])

    yt_df = flatten_youtube(YOUTUBE_SAMPLE)
    sk_df = flatten_skool(SKOOL_SAMPLE)

    yt_file = write_parquet_with_row_marker(yt_df, tmp_dir / "youtube_videos.parquet", marker=0)
    sk_file = write_parquet_with_row_marker(sk_df, tmp_dir / "skool_members.parquet", marker=0)

    print(f"Uploading {yt_file.name} -> {yt_table.schema}.schema/{yt_table.table}/")
    print(client.upload_data_file(yt_table, yt_file))
    print(f"Uploading {sk_file.name} -> {sk_table.schema}.schema/{sk_table.table}/")
    print(client.upload_data_file(sk_table, sk_file))

    yt_file.unlink()
    sk_file.unlink()

    print()
    print("Also emitting the intermediate JSON for reference:")
    print(json.dumps(YOUTUBE_SAMPLE, indent=2)[:200] + "...")


if __name__ == "__main__":
    main()
