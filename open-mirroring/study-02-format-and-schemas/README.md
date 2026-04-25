# Study-02: Format and Multi-Schema Layout

Answers decision questions **Q3 (data structure)** and **Q4 (one mirror vs. many)**.

## Goal

1. Prove the full data format works for realistic JSON payloads from YouTube and Skool.
2. Prove all four `__rowMarker__` values behave as documented (insert, update, delete, upsert, key change).
3. Prove a single mirrored DB cleanly houses multiple sources via `<schema>.schema/` folder naming.

## Scripts

| Script | Purpose |
|--------|---------|
| `poc_json_to_parquet.py` | YouTube + Skool JSON -> flattened DataFrame -> parquet with `__rowMarker__=0` -> upload to separate schemas. |
| `poc_initial_vs_incremental.py` | Exercises initial load, update, delete, upsert, and key-column change on `test.schema/row_marker_demo`. |
| `poc_multi_schema.py` | Seeds four tables across `youtube.schema` and `skool.schema` in one mirror. |

## Pre-reqs

- Study-01 complete. `BRONZE_MIRROR_ID` set. Mirroring is running.

## Run order

```bash
python feasibility/open-mirroring/study-02-format-and-schemas/poc_json_to_parquet.py
python feasibility/open-mirroring/study-02-format-and-schemas/poc_initial_vs_incremental.py
python feasibility/open-mirroring/study-02-format-and-schemas/poc_multi_schema.py
```

After each run, query the mirrored DB's SQL analytics endpoint to confirm state.

## Expected results

**After `poc_json_to_parquet.py`:**
- `youtube.videos` has 2 rows (abc123, def456)
- `skool.members` has 2 rows (m001, m002)

**After `poc_initial_vs_incremental.py`, final state of `test.row_marker_demo`:**
| employee_id | location |
|-------------|----------|
| E0001_NEW   | Bellevue |
| E0003       | Kirkland |
| E0004       | Seattle  |

(E0001 and E0002 should NOT be present.)

**After `poc_multi_schema.py`:**
- `youtube.videos`, `youtube.channels`, `skool.communities`, `skool.members` all visible as separate SQL-queryable tables under one mirrored DB item.

## Verdict (2026-04-20)

- [x] **JSON -> parquet -> landed**: PASS. `youtube.videos` 2 rows/230 bytes, `skool.members` 2 rows/104 bytes.
- [x] **INSERT (no marker) on initial load**: PASS. Confirmed by Study-03 delta-scan.
- [x] **UPDATE (marker=1) with full row**: PASS. E0001 Redmond -> Bellevue applied.
- [x] **DELETE (marker=2) with keys only**: PASS. E0002 removed.
- [x] **UPSERT (marker=4)**: PASS. E0003 updated to Kirkland, E0004 inserted.
- [x] **Key column change via DELETE+INSERT in one file**: PASS. E0001 -> E0001_NEW.
- [x] **Multi-schema namespacing works in one mirror**: PASS. `youtube.schema/`, `skool.schema/`, `test.schema/` surface as distinct schemas.
- [x] Final state of `test.row_marker_demo` confirmed via delta-scan: `{E0001_NEW:Bellevue, E0003:Kirkland, E0004:Seattle}`.

### Key findings / gotchas

- **Explicit pyarrow schema is mandatory for producers doing deletes or partial rows.** The first run of `poc_initial_vs_incremental.py` used `pd.DataFrame(...)` and let pandas/pyarrow infer types. File 3 (`location: [None]` as the only value) was inferred as integer, triggering `SchemaMergeFailure` in the mirror ("Type mismatch for column 'location'. Incoming type: 'integer', existing type: 'string'"). The fix: declare a `pa.schema([...])` once and drive all uploads through it. The POC now does this.
- **Recovery from schema errors**: deleting the landing-zone folder drops the table (per docs). Re-uploading into the recreated folder starts fresh with the new schema. Took ~90s between drop and catch-up.
- **Schemaless tables** (e.g. `smoke_test` uploaded with no `<x>.schema/` folder) land under `/Tables/dbo/` in the mirror's Delta tree - `dbo` is the `defaultSchema` from `mirroring.json`. This matters for any consumer that builds the ABFSS path: use `dbo` as the schema arg when reading schemaless landing-zone tables.
- **Replication latency**: mirror discovers new table folders in ~15-20s after the first file lands. Processing 5 sequential files took ~90s.
- **`processedRows` is cumulative** over processed files, not current-state row count. Do not use it for row-count verification - use delta-scan or the SQL endpoint.
- **`poc_multi_schema.py` was NOT run** - it overlaps with `poc_json_to_parquet.py` (same `youtube.schema/videos` and `skool.schema/members` folders, different column schemas) and would have caused another `SchemaMergeFailure`. Multi-schema layout is already proven by the three schemas created above. `poc_multi_schema.py` is kept as a standalone demo for a clean mirror.

## Notes

- All scripts write `__rowMarker__` as the **last column**, as required.
- Schema names in code use dots in SQL (`youtube.videos`) but folder names use `.schema` suffix (`youtube.schema/videos`).
- Keep `_metadata.json` simple - just `keyColumns`. `LastUpdateTimeFileDetection` and `isUpsertDefaultRowMarker` are optional; try them in a follow-up if the sequential filename approach proves fragile for our concurrent producers.
