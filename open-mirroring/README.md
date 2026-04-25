# Feasibility Study 03 — Open Mirroring

> Please note: the code in this repo is for research purposes only, and is not validated/ tested for Production use cases. Use at your own risk. 

Evaluating Microsoft Fabric's **Open Mirroring** (Mirrored Database in "open" mode) as the raw/bronze landing zone for this project. Producers — YouTube REST pulls, Skool scrapers, User Data Functions, Claude Routines — push parquet files into a single mirrored item; the mirror exposes them as queryable Delta tables that the existing dbt pipeline can consume.

The study answers six decision questions across four POC streams, each with a `PASS / FAIL / PASS-WITH-CAVEATS` verdict.

## Folder layout

```
open-mirroring/
├── README.md                       (this file)
├── docs/                           Research, protocol reference, session log
├── clients/                        Reusable Python helpers (auth, REST, landing zone)
├── study-01-setup-and-ingest/      Q1 setup + Q2 service-principal ingest
├── study-02-format-and-schemas/    Q3 data structure + Q4 one-vs-many mirrors
├── study-03-dbt-integration/       Q5 dbt / DuckDB delta_scan integration
└── study-04-cicd/                  Q6 Git integration + deployment pipeline
```

## docs/

Background and protocol material, written before the POCs ran.

| File | Purpose |
|------|---------|
| `research-plan.md` | The six decision questions, the settled answers from research, references. The canonical entry point. |
| `landing-zone-format.md` | Producer-facing quick reference: path shape, `_metadata.json`, `__rowMarker__` semantics, schema evolution rules, retention. Read this before writing a producer. |
| `session-notes.md` | Chronological log of decisions, surprises, and per-study findings. |

## clients/

Vendored Python helpers used by every POC. Thin wrappers — the landing-zone protocol is the source of truth.

| File | Purpose |
|------|---------|
| `config.py` | Loads `.env`, exposes `FABRIC_WORKSPACE_ID`, `BRONZE_MIRROR_ID`, and helpers `landing_zone_url()` / `tables_abfss_root()`. Pinned to the **DEV** workspace var to avoid PROD accidents. |
| `auth.py` | Service-principal token acquisition for both the Fabric REST API and the OneLake ADLS Gen2 endpoint. |
| `mirror_api.py` | REST helpers for the Mirrored Database lifecycle: create, get, start, stop, status, table status, `wait_for_running`. Includes the `GenericMirror` definition needed for a startable open mirror. |
| `openmirroring.py` | `MirrorClient` for landing-zone uploads — `ensure_table`, `next_data_filename`, `upload_data_file`. |

## study-01-setup-and-ingest/  → Q1, Q2

Prove an SP-only producer can create a mirror, drop a parquet, and see it replicated.

- `poc_sp_upload_smoke.py` — three-row smoke upload to `LandingZone/smoke_test/`.
- **Verdict: PASS.** Replication completed in ~45 s; well inside the 2–5 min documented bound. Required tenant settings and SP Contributor role on the workspace are documented in the study README.

## study-02-format-and-schemas/  → Q3, Q4

Prove the data format works for realistic JSON payloads, all four `__rowMarker__` operations behave as documented, and one mirror cleanly hosts multiple sources via `<schema>.schema/` folders.

- `poc_json_to_parquet.py` — YouTube + Skool JSON → flattened parquet → upload.
- `poc_initial_vs_incremental.py` — insert / update / delete / upsert / key-change in one mirror.
- `poc_multi_schema.py` — four tables across `youtube.schema/` and `skool.schema/`.
- **Verdict: PASS.** Key gotcha: producers **must** declare an explicit `pa.schema([...])`; pandas type inference triggered `SchemaMergeFailure` on a column that landed all-`None`.

## study-03-dbt-integration/  → Q5

Prove dbt can source from the mirror with a one-line change to the existing `read_delta()` macro.

- `read_delta.sql` — extended macro with a `source_root='lakehouse'|'mirror'` argument.
- `stg_youtube_videos.sql` — drop-in staging model reading from the mirror.
- `poc_delta_scan_mirror.py` — DuckDB `delta_scan()` over the mirror via SP secret (the exact pattern the macro generates on the `fabric` target).
- **Verdict: PASS for the critical path** (delta-scan over mirror with SP auth). Macro drop-in and full `dbt build --target fabric` deferred to in-Fabric execution.

## study-04-cicd/  → Q6

Prove the mirror fits the existing `Fabric_BMAD_DEV` → `Fabric_BMAD_PROD` flow.

- `poc_start_mirroring.py` — post-deploy hook calling `startMirroring`, since mirroring **does not auto-start** after deployment.
- `deploy-mirror-workflow.yml.example` — illustrative GitHub Actions sketch; not yet wired up.
- **Verdict: partial.** Claude-side scripts verified; Git integration commit, deployment pipeline run, and PROD post-deploy start are pending portal/user action.

## Running the studies

Studies are independent but assume the prior one for context. Activate the project root `.venv`, then run scripts from the repo root, e.g.:

```bash
python feasibility/open-mirroring/study-01-setup-and-ingest/poc_sp_upload_smoke.py
```

Each study folder's `README.md` lists prerequisites, run order, and expected results.

## Aggregate verdict (in progress)

| Study | Question | Verdict |
|-------|----------|---------|
| 01 | Setup + SP ingest | PASS |
| 02 | Format + multi-schema | PASS (with explicit-pyarrow-schema discipline) |
| 03 | dbt integration | PASS for critical path; macro/dbt-run deferred |
| 04 | CI/CD | Partial — awaiting Git integration + deployment-pipeline run |

The aggregate recommendation will be added to `docs/research-plan.md` once Study-04 completes.
