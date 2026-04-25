# Landing Zone Format - Quick Reference for Producers

Read this before writing a producer that pushes into the bronze mirror.

## Path shape

```
https://onelake.dfs.fabric.microsoft.com/<workspaceId>/<mirroredDbId>/Files/LandingZone/[<schema>.schema/]<table>/<file>
```

- `<workspaceId>` - the Fabric workspace GUID (e.g. `Fabric_BMAD_DEV`).
- `<mirroredDbId>` - the Mirrored Database item GUID. Different per environment.
- `<schema>.schema/` - optional. Use for multi-source namespacing (e.g. `youtube.schema/`, `skool.schema/`).
- `<table>/` - one folder per table. Creating the folder creates the table.
- `<file>` - `_metadata.json`, or a 20-digit sequential data file.

## Minimum producer checklist

1. Acquire a token with `ClientSecretCredential`, scope `https://storage.azure.com/.default`.
2. Open a `DataLakeServiceClient` at `https://onelake.dfs.fabric.microsoft.com`.
3. Ensure `_metadata.json` exists in the table folder:
   ```json
   { "keyColumns": ["id"] }
   ```
4. Convert your payload (probably JSON) to Parquet. If you want update/delete semantics, add `__rowMarker__` as the **last column** (0=insert, 1=update, 2=delete, 4=upsert).
5. Find the next sequential file number by listing the folder and taking `max(file)+1`. Format as 20 digits: `f"{n:020d}.parquet"`.
6. Upload the parquet file.
7. Within minutes, the row shows up in the Mirrored Database's SQL analytics endpoint.

## Alternative: no sequential-filename bookkeeping

Add to `_metadata.json`:
```json
{
  "keyColumns": ["id"],
  "fileDetectionStrategy": "LastUpdateTimeFileDetection",
  "isUpsertDefaultRowMarker": true
}
```
Mirroring reads files in last-modified order; no counter to maintain. Rows are upserted by default.

## Writing a row update

Updates need the **full row** (not just changed columns). Example (Parquet schema `id, title, views, __rowMarker__`):

| id   | title        | views | `__rowMarker__` |
|------|--------------|-------|---------|
| v001 | Old title    | 100   | 0       |
| v002 | Another      | 50    | 0       |
| v001 | NEW title    | 120   | 1       |

## Writing a delete

Only key columns are needed in a delete row:

| id   | title | views | `__rowMarker__` |
|------|-------|-------|---------|
| v001 |       |       | 2       |

## Key column change

Represent as delete-of-old + insert-of-new in the same file:

| id   | title     | views | `__rowMarker__` |
|------|-----------|-------|---------|
| v001 |           |       | 2       |
| v002 | New title | 120   | 0       |

## Things you do NOT do

- Do NOT upload JSON directly. Convert to parquet first.
- Do NOT change a column's data type in place. Drop the table folder and recreate.
- Do NOT assume processed files stay put. Mirroring moves them to `_ProcessedFiles/`, then `_FilesReadyToDelete/` (auto-purged after 7 days).
- Do NOT skip `_metadata.json`. Without it, updates and deletes silently don't work.

## File retention

The landing zone is **transient**, not a durable data store. Two separate retentions to know:

### Landing zone files (the parquet files you upload)

| Stage | Location | Retention |
|---|---|---|
| Just uploaded | `LandingZone/<schema>.schema/<table>/00000000000000000N.parquet` | Until mirror processes it (seconds-minutes) |
| Processed | `LandingZone/.../_ProcessedFiles/` then `_FilesReadyToDelete/` | **7 days**, then auto-purged by Fabric |
| Latest file | Stays in place | Kept so producers can find the next sequence number |

Observed in Study-02: `00000000000000000001.parquet` moved into `_FilesReadyToDelete/` after ingestion, alongside a `_FilesReadyToDeleteInfo.json`.

### Delta tables (your real data)

Under `Tables/<schema>/<table>/` - standard Delta Lake storage:

- Mirror auto-runs `OPTIMIZE` and `VACUUM`.
- Delta time-travel window is the default (~7 days) unless overridden.
- Row data itself persists indefinitely; only superseded parquet files and old log entries get vacuumed.

