# Open Mirroring as Raw Landing Zone - Research Plan

## Why this study exists

The project needs a raw/bronze layer in Fabric that accepts files from diverse, low-trust producers:
- YouTube REST API pulls (JSON responses)
- Skool scraping agents (JSON or CSV)
- User Data Functions and notebooks (arbitrary formats)
- Claude Routines running on schedules

Requirements for the landing zone:
- Service-principal authentication (no user sign-in)
- Append-style writes from independent producers
- Automatic conversion into a queryable table format (Delta)
- Integrates with the existing dbt + DuckDB workflow at `feasibility/duckdb-dbt/`
- Fits the existing `Fabric_BMAD_DEV` -> `Fabric_BMAD_PROD` deployment path

Open Mirroring (Fabric Mirrored Database in "open" mode) is evaluated against these needs.

## The six decision questions

1. What are the setup steps?
2. Can data be sent via a Service Principal?
3. What structure do the data need to be in?
4. One mirror per source, or one shared mirror subdivided by schema?
5. How does the mirror integrate with the dbt workflow?
6. How does the mirror fit the existing version-control / deployment process?

## Settled answers (from research, not yet from this study's POCs)

### 1. Setup

- Create a **Mirrored Database** item in a workspace.
  - Portal: Create -> Mirrored Database card -> name -> Create.
  - REST: `POST https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/mirroredDatabases` with a minimal `mirroring.json` (open mode, no source connection).
- On the item's Home page, copy the **Landing Zone URL**:
  `https://onelake.dfs.fabric.microsoft.com/<workspaceId>/<mirroredDbId>/Files/LandingZone/`
- Press **Start mirroring** (or call the equivalent REST API). Mirroring does **not** start on its own after an initial deployment.
- Prereqs: active Fabric capacity. Paused capacity stops replication.

### 2. Service Principal

Yes - supported, and is the intended mode for programmatic producers.

- Auth: `azure.identity.ClientSecretCredential` over ADLS Gen2 endpoints.
- Scope for the `DataLakeServiceClient`: `https://storage.azure.com/.default` (OneLake honours it).
- Tenant settings (admin-owned, both under Fabric Admin portal -> Tenant settings, each scoped to a security group that contains the SP):
  - **Developer settings -> "Service principals can access Fabric APIs"** (historical name: "Allow service principals to use Power BI APIs").
  - **OneLake -> "Users can access data stored in OneLake with apps external to Fabric"** (a.k.a. "Allow apps running outside of Fabric to access data via OneLake").
  Neither grants access on its own - they just permit RBAC to be granted.
- Item/workspace RBAC: SP needs **Contributor** on the workspace (or Read/Write on the Mirrored Database item).
- Official Python SDK: `microsoft/fabric-toolbox/tools/OpenMirroringPythonSDK` (`openmirroring_operations.py`, a single module, not on PyPI - will be vendored into `feasibility/open-mirroring/clients/`).

### 3. Data structure

Per-table folder in the landing zone contains:

```
LandingZone/
  [<schemaname>.schema/]
    <TableName>/
      _metadata.json
      00000000000000000001.parquet
      00000000000000000002.parquet
      ...
```

`_metadata.json` (minimal):
```json
{ "keyColumns": ["id"] }
```

Optional extras:
```json
{
  "keyColumns": ["id"],
  "fileDetectionStrategy": "LastUpdateTimeFileDetection",
  "isUpsertDefaultRowMarker": true
}
```
`LastUpdateTimeFileDetection` removes the sequential-filename requirement (files read by timestamp). `isUpsertDefaultRowMarker: true` makes the default operation an upsert when `__rowMarker__` is absent. Attractive for our append-style producers.

**Supported data file formats: Parquet (preferred), CSV, TSV, PSV. JSON is NOT supported directly** - YouTube/Skool JSON responses must be converted to Parquet before upload (pyarrow / pandas). Compression: uncompressed, Snappy, GZIP, ZSTD.

**Filename rules** (when not using `LastUpdateTimeFileDetection`):
- 20 digits, zero-padded, sequential: `00000000000000000001.parquet` -> `00000000000000000002.parquet` -> ...
- Continuous numbers. Mirroring moves processed files to `_ProcessedFiles/` and `_FilesReadyToDelete/` (auto-deleted after 7 days).

**`__rowMarker__` column** (must be the **final** column):

| Value | Meaning | If row missing in dest | If row exists |
|-------|---------|-----------------------|---------------|
| 0 | Insert | Insert | Insert (no dedup check) |
| 1 | Update | Insert (no key validation) | Update by key |
| 2 | Delete | No-op | Delete by key |
| 4 | Upsert | Insert | Update by key |

