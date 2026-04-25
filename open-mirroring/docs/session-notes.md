# Session Notes - Open Mirroring Feasibility

## 2026-04-20 - Kickoff and research phase

- Research completed across six decision questions. Findings documented in `research-plan.md` and `landing-zone-format.md`.
- Plan approved: four studies (setup+SP, format+schemas, dbt, CI/CD).
- Key surprise: **JSON not directly supported** by the landing zone. Producers must convert JSON -> Parquet before upload. Handled in Study-02.
- Key surprise: **mirroring does not auto-start after deployment**. Every environment needs a post-deploy "start mirroring" REST call. Handled in Study-04.
- Key confirmation: the existing `read_delta()` macro at `feasibility/duckdb-dbt/poc_local_final_clean/macros/read_delta.sql` already uses `delta_scan()` on a parameterized root - extending for a second root (mirror vs. lakehouse) is a one-line change.

## Open questions (to resolve during POC execution)

- Does `isUpsertDefaultRowMarker: true` combined with `LastUpdateTimeFileDetection` break incremental-update accuracy? (Study-02)
- Does the Mirrored Database SQL analytics endpoint work with dbt's `fabric` target out of the box, or do we need a DSN-style connection string? (Study-03)
- Does `fab` CLI support mirrored-database deployment, or do we need the REST API for CI? (Study-04)

## 2026-04-20 - Schema evolution guidance added

- Producer-facing walkthrough added to `landing-zone-format.md` -> "Schema evolution" section. Covers the `skool.members` case (add two nullable columns without downtime), the rollout sequence, backfill pattern, and the "don't drift existing column types" discipline.
- Summary copy in `research-plan.md` pointing at the walkthrough.

## 2026-04-20 - CI/CD design discussion

- User asked what gets deployed DEV -> TEST -> PROD via Fabric's deployment pipeline. Answer: only the item shell (`mirroring.json` + `.platform`). Tables, schemas, landing-zone files, and Delta data are all **per-environment** - they do not cross stages. PROD starts empty.
- Two-pipeline design agreed in principle:
  1. Infrastructure pipeline: Fabric Git + deployment pipeline promotes the `bronze_mirror` item shell; post-deploy hook calls `startMirroring` on the target.
  2. Producer pipeline(s): each producer (YouTube, Skool, Claude Routines, UDFs) is configured per-environment with its own `BRONZE_MIRROR_ID` + workspace, deployed independently.
- Bootstrap question left open: on a fresh PROD mirror, do we (a) accept it catches up naturally from next producer run, (b) run a mirror-init script to pre-create empty table folders with `_metadata.json`, or (c) run an explicit backfill producer. User to pick between these.

## 2026-04-20 - Studies 01, 02, 03 executed

### Studies 02 + 03 findings

- **Explicit pyarrow schema mandatory for producers** doing deletes or partial-row incrementals. First attempt of `poc_initial_vs_incremental.py` used pandas type inference; file 3 with `location: [None]` got inferred as integer -> mirror SchemaMergeFailure ("incoming type integer, existing type string"). Fix: drive all uploads through a `pa.schema([...])`. Noted as a project-wide lesson for any future producer code.
- **Drop-and-recreate recovery works**: deleting the landing-zone folder drops the mirror's table, re-uploading recreates it with fresh schema. ~90s catch-up.
- **Schemaless tables land under `/Tables/dbo/`** (the `defaultSchema` from `mirroring.json`). Consumers building ABFSS paths must use `dbo` as the schema arg. Recommendation for our project: always use an explicit `<source>.schema/` folder when producing - no schemaless landing zones.
- **DuckDB delta_scan over mirror works with SP auth** - proven via `study-03-dbt-integration/poc_delta_scan_mirror.py`. That's the exact pattern the extended `read_delta()` macro generates, so dbt integration is effectively proven without running dbt itself. Full `dbt compile --target fabric` deferred because the fabric target runs in a Fabric notebook.
- **`__rowMarker__` semantics verified end-to-end**: insert (no marker), update (1), delete (2), upsert (4), and key-change (delete+insert in one file) all produce the correct final state.

## 2026-04-20 - Study-01 executed

- Claude initially created a mirror in **PROD** by defaulting to `FABRIC_WORKSPACE_ID` env var, which is the PROD workspace. The dev pattern in this repo is `FABRIC_DEV_WORKSPACE_ID`. `config.py` now pins to the DEV variant. PROD mirror (`706b5515-adf9-4e8e-99d9-c06e1fa2556d` in workspace `e7da9a20-3fee-4a09-9ae4-83bf9b7466a4`) is an orphan - should be deleted from the PROD workspace portal.
- `startMirroring` returned `MirroringDefinitionMissing` on the bare item. User recreated via the portal in DEV, which filled in the definition correctly. For REST creates, the body needs a proper `mirroring.json` with `source.type: "GenericMirror"` - will fix `poc_create_mirror.py` next.
- DEV mirror: workspace `d9b72fad-f41f-4924-a4ef-ccc2be71344c`, item `894a75c6-0cde-490c-9631-c55eb90bf7fc`.
- Smoke upload (3 rows, 1 parquet file) replicated in ~45 seconds from upload to `Replicating` status with full metrics.
