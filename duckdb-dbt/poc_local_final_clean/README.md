# dbt + Ontology Development Workflow

## Overview

The ontology is the design authority for gold-layer table schemas. dbt is the execution mechanism that builds them. Raw tables exist in the Fabric lakehouse (created by a separate landing zone process) and are read directly via `delta_scan()` -- no catalog pre-registration needed.

## Day-to-Day Development

### 1. Make dbt model changes locally

```bash
cd feasibility/duckdb-dbt/poc_local_final_clean

# Seed raw data, run models, test
dbt seed --target local
dbt run --target local
dbt test --target local
```

### 2. Deploy to DEV

```bash
python tools/deploy.py --target dev
```

This copies dbt project files to `DEV_FilmProd_LH2/Files/dbt/`. No metadata.db is uploaded -- DuckLake auto-creates it on first run.

Then run the notebook in Fabric DEV (manually or via `fab job run`).

### 3. Deploy to PROD

```bash
python tools/deploy.py --target prod
```

Same process, targets `fea002_data_lh` in `Fabric_BMAD_PROD`.

## Ontology-Driven Schema Changes

When you update the ontology (add entities, properties, relationships), the dbt models need to reflect those changes.

### Step 1: Update the ontology

Make changes to the DEV ontology via the API tooling or Fabric UI (add a property, new entity, etc.).

### Step 2: Detect drift

```bash
python tools/sync_ontology_to_dbt.py
```

This reads the DEV ontology from the Fabric API, compares it against `models/gold/schema.yml`, and:
- Prints a human-readable report
- Writes a timestamped YAML file into `ontology_changes/` with machine-readable instructions

Example output:
```
[ADD] e2e_c02_film (entity: Film)
      Add 1 column(s) to e2e_c02_film
        cast(null as VARCHAR) as language
      Run: dbt run --full-refresh --select e2e_c02_film --target local
```

### Step 3: Apply changes via Claude

Ask Claude to read the latest file in `ontology_changes/` and update the dbt models. Claude will:
- Add new columns to the `.sql` model SELECT statements
- Add column definitions to `schema.yml`
- Handle comma placement, formatting, and computed column ordering correctly

### Step 4: Verify locally

```bash
dbt run --full-refresh --target local
dbt test --target local
```

Use `--full-refresh` because schema changes require a full table rebuild.

### Step 5: Re-run sync to confirm

```bash
python tools/sync_ontology_to_dbt.py
```

Should report: "All dbt models match the ontology. No changes needed."

### Step 6: Deploy

```bash
python tools/deploy.py --target dev    # then run notebook in DEV
python tools/deploy.py --target prod   # then run notebook in PROD
```

## How delta_scan() Works

The `read_delta()` macro in `macros/read_delta.sql` abstracts raw table access:

- **Local target**: uses `source()` which reads from DuckLake catalog (populated by `dbt seed`)
- **Fabric target**: uses `delta_scan()` which reads Delta tables directly from OneLake

This means no bootstrap or catalog sync is needed for raw tables. dbt reads them directly from wherever they live.

## Incremental vs Full Refresh

Gold models can be configured as incremental (see `e2e_c02_film.sql` for an example):

- **Normal run**: only processes new rows (based on `unique_key`)
- **Schema change**: run with `--full-refresh` to rebuild the table with the new schema
- **Full rebuild**: `dbt run --full-refresh --target local` rebuilds everything

## Key Files

| File | Purpose |
|------|---------|
| `profiles.yml` | dbt profiles (local + fabric targets) |
| `tools/deploy.py` | Upload dbt files to Fabric lakehouse |
| `tools/sync_ontology_to_dbt.py` | Compare ontology vs dbt, write change log |
| `tools/promote_ontology.py` | Promote ontology definition from DEV to PROD |
| `ontology_changes/` | Timestamped change logs for Claude (yyyymmdd-hhmm.yml) |
| `macros/read_delta.sql` | Abstracts raw table access (source vs delta_scan) |
| `macros/table_replace.sql` | Custom materialization (CREATE OR REPLACE TABLE) |
| `models/gold/schema.yml` | Gold model column definitions and tests |
