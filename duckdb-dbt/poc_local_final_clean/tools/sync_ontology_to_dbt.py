"""Compare ontology definition against dbt gold models and produce a change log.

Reads the DEV ontology from the Fabric API, parses the current dbt schema.yml,
and writes a timestamped YAML change log into the ontology_changes/ folder
that Claude can consume to apply the dbt model updates.

Usage:
    python tools/sync_ontology_to_dbt.py
    python tools/sync_ontology_to_dbt.py --output-dir ontology_changes/20260331-1430
"""
import argparse
import os
import sys
from datetime import datetime, timezone

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "ontology", "clients"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))

from ontology_client import OntologyClient
from definition_builder import decode_definition, list_entity_types, list_data_bindings

DEV_WORKSPACE_ID = os.environ["FABRIC_DEV_WORKSPACE_ID"]
DEV_ONTOLOGY_ID = os.environ["FABRIC_DEV_ONTOLOGY_ID"]

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEMA_YML = os.path.join(PROJECT_ROOT, "models", "gold", "schema.yml")
CHANGE_LOG_DIR = os.path.join(PROJECT_ROOT, "ontology_changes")

ONTOLOGY_TYPE_TO_DUCKDB = {
    "String": "VARCHAR",
    "DateTime": "TIMESTAMP",
    "BigInt": "BIGINT",
    "Double": "DOUBLE",
    "Boolean": "BOOLEAN",
    "Object": "VARCHAR",
}


# -- Ontology parsing ---------------------------------------------------------

def get_table_map(parts):
    """Build entity_id -> (schema, table_name) from data bindings."""
    table_map = {}
    for b in list_data_bindings(parts):
        et_id = b["path"].split("/")[1]
        src = b["content"].get("dataBindingConfiguration", {}).get("sourceTableProperties", {})
        table_name = src.get("sourceTableName")
        schema = src.get("sourceSchema", "dbo")
        if table_name:
            table_map[et_id] = (schema, table_name)
    return table_map


def get_ontology_models(parts):
    """Extract {table_name: {entity_name, properties}} from ontology definition."""
    entities = list_entity_types(parts)
    table_map = get_table_map(parts)
    models = {}

    for entity in entities:
        et_id = str(entity["id"])
        if et_id not in table_map:
            continue

        _schema, table_name = table_map[et_id]
        all_props = entity.get("properties", []) + entity.get("timeseriesProperties", [])
        models[table_name] = {
            "entity_name": entity["name"],
            "properties": [
                {"name": p["name"], "ontology_type": p["valueType"],
                 "duckdb_type": ONTOLOGY_TYPE_TO_DUCKDB.get(p["valueType"], "VARCHAR")}
                for p in all_props
            ],
        }

    return models


# -- dbt model parsing --------------------------------------------------------