- **Initial load**: `__rowMarker__` is optional. Whole file treated as INSERT.
- **Incremental**: `__rowMarker__` required. Updates must include **all columns** (full row data). Deletes only need key columns.
- **Key column change**: represent as DELETE on old key + INSERT with new key in the same change batch.
- **Row order within a file** matters - it's the applied transaction order. **File order** matters too (sequential numbers, or timestamps).

**Schema evolution**:
- Adding a column: add it to the next file. Mirror adds the column to the Delta table; old rows get NULL. Zero-downtime.
- Dropping a column: stop sending it. Old rows keep their values; new rows get NULL. To actually remove it, drop and recreate the folder (destroys historical data).
- Changing a column type: drop and recreate the folder - cannot change type in place. Replication stops with `SchemaMergeFailure` on any type drift.
- Renaming a column or table: drop and recreate the folder with new data.
- **Full producer-facing walkthrough** (with code example for adding two nullable columns, rollout sequence, backfill, and the PR-review discipline needed to prevent type drift) lives in `landing-zone-format.md` under "Schema evolution".

### 4. One mirror vs. many

**One mirror** is recommended, subdivided by schema. The landing zone supports a schema level via `<schemaname>.schema/` folders:

```
LandingZone/
  youtube.schema/
    videos/
      _metadata.json
      00000000000000000001.parquet
    channels/
      ...
  skool.schema/
    communities/
      ...
    members/
      ...
```

Each producer owns a schema. Table governance and SQL analytics namespacing mirror this layout. Single-item CI/CD diff surface.

### 5. dbt integration

The mirrored database exposes Delta tables at:
```
abfss://<workspaceId>@onelake.dfs.fabric.microsoft.com/<mirroredDbId>/Tables/[<schema>/]<table>
```

The existing `feasibility/duckdb-dbt/poc_local_final_clean/macros/read_delta.sql` uses `delta_scan('{ROOT_PATH}/Tables/{schema}/{table}')`. Extending it to accept a `source_root` argument is a one-line change - no new adapter or dbt feature needed.

See `study-03-dbt-integration/` for the concrete macro change.

### 6. CI/CD

Fully supported in both Git integration and Fabric deployment pipelines.

- **Git integration**: commits `{displayName}.MirroredDatabase/` folder with:
  - `mirroring.json` - item definition (table list, options; is source-less for open mirroring)
  - `.platform` - system file, stable logical ID across environments
  Child items (SQL analytics endpoint, views) are **not** tracked.
- **Deployment pipelines**: Fabric's built-in DEV/TEST/PROD stages copy the item across. Our existing `Fabric_BMAD_DEV` -> `Fabric_BMAD_PROD` pair works.
- **Gotchas**:
  - Mirroring does **not auto-start** after deployment. Need a post-deploy hook calling the REST API. Where that hook lives (GitHub Actions, a Fabric notebook, or manual run) is left open for Study-04 - the mirror deployment path will likely be distinct from the existing dbt GitHub Actions.
  - Landing zone URL differs per stage (different `mirroredDbId`). Producer configs must be re-pointed per environment - no way to share a URL across stages.
  - New-table onboarding: producer just drops a new folder. The `mirroring.json` diff (if using the "mirror all" option) may be empty; table additions are runtime, not definition-time.

## Verdict format

Each study's README ends with a clear `PASS / FAIL / PASS-WITH-CAVEATS` verdict. After all four studies, the top-level `docs/research-plan.md` will be updated with the aggregate verdict and a recommendation for production.

## References

- [Open Mirroring tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/open-mirroring-tutorial)
- [Landing zone format spec](https://learn.microsoft.com/en-us/fabric/mirroring/open-mirroring-landing-zone-format)
- [Use Blob and ADLS APIs to mirror data into OneLake](https://learn.microsoft.com/en-us/fabric/onelake/onelake-apis-in-action)
- [CI/CD for mirrored databases](https://learn.microsoft.com/en-us/fabric/mirroring/mirrored-database-cicd)
- [Mirroring REST API](https://learn.microsoft.com/en-us/fabric/mirroring/mirrored-database-rest-api)
- [Open Mirroring Python SDK (fabric-toolbox)](https://github.com/microsoft/fabric-toolbox/tree/main/tools/OpenMirroringPythonSDK)
- [Sample app (.NET) - cmaneu/fabric-open-mirroring-sample](https://github.com/cmaneu/fabric-open-mirroring-sample)