### Practical implications

- **Don't treat the landing zone as durable.** If you need the raw payloads later (audit, replay into a different mirror), copy files to your own OneLake/ADLS folder on upload. The mirror will purge them within 7 days.
- **For high-volume producers**, proactively delete `_ProcessedFiles/` and `_FilesReadyToDelete/` folders after confirming replication - cuts storage cost before the 7-day grace period. Mirror tolerates this. (The Microsoft sample shows the pattern as `CleanUpTableAsync`.)
- **For recovery**, use Delta time-travel on the mirrored table (`VERSION AS OF ...`), not landing-zone files. The landing zone is gone by then.
- **Producer idempotency**: a re-run that tries to write the same file number won't collide (the original was moved/deleted) but also won't re-replicate. If you need replay, bump to the next sequence number.

## Schema evolution

**Adding a nullable column is zero-downtime.** Update the producer's `pa.schema([...])`, deploy, write the next file. Mirror unions the Delta schema automatically within ~30s. Old rows get NULL for the new column; new rows get the populated value. No table drop, no data loss, no `bronze_mirror` infra change.

### Example: adding `membership_start_date` and `membership_end_date` to `skool.members`

Before:
```python
SCHEMA = pa.schema([
    ("member_id", pa.string()),
    ("community", pa.string()),
    ("joined_at", pa.date32()),
    ("posts", pa.int32()),
    ("__rowMarker__", pa.int32()),
])
```

After (insert BEFORE `__rowMarker__`; existing columns and types unchanged):
```python
SCHEMA = pa.schema([
    ("member_id", pa.string()),
    ("community", pa.string()),
    ("joined_at", pa.date32()),
    ("posts", pa.int32()),
    ("membership_start_date", pa.date32()),  # NEW, nullable
    ("membership_end_date", pa.date32()),    # NEW, nullable
    ("__rowMarker__", pa.int32()),
])
```

Rollout:
1. Merge producer change to DEV branch, deploy to DEV.
2. Producer writes its next sequential file (e.g. `00000000000000000523.parquet`) with 7 columns.
3. Wait ~30s. `delta_scan` confirms two new columns; old rows show NULL; new rows populated.
4. Promote producer to PROD. PROD `skool.members` gains the columns on the next file there.

### What you must NOT do when evolving schema

| Don't | Why |
|---|---|
| Change the type of an existing column (e.g. `posts` int -> string) | Mirror throws `SchemaMergeFailure` and stops replicating that table. Only remedy is folder drop. |
| Rename a column in place | Treated as: old column dropped, new column added. Old rows lose the value. Use a silver-layer view if you need a rename without data rewrite. |
| Put new columns after `__rowMarker__` | `__rowMarker__` must remain the last column. |
| Drop the table folder just to add columns | Loses your historical rows. Drop-and-recreate is for TYPE changes or genuine column removal, not additions. |
| Declare new columns NOT NULL | Existing rows can't satisfy it. Keep new columns nullable. |

### Removing a column

Mirror keeps unioned columns forever, showing NULL for new rows that don't include them. To truly drop a column you have to drop the folder and recreate it - which means losing all historical data. Practical answer: stop writing the column, accept NULLs on new rows, and project it out in a silver-layer view.

### Backfilling new columns on historical rows

If you have the values, send a follow-up file with `__rowMarker__=1` (update) for each historical row, including the full row data plus the new column values:

```
{member_id, community, joined_at, posts, membership_start_date, membership_end_date, __rowMarker__=1}
```

Key matches -> row updated. Thousands of rows fit in one file; millions, batch across multiple sequential files.

### The subtle gotcha (learned in Study-02)

Your existing columns must keep their **exact** pyarrow types across releases. If a producer refactor accidentally changes `joined_at` from `date32` to `timestamp[us]`, or `posts` from `int32` to `int64`, the next file triggers `SchemaMergeFailure` and replication stops. This is why the producer's `pa.schema([...])` is checked into code and reviewed in PR - pandas type inference must NOT drive it.
