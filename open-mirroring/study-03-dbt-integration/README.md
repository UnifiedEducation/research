# Study-03: dbt Integration

Answers decision question **Q5 (how does the mirror integrate with dbt?)**.

## Goal

Prove dbt staging models can source from the Mirrored Database's Delta tables with a **one-line change** to the existing `read_delta()` macro.

## The change

The current macro at `feasibility/duckdb-dbt/poc_local_final_clean/macros/read_delta.sql`:

```sql
{% macro read_delta(schema_name, table_name) %}
  {% if target.name == 'local' %}
    {{ source(schema_name, table_name) }}
  {% else %}
    delta_scan('{{ env_var("ROOT_PATH") }}/Tables/{{ schema_name }}/{{ table_name }}')
  {% endif %}
{% endmacro %}
```

Proposed replacement (`read_delta.sql` in this folder):

```sql
{% macro read_delta(schema_name, table_name, source_root='lakehouse') %}
  {% if target.name == 'local' %}
    {{ source(schema_name, table_name) }}
  {% else %}
    {% if source_root == 'mirror' %}
      {% set root = env_var('MIRROR_ROOT_PATH') %}
    {% else %}
      {% set root = env_var('ROOT_PATH') %}
    {% endif %}
    delta_scan('{{ root }}/Tables/{{ schema_name }}/{{ table_name }}')
  {% endif %}
{% endmacro %}
```

Call sites choose the root:
```sql
-- reads from lakehouse (default, unchanged behaviour)
select * from {{ read_delta('raw', 'raw_film_catalog') }}

-- reads from the open mirror
select * from {{ read_delta('youtube', 'videos', source_root='mirror') }}
```

## Environment additions

Add to the `fabric` profile's environment (Fabric notebook env, `.env`, or deploy script):

```
MIRROR_ROOT_PATH=abfss://<workspaceId>@onelake.dfs.fabric.microsoft.com/<mirroredDbId>
```

The clients helper `tables_abfss_root()` in `feasibility/open-mirroring/clients/config.py` computes this from `BRONZE_MIRROR_ID` + `FABRIC_WORKSPACE_ID` - use it to populate the env variable during deployment.

## Sample staging model

`stg_youtube_videos.sql` in this folder is a drop-in example that reads the `youtube.videos` table seeded by Study-02 and casts types. Copy into the dbt project's `models/staging/` directory.

## Verification

1. Copy `read_delta.sql` into `feasibility/duckdb-dbt/poc_local_final_clean/macros/` (replacing the existing file).
2. Copy `stg_youtube_videos.sql` into `feasibility/duckdb-dbt/poc_local_final_clean/models/staging/`.
3. Set `MIRROR_ROOT_PATH` in the Fabric notebook environment.
4. Run `dbt build --target fabric --select stg_youtube_videos`.
5. Confirm the resulting view returns the rows seeded by Study-02's `poc_json_to_parquet.py`.

## Decision: staging in the same dbt project, or a new one?

Recommendation: **same project**, different model subfolder (`models/staging/bronze_mirror/`). Reasons:

- One project = one deployment pipeline = one set of Fabric notebooks, consistent with the current CI setup.
- The `read_delta()` macro handles the root difference cleanly - no code fork needed.
- Schema separation (raw vs. youtube vs. skool) is already supported by the `generate_schema_name` macro override.

If later the mirror consumers diverge significantly from the AEMO dataset the current project was built around, split then - not now.

## Verdict (2026-04-20)

The critical question - "can DuckDB's `delta_scan()` read the mirror's Delta tables via ABFSS with an SP secret?" - is answered **PASS** by `poc_delta_scan_mirror.py`. That script runs the exact pattern the extended `read_delta()` macro generates on the `fabric` target. Results:

| Table | Schema (ABFSS) | Rows | Columns |
|-------|----------------|------|---------|
| `youtube.videos` | `youtube` | 2 | video_id, title, channel_id, published_at, view_count, like_count |
| `skool.members` | `skool` | 2 | member_id, community, joined_at, posts |
| `test.row_marker_demo` | `test` | 3 (final state after all `__rowMarker__` ops) | employee_id, location |
| `dbo.smoke_test` | `dbo` | 3 | id, payload, created_at |

DuckDB setup used:
```sql
INSTALL azure; LOAD azure;
INSTALL delta; LOAD delta;
CREATE SECRET (TYPE AZURE, PROVIDER SERVICE_PRINCIPAL,
  TENANT_ID '...', CLIENT_ID '...', CLIENT_SECRET '...',
  ACCOUNT_NAME 'onelake');
SELECT * FROM delta_scan('abfss://<ws>@onelake.dfs.fabric.microsoft.com/<mirrored-db-id>/Tables/<schema>/<table>');
```

- [x] `delta_scan()` over the mirror Tables/ path works with SP auth: PASS
- [x] Columns and row counts match source data: PASS
- [x] Final state after incremental `__rowMarker__` operations is correct: PASS
- [ ] Macro change compiled in the real dbt project: **NOT YET EXECUTED**. The macro source is ready in this folder; dropping it into `feasibility/duckdb-dbt/poc_local_final_clean/macros/` and running `dbt compile --target fabric` is the next step. Deferred because the `fabric` target runs inside a Fabric notebook, not locally.
- [ ] Full `dbt build` on a staging model against the mirror: **DEFERRED**. Direct `delta_scan` proves the path works; dbt integration is a small amount of additional glue.

### Gotcha: schemaless tables

Tables uploaded without a `<name>.schema/` folder land under `/Tables/dbo/` in the mirror Delta tree (the `defaultSchema` from `mirroring.json`). So a caller must know to pass `'dbo'` as the schema arg - e.g. `read_delta('dbo', 'smoke_test', source_root='mirror')`. Recommendation: always use an explicit schema folder when producing into the landing zone. Don't rely on the default.
