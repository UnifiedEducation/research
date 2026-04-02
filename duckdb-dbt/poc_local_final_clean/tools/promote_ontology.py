"""Promote ontology definition from DEV to PROD.

Reads the DEV ontology, rewrites all bindings to point at the PROD
workspace/lakehouse, updates the PROD ontology definition, then executes
the latest migration script against the PROD lakehouse via Livy.

Usage:
    python tools/promote_ontology.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "ontology", "clients"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))

from ontology_client import OntologyClient
from livy_client import LivyClient
from definition_builder import (
    decode_definition, encode_definition,
    list_entity_types, list_data_bindings, list_contextualizations,
)

# -- Config -------------------------------------------------------------------

DEV_WORKSPACE_ID = os.environ["FABRIC_DEV_WORKSPACE_ID"]
DEV_ONTOLOGY_ID = os.environ["FABRIC_DEV_ONTOLOGY_ID"]

PROD_WORKSPACE_ID = os.environ["FABRIC_WORKSPACE_ID"]
PROD_LAKEHOUSE_ID = os.environ["FABRIC_LAKEHOUSE_ID"]
PROD_ONTOLOGY_ID = os.environ["FABRIC_ONTOLOGY_ID"]

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")


# -- Ontology promotion ------------------------------------------------------

def read_and_rewrite_definition():
    """Read DEV ontology definition and rewrite all bindings to PROD."""
    dev_client = OntologyClient(DEV_WORKSPACE_ID)

    print("Reading DEV ontology definition...")
    raw = dev_client.get_definition(DEV_ONTOLOGY_ID)
    parts = decode_definition(raw)

    entities = list_entity_types(parts)
    bindings = list_data_bindings(parts)
    ctxs = list_contextualizations(parts)
    print(f"  {len(entities)} entities, {len(bindings)} bindings, {len(ctxs)} contextualizations")

    # Rewrite all workspace/lakehouse references to PROD
    rewritten = 0
    for part in parts:
        content = part["content"]
        if not isinstance(content, dict):
            continue

        if "/DataBindings/" in part["path"]:
            src = content.get("dataBindingConfiguration", {}).get("sourceTableProperties", {})
            src["workspaceId"] = PROD_WORKSPACE_ID
            src["itemId"] = PROD_LAKEHOUSE_ID
            rewritten += 1

        if "/Contextualizations/" in part["path"]:
            tbl = content.get("dataBindingTable", {})
            tbl["workspaceId"] = PROD_WORKSPACE_ID
            tbl["itemId"] = PROD_LAKEHOUSE_ID
            rewritten += 1

    print(f"  Rewrote {rewritten} bindings to PROD")
    return parts


def update_prod_ontology(parts):
    """Push the rewritten definition to the PROD ontology."""
    prod_client = OntologyClient(PROD_WORKSPACE_ID)

    print(f"\nUpdating PROD ontology ({PROD_ONTOLOGY_ID})...")
    prod_client.update_definition(PROD_ONTOLOGY_ID, encode_definition(parts))
    print("  Ontology definition updated.")


# -- Migration execution -----------------------------------------------------

def read_migration_pointer():
    """Read migrations.yml to get the migration file to execute."""
    yml_path = os.path.join(ROOT_DIR, "migrations.yml")
    if not os.path.exists(yml_path):
        return None
    with open(yml_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("migration_to_run:"):
                rel_path = line.split(":", 1)[1].strip()
                if not rel_path:
                    return None
                return os.path.join(ROOT_DIR, rel_path)
    return None


def execute_migration(migration_path):
    """Execute a migration SQL file against the PROD lakehouse via Livy."""
    print(f"\nExecuting migration: {os.path.basename(migration_path)}")

    with open(migration_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse statements (skip comments and blank lines)
    statements = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        statements.append(line)

    if not statements:
        print("  No statements to execute.")
        return

    print(f"  {len(statements)} statement(s) to execute")

    with LivyClient(PROD_WORKSPACE_ID, PROD_LAKEHOUSE_ID) as livy:
        for i, stmt in enumerate(statements, 1):
            print(f"  [{i}/{len(statements)}] {stmt[:80]}...")
            try:
                livy.sql(stmt)
            except Exception as e:
                err = str(e).lower()
                if "already exists" in err:
                    print(f"    (skipped -- already exists)")
                else:
                    raise

    print("  Migration complete.")


# -- Main ---------------------------------------------------------------------

def main():
    parts = read_and_rewrite_definition()
    update_prod_ontology(parts)

    migration = read_migration_pointer()
    if migration:
        execute_migration(migration)
    else:
        print("\nNo migration files found -- skipping lakehouse sync.")

    print("\nPromotion complete.")


if __name__ == "__main__":
    main()
