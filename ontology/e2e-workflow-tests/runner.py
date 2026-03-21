"""
E2E Workflow Test Runner

Orchestrates end-to-end ontology workflow tests using existing client modules.
Each case folder contains a data package (ontology.json, seed CSVs, GQL queries)
with no Python code. This runner handles all the orchestration.

Usage:
    python runner.py <case-folder> --setup      Create ontology + tables + data + bindings
    python runner.py <case-folder> --validate   Run GQL queries against the graph
    python runner.py <case-folder> --cleanup    Delete ontology + drop tables

    python runner.py --all --setup              Setup all cases
    python runner.py --all --cleanup            Cleanup all cases

Graph refresh is manual (API refresh not supported for ontology-managed graphs).
After --setup, refresh the graph from the Fabric UI, then run --validate.
"""
import sys
import os
import json
import argparse
import time
from pathlib import Path

# Add clients directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
CLIENTS_DIR = SCRIPT_DIR.parent / "clients"
sys.path.insert(0, str(CLIENTS_DIR))

from config import FABRIC_WORKSPACE_ID
from ontology_client import OntologyClient
from graph_client import GraphClient
from definition_builder import (
    encode_definition, decode_definition,
    build_from_config, add_all_bindings, add_all_contextualizations,
)
from lakehouse_sync import create_tables_from_config, load_csv_data
from livy_client import LivyClient

LAKEHOUSE_ID = os.environ.get(
    "FABRIC_LAKEHOUSE_ID", "7c750a97-d839-4166-9ef7-177d2c1622d9"
)


# ---------------------------------------------------------------------------
# Config / state helpers
# ---------------------------------------------------------------------------

def load_config(case_dir: Path) -> dict:
    with open(case_dir / "ontology.json", encoding="utf-8") as f:
        return json.load(f)


def load_state(case_dir: Path) -> dict:
    state_path = case_dir / "_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"No _state.json in {case_dir}. Run --setup first.")
    with open(state_path, encoding="utf-8") as f:
        return json.load(f)


def save_state(case_dir: Path, state: dict):
    with open(case_dir / "_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def create_ontology_and_get_id(ont: OntologyClient, name: str,
                                description: str) -> str:
    """Create an ontology and return its ID (handles async LRO)."""
    result = ont.create_ontology(name, description=description)
    ontology_id = result.get("id")
    if not ontology_id:
        print("  Async creation - finding ontology by name...")
        time.sleep(3)
        for o in ont.list_ontologies():
            if o["displayName"] == name:
                return o["id"]
        raise RuntimeError(f"Failed to find ontology '{name}' after creation")
    return ontology_id


# ---------------------------------------------------------------------------
# --setup
# ---------------------------------------------------------------------------

def do_setup(case_dir: Path):
    config = load_config(case_dir)
    workspace_id = FABRIC_WORKSPACE_ID
    ont = OntologyClient()

    print(f"\n{'=' * 60}")
    print(f"  SETUP: {config['name']}")
    print(f"{'=' * 60}")
    print(f"  {config['description']}\n")

    # 1. Build definition from config
    print("Building ontology definition...")
    parts, entity_map, rel_map = build_from_config(config)
    print(f"  Entities: {', '.join(entity_map.keys())}")
    print(f"  Relationships: {', '.join(rel_map.keys())}")

    # 2. Create ontology + push schema
    print("\nCreating ontology...")
    ontology_id = create_ontology_and_get_id(
        ont, config["name"], config["description"]
    )
    print(f"  Ontology ID: {ontology_id}")

    print("\nPushing entity and relationship definition...")
    ont.update_definition(ontology_id, encode_definition(parts))
    print("  Done")

    # 3. Create tables + load seed data
    print("\nOpening Livy session...")
    with LivyClient(workspace_id, LAKEHOUSE_ID) as livy:
        print("\nCreating tables...")
        create_tables_from_config(livy, config["entities"], entity_map)
        print("\nLoading seed data...")
        load_csv_data(livy, case_dir / "seed-data", config["entities"], entity_map)

    # 4. Re-fetch definition, add bindings + contextualizations, push
    print("\nRe-fetching definition...")
    raw = ont.get_definition(ontology_id)
    parts = decode_definition(raw)
    print(f"  Got {len(parts)} parts")

    print("\nBuilding data bindings...")
    parts = add_all_bindings(
        parts, entity_map, config["entities"], workspace_id, LAKEHOUSE_ID
    )
    print("\nBuilding contextualizations...")
    parts = add_all_contextualizations(
        parts, rel_map, entity_map, workspace_id, LAKEHOUSE_ID
    )

    print("\nPushing final definition (bindings + contextualizations)...")
    ont.update_definition(ontology_id, encode_definition(parts))
    print("  Done")

    # 5. Save state
    save_state(case_dir, {
        "ontologyId": ontology_id,
        "ontologyName": config["name"],
        "tables": [info["table"] for info in entity_map.values()],
    })

    print(f"\n{'=' * 60}")
    print("  Setup complete!")
    print()
    print("  NEXT STEPS:")
    print("  1. Open Fabric UI -> navigate to the ontology")
    print("  2. Open the auto-provisioned graph model")
    print("  3. Click 'Refresh now' in the Schedule panel")
    print("  4. Wait for refresh to complete")
    print(f"  5. Run: python runner.py {case_dir.name} --validate")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------

