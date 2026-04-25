# Study-01: Setup and Service-Principal Ingest

Answers decision questions **Q1 (setup)** and **Q2 (service principal)**.

## Goal

Prove that a service-principal-only producer can:
1. Create a Mirrored Database in a Fabric workspace
2. Drop a parquet file into the landing zone
3. See it replicated as a queryable Delta table

...using only the SP credentials already present in the project `.env`.

## Scripts

| Script | Purpose |
|--------|---------|
| `poc_sp_upload_smoke.py` | Writes a tiny parquet locally, uploads to `LandingZone/smoke_test/`, polls replication status. |

## Prerequisites

1. **Tenant admin** has enabled both settings in Fabric Admin portal -> Tenant settings, each scoped to a security group that contains our SP (not "entire org"):
   - **Developer settings -> "Service principals can access Fabric APIs"** (historical name: "Allow service principals to use Power BI APIs"). Lets the SP call the Fabric REST API.
   - **OneLake -> "Users can access data stored in OneLake with apps external to Fabric"** (a.k.a. "Allow apps running outside of Fabric to access data via OneLake"). Lets our Python producers talk to `onelake.dfs.fabric.microsoft.com` via the ADLS Gen2 SDK.
   Neither setting grants access on its own - they just allow RBAC to be given.
2. The SP is assigned **Contributor** role on `FABRIC_WORKSPACE_ID` (Workspace access -> Manage access -> Add).
3. Project `.venv` activated, `pip install -r requirements.txt` run.

## Run order

```bash
# Activate the project-root .venv first
python feasibility/open-mirroring/study-01-setup-and-ingest/poc_create_mirror.py
# Paste BRONZE_MIRROR_ID into .env
# In the Fabric portal, open the item and click "Start mirroring"
python feasibility/open-mirroring/study-01-setup-and-ingest/poc_sp_upload_smoke.py
```

## Expected result

- In the portal, the mirrored DB's landing-zone URL is visible.
- After `poc_sp_upload_smoke.py`, the Explorer shows `smoke_test` under Tables; SQL endpoint returns 3 rows.
- Within 2-5 min, the uploaded parquet is moved to `_ProcessedFiles/`.

## Verdict (2026-04-20)

- [x] SP upload to landing zone: **PASS**. Uploaded `00000000000000000001.parquet` to `smoke_test/` folder with 3 rows.
- [x] Replication produced queryable Delta table: **PASS**. `getTablesMirroringStatus` showed status `Replicating`, `processedRows: 3`, `processedBytes: 170`.
- [x] Replication latency: ~45 seconds from upload to `Replicating` status with metrics. Well inside the "2-5 min" doc bound.
- [x] Tenant/workspace config needed:
  - Both tenant settings enabled (Developer + OneLake), scoped to SP security group.
  - SP assigned Contributor on the DEV workspace.


## Notes

- If the `start mirroring` button isn't clickable in the portal, the tenant settings probably aren't applied. The SP can also call `mirror_api.start_mirroring(...)`.