def get_dbt_schema(schema_path):
    """Extract {model_name: [column_names]} from schema.yml."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    models = {}
    for model in schema.get("models", []):
        models[model["name"]] = [c["name"] for c in model.get("columns", [])]

    return models


# -- Comparison ----------------------------------------------------------------

def compare(ontology_models, dbt_schema):
    """Compare ontology entities against dbt models. Returns structured changes."""
    changes = []

    for table_name, ont in sorted(ontology_models.items()):
        ont_col_names = {p["name"] for p in ont["properties"]}
        dbt_cols = set(dbt_schema.get(table_name, []))
        if table_name not in dbt_schema:
            changes.append({
                "model": table_name,
                "entity": ont["entity_name"],
                "action": "create_model",
                "sql_file": f"models/gold/{table_name}.sql",
                "columns": ont["properties"],
            })
            continue

        # Columns in ontology but missing from dbt schema.yml
        added = ont_col_names - dbt_cols
        # Columns in dbt but not in ontology (computed columns -- informational)
        extra = dbt_cols - ont_col_names

        if added:
            new_props = [p for p in ont["properties"] if p["name"] in added]
            changes.append({
                "model": table_name,
                "entity": ont["entity_name"],
                "action": "add_columns",
                "sql_file": f"models/gold/{table_name}.sql",
                "columns": new_props,
            })

        if extra:
            changes.append({
                "model": table_name,
                "entity": ont["entity_name"],
                "action": "info_computed_columns",
                "note": f"Columns in dbt but not in ontology (likely computed): {', '.join(sorted(extra))}",
            })

    return changes


# -- Change log output ---------------------------------------------------------

def write_change_log(changes, ontology_models, dbt_schema, output_dir=None):
    """Write machine-readable change log for Claude to consume.

    Args:
        output_dir: If provided, writes dbt_changes.yml into this directory.
                    Otherwise, writes a timestamped file into ontology_changes/.
    """
    actionable = [c for c in changes if c["action"] in ("create_model", "add_columns")]

    log = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "ontology_id": DEV_ONTOLOGY_ID,
        "summary": f"{len(actionable)} model(s) need updates" if actionable else "All models in sync",
        "status": "changes_needed" if actionable else "in_sync",
        "changes": [],
    }

    for change in changes:
        entry = {
            "model": change["model"],
            "entity": change["entity"],
            "action": change["action"],
        }

        if change["action"] == "create_model":
            entry["sql_file"] = change["sql_file"]
            entry["instruction"] = f"Create new gold model for ontology entity '{change['entity']}'"
            entry["columns"] = [
                {"name": c["name"], "duckdb_type": c["duckdb_type"],
                 "sql_expression": f"cast(null as {c['duckdb_type']}) as {c['name']}"}
                for c in change["columns"]
            ]

        elif change["action"] == "add_columns":
            entry["sql_file"] = change["sql_file"]
            entry["instruction"] = f"Add {len(change['columns'])} column(s) to {change['model']}"
            entry["columns"] = [
                {"name": c["name"], "duckdb_type": c["duckdb_type"],
                 "sql_expression": f"cast(null as {c['duckdb_type']}) as {c['name']}"}
                for c in change["columns"]
            ]
            entry["post_apply"] = "Run: dbt run --full-refresh --select {model} --target local".format(**change)

        elif change["action"] == "info_computed_columns":
            entry["note"] = change["note"]

        log["changes"].append(entry)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        change_log_path = os.path.join(output_dir, "dbt_changes.yml")
    else:
        os.makedirs(CHANGE_LOG_DIR, exist_ok=True)
        filename = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M.yml")
        change_log_path = os.path.join(CHANGE_LOG_DIR, filename)

    with open(change_log_path, "w", encoding="utf-8") as f:
        yaml.dump(log, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return log, change_log_path


# -- Report --------------------------------------------------------------------

def print_report(log, change_log_path):
    """Print human-readable summary."""
    print("=" * 70)
    print("ONTOLOGY -> dbt SYNC REPORT")
    print(f"Generated: {log['generated']}")
    print("=" * 70)

    if log["status"] == "in_sync":
        print("\nAll dbt models match the ontology. No changes needed.")
        return

    for entry in log["changes"]:
        if entry["action"] == "create_model":
            print(f"\n  [NEW] {entry['model']} (entity: {entry['entity']})")
            print(f"        {entry['instruction']}")
            for col in entry["columns"]:
                print(f"          {col['sql_expression']}")

        elif entry["action"] == "add_columns":
            print(f"\n  [ADD] {entry['model']} (entity: {entry['entity']})")
            print(f"        {entry['instruction']}")
            for col in entry["columns"]:
                print(f"          {col['sql_expression']}")
            print(f"        {entry['post_apply']}")

        elif entry["action"] == "info_computed_columns":
            print(f"\n  [i]   {entry['model']}: {entry['note']}")

    print(f"\nChange log written to: {change_log_path}")
    print()


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compare ontology vs dbt models")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Write dbt_changes.yml into this directory instead of a timestamped file",
    )
    args = parser.parse_args()

    print("Reading DEV ontology definition...")
    client = OntologyClient(DEV_WORKSPACE_ID)
    raw = client.get_definition(DEV_ONTOLOGY_ID)
    parts = decode_definition(raw)

    ontology_models = get_ontology_models(parts)
    print(f"  Found {len(ontology_models)} entities with data bindings")

    dbt_schema = get_dbt_schema(SCHEMA_YML)
    print(f"  Found {len(dbt_schema)} dbt gold models\n")

    changes = compare(ontology_models, dbt_schema)
    log, change_log_path = write_change_log(
        changes, ontology_models, dbt_schema, output_dir=args.output_dir
    )
    print_report(log, change_log_path)


if __name__ == "__main__":
    main()