def do_validate(case_dir: Path, graph_id: str = None):
    config = load_config(case_dir)
    load_state(case_dir)  # verify setup was run

    print(f"\n{'=' * 60}")
    print(f"  VALIDATE: {config['name']}")
    print(f"{'=' * 60}\n")

    gc = GraphClient()

    # Find graph model
    if not graph_id:
        for g in gc.list_graph_models():
            if config["name"] in g.get("displayName", ""):
                graph_id = g["id"]
                print(f"Found graph: {g['displayName']} ({graph_id})")
                break

    if not graph_id:
        print("Could not auto-detect graph model. Available models:")
        for g in gc.list_graph_models():
            print(f"  - {g.get('displayName', '?')} ({g['id']})")
        print("\nRe-run with: python runner.py <case> --validate --graph-id <id>")
        return

    # Execute GQL queries
    gql_files = sorted((case_dir / "gql-queries").glob("*.gql"))
    if not gql_files:
        print("No .gql files found.")
        return

    print(f"Executing {len(gql_files)} GQL queries...\n")
    passed = failed = 0

    for gql_file in gql_files:
        content = gql_file.read_text(encoding="utf-8")
        header_lines, query_lines = [], []
        for line in content.strip().split("\n"):
            if line.strip().startswith("//"):
                header_lines.append(line.strip().lstrip("/ ").strip())
            else:
                query_lines.append(line)
        query = "\n".join(query_lines).strip()

        print(f"--- {gql_file.name} ---")
        for h in header_lines:
            print(f"  {h}")
        print()

        try:
            result = gc.execute_query(graph_id, query)
            status = result.get("status", {})
            if status.get("code") == "00000":
                data = result.get("result", {})
                columns = data.get("columns", [])
                rows = data.get("data", [])
                # columns are dicts: {"name": "...", "gqlType": "...", "jsonType": "..."}
                col_names = [c["name"] if isinstance(c, dict) else str(c) for c in columns]
                if col_names:
                    header = " | ".join(col_names)
                    print(f"  {header}")
                    print(f"  {'-' * len(header)}")
                for row in rows:
                    # rows are dicts: {"colName": value, ...}
                    if isinstance(row, dict):
                        vals = [str(row.get(c, "")) for c in col_names]
                    else:
                        vals = [str(v) for v in row]
                    print(f"  {' | '.join(vals)}")
                print(f"  ({len(rows)} rows)")
                passed += 1
            else:
                print(f"  ERROR: {status.get('description', 'Unknown error')}")
                failed += 1
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            failed += 1
        print()

    print(f"Results: {passed} passed, {failed} failed out of {len(gql_files)} queries")


# ---------------------------------------------------------------------------
# --cleanup
# ---------------------------------------------------------------------------

def do_cleanup(case_dir: Path):
    config = load_config(case_dir)
    state = load_state(case_dir)

    print(f"\n{'=' * 60}")
    print(f"  CLEANUP: {config['name']}")
    print(f"{'=' * 60}\n")

    tables = state.get("tables", [])
    if tables:
        print("Dropping tables...")
        with LivyClient(FABRIC_WORKSPACE_ID, LAKEHOUSE_ID) as livy:
            for table in tables:
                print(f"  DROP TABLE {table}")
                livy.sql(f"DROP TABLE IF EXISTS {table}")
        print()

    print(f"Deleting ontology {state['ontologyId']}...")
    OntologyClient().delete_ontology(state["ontologyId"])
    print("  Done\n")

    state_path = case_dir / "_state.json"
    if state_path.exists():
        state_path.unlink()
        print("Removed state file")
    print("Cleanup complete!\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="E2E Ontology Workflow Test Runner")
    parser.add_argument("case", nargs="?",
                        help="Case folder name (e.g. case-01-online-courses)")
    parser.add_argument("--all", action="store_true",
                        help="Run against all case-* directories")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true")
    group.add_argument("--validate", action="store_true")
    group.add_argument("--cleanup", action="store_true")

    parser.add_argument("--graph-id", default=None,
                        help="Graph model ID override for --validate")
    args = parser.parse_args()

    if args.all:
        case_dirs = sorted(SCRIPT_DIR.glob("case-*"))
        if not case_dirs:
            print("No case-* directories found.")
            sys.exit(1)
        print(f"Found {len(case_dirs)} case(s): {', '.join(d.name for d in case_dirs)}\n")
    elif args.case:
        case_dir = SCRIPT_DIR / args.case
        if not case_dir.exists():
            print(f"ERROR: Case directory not found: {case_dir}")
            sys.exit(1)
        case_dirs = [case_dir]
    else:
        parser.error("Provide a case folder name or use --all")

    for case_dir in case_dirs:
        try:
            if args.setup:
                do_setup(case_dir)
            elif args.validate:
                do_validate(case_dir, graph_id=args.graph_id)
            elif args.cleanup:
                do_cleanup(case_dir)
        except Exception as e:
            print(f"\nERROR in {case_dir.name}: {e}")
            if len(case_dirs) == 1:
                raise
            print("Continuing with next case...\n")


if __name__ == "__main__":
    main()
