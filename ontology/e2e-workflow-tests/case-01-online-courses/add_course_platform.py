"""
Incremental update: Add CoursePlatform entity to the existing OnlineCourses ontology.

Safe for re-deployment - strips any existing CoursePlatform artifacts before re-adding.

Demonstrates evolving a live ontology:
  1. Fetch the current definition
  2. Clean out any previous CoursePlatform artifacts
  3. Add CoursePlatform entity, PlatformID on Course, publishedOn relationship
  4. Add data bindings and contextualizations
  5. Push the updated definition in a single atomic update
  6. (Optionally) create/update Lakehouse tables and load seed data
"""
import sys
import json
import csv as csv_mod
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CLIENTS_DIR = SCRIPT_DIR.parents[1] / "clients"
sys.path.insert(0, str(CLIENTS_DIR))

from config import FABRIC_WORKSPACE_ID
from ontology_client import OntologyClient
from livy_client import LivyClient
from definition_builder import (
    decode_definition, encode_definition, generate_id,
    make_entity_type, make_property,
    add_entity_type, get_entity_type, update_entity_type, list_entity_types,
    remove_entity_type, list_relationship_types, remove_relationship_type,
    make_relationship_type, add_relationship_type,
    make_lakehouse_binding, make_property_binding, add_data_binding,
    make_contextualization, make_key_ref_binding, add_contextualization,
)
from lakehouse_sync import entity_name_to_table

# Load state from previous deployment
state = json.loads((SCRIPT_DIR / "_state.json").read_text())
ONTOLOGY_ID = state["ontologyId"]
LAKEHOUSE_ID = "7c750a97-d839-4166-9ef7-177d2c1622d9"
TABLE_PREFIX = "e2e_c01"
PLATFORM_TABLE = f"{TABLE_PREFIX}_course_platform"
COURSE_TABLE = f"{TABLE_PREFIX}_course"


def update_definition():
    """Rebuild and push the ontology definition with CoursePlatform."""
    ont = OntologyClient()

    print("=" * 60)
    print("  ADD CoursePlatform TO EXISTING ONTOLOGY")
    print("=" * 60)
    print(f"  Ontology: {ONTOLOGY_ID}")
    print()

    # === STEP 1: Read existing ontology definition ===
    print("STEP 1: Fetching current ontology definition...")
    raw = ont.get_definition(ONTOLOGY_ID)
    parts = decode_definition(raw)
    existing_entities = list_entity_types(parts)
    print(f"  Found {len(existing_entities)} existing entities:")
    for e in existing_entities:
        print(f"    - {e['name']} (id: {e['id']})")

    # --- Clean out any previous CoursePlatform artifacts ---
    print("\n  Cleaning previous CoursePlatform artifacts (if any)...")
    cleaned = False
    for e in existing_entities:
        if e["name"] == "CoursePlatform":
            parts = remove_entity_type(parts, str(e["id"]))
            print(f"    Removed entity CoursePlatform ({e['id']})")
            cleaned = True
    for r in list_relationship_types(parts):
        if r["name"] == "publishedOn":
            parts = remove_relationship_type(parts, str(r["id"]))
            print(f"    Removed relationship publishedOn ({r['id']})")
            cleaned = True
    if not cleaned:
        print("    None found - clean slate")

    # Re-read entities after cleanup
    existing_entities = list_entity_types(parts)

    # Find the existing Course entity
    course_entity = None
    course_et_id = None
    for e in existing_entities:
        if e["name"] == "Course":
            course_entity = e
            course_et_id = str(e["id"])
            break
    if not course_entity:
        print("ERROR: Course entity not found in ontology!")
        return
    print(f"\n  Course entity ID: {course_et_id}")

    # === STEP 2: Build CoursePlatform entity ===
    print("\nSTEP 2: Building CoursePlatform entity...")
    platform_id_prop = make_property("PlatformID", "String")
    platform_name_prop = make_property("name", "String")
    platform_url_prop = make_property("url", "String")

    cp_et_id, cp_et_def = make_entity_type(
        "CoursePlatform",
        properties=[platform_id_prop, platform_name_prop, platform_url_prop],
        entity_id_parts=[platform_id_prop["id"]],
        display_name_property_id=platform_name_prop["id"],
    )
    parts = add_entity_type(parts, cp_et_id, cp_et_def)
    print(f"  Entity ID: {cp_et_id}")
    print(f"  Properties: PlatformID, name, url")

    # === STEP 3: Add PlatformID property to existing Course entity ===
    print("\nSTEP 3: Adding PlatformID property to Course...")
    platform_fk_prop = {
        "id": generate_id(),
        "name": "PlatformID",
        "redefines": None,
        "baseTypeNamespaceType": None,
        "valueType": "String",
    }
    existing_prop_names = [p["name"] for p in course_entity["properties"]]
    if "PlatformID" in existing_prop_names:
        print("  PlatformID already exists on Course - reusing")
        platform_fk_prop = next(
            p for p in course_entity["properties"] if p["name"] == "PlatformID"
        )
    else:
        course_entity["properties"].append(platform_fk_prop)
        parts = update_entity_type(parts, course_et_id, course_entity)
        print(f"  Added PlatformID (prop id: {platform_fk_prop['id']})")

    # === STEP 4: Add publishedOn relationship ===
    print("\nSTEP 4: Adding publishedOn relationship (Course -> CoursePlatform)...")
    rt_id, rt_def = make_relationship_type(
        "publishedOn", course_et_id, cp_et_id
    )
    parts = add_relationship_type(parts, rt_id, rt_def)
    print(f"  Relationship ID: {rt_id}")

    # === STEP 5: Add data binding for CoursePlatform ===
    print("\nSTEP 5: Adding data binding for CoursePlatform...")
    prop_bindings = [
        make_property_binding("PlatformID", platform_id_prop["id"]),
        make_property_binding("name", platform_name_prop["id"]),
        make_property_binding("url", platform_url_prop["id"]),
    ]
    bid, binding_def = make_lakehouse_binding(
        cp_et_id, prop_bindings,
        FABRIC_WORKSPACE_ID, LAKEHOUSE_ID, PLATFORM_TABLE,
    )
    parts = add_data_binding(parts, cp_et_id, bid, binding_def)
    print(f"  Binding ID: {bid}")

    # Update Course data binding to include PlatformID
    print("\n  Updating Course data binding to include PlatformID...")
    course_binding_path = None
    course_binding = None
    for p in parts:
        if f"EntityTypes/{course_et_id}/DataBindings/" in p["path"]:
            course_binding_path = p["path"]
            course_binding = p["content"]
            break
    if course_binding:
        existing_cols = [
            pb["sourceColumnName"]
            for pb in course_binding["dataBindingConfiguration"]["propertyBindings"]
        ]
        if "PlatformID" not in existing_cols:
            course_binding["dataBindingConfiguration"]["propertyBindings"].append(
                make_property_binding("PlatformID", platform_fk_prop["id"])
            )
            parts = [
                {"path": p["path"],
                 "content": course_binding if p["path"] == course_binding_path else p["content"]}
                for p in parts
            ]
            print(f"  Added PlatformID to Course binding")
        else:
            print(f"  PlatformID already in Course binding")
    else:
        print("  WARNING: No existing Course binding found")

    # === STEP 6: Add contextualization for publishedOn ===
    print("\nSTEP 6: Adding contextualization for publishedOn...")
    course_key_prop_id = next(
        p["id"] for p in course_entity["properties"] if p["name"] == "CourseID"
    )
    source_bindings = [make_key_ref_binding("CourseID", str(course_key_prop_id))]
    target_bindings = [make_key_ref_binding("PlatformID", platform_id_prop["id"])]

    ctx_id, ctx_def = make_contextualization(
        FABRIC_WORKSPACE_ID, LAKEHOUSE_ID, COURSE_TABLE,
        source_bindings, target_bindings,
    )
    parts = add_contextualization(parts, rt_id, ctx_id, ctx_def)
    print(f"  Contextualization ID: {ctx_id}")
    print(f"  Context table: {COURSE_TABLE} (source-side FK)")

    # === STEP 7: Push updated definition ===
    print("\nSTEP 7: Pushing updated ontology definition...")
    encoded = encode_definition(parts)
    ont.update_definition(ONTOLOGY_ID, encoded)
    print("  Done")

    # Update state file
    if PLATFORM_TABLE not in state["tables"]:
        state["tables"].append(PLATFORM_TABLE)
        (SCRIPT_DIR / "_state.json").write_text(json.dumps(state, indent=2))
        print(f"\n  Updated _state.json with {PLATFORM_TABLE}")

    print(f"\n{'=' * 60}")
    print("  DEFINITION UPDATED!")
    print(f"{'=' * 60}")
    print(f"  New entity:       CoursePlatform ({cp_et_id})")
    print(f"  New relationship: publishedOn ({rt_id})")
    print(f"  Course updated:   +PlatformID property")
    print(f"  Bindings:         CoursePlatform -> {PLATFORM_TABLE}")
    print(f"  Contextualization: publishedOn via {COURSE_TABLE}")
    print(f"{'=' * 60}")


def setup_tables():
    """Create/update Lakehouse tables and load seed data (run after definition update)."""
    print("\n" + "=" * 60)
    print("  LAKEHOUSE TABLE SETUP")
    print("=" * 60)

    with LivyClient(FABRIC_WORKSPACE_ID, LAKEHOUSE_ID) as livy:
        # Create CoursePlatform table
        print(f"\n  Creating table '{PLATFORM_TABLE}'...")
        livy.sql(
            f"CREATE TABLE IF NOT EXISTS {PLATFORM_TABLE} "
            f"(PlatformID STRING, name STRING, url STRING) USING DELTA"
        )
        print("    Done")

        # ALTER Course table to add PlatformID column
        print(f"\n  Checking if '{COURSE_TABLE}' needs PlatformID column...")
        cols_result = livy.execute(
            f'print([f.name for f in spark.table("{COURSE_TABLE}").schema.fields])',
            kind="pyspark",
        )
        if cols_result and "PlatformID" in cols_result:
            print("    PlatformID column already exists")
        else:
            print("    ALTER TABLE: adding PlatformID column...")
            livy.sql(f"ALTER TABLE {COURSE_TABLE} ADD COLUMN PlatformID STRING")
            print("    Done")

        # Truncate and reload CoursePlatform seed data
        print(f"\n  Truncating {PLATFORM_TABLE}...")
        livy.sql(f"TRUNCATE TABLE {PLATFORM_TABLE}")
        csv_path = SCRIPT_DIR / "seed-data" / "CoursePlatform.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        values = []
        for row in rows:
            pid = row["PlatformID"].replace("'", "''")
            name = row["name"].replace("'", "''")
            url = row["url"].replace("'", "''")
            values.append(f"('{pid}', '{name}', '{url}')")
        sql = f"INSERT INTO {PLATFORM_TABLE} (PlatformID, name, url) VALUES {', '.join(values)}"
        print(f"  Loading {len(rows)} rows into {PLATFORM_TABLE}...")
        livy.sql(sql)

        # Update Course rows with PlatformID
        print(f"\n  Updating {COURSE_TABLE} with PlatformID values...")
        csv_path = SCRIPT_DIR / "seed-data" / "Course.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        for row in rows:
            cid = row["CourseID"].replace("'", "''")
            pid = row["PlatformID"].replace("'", "''")
            livy.sql(
                f"UPDATE {COURSE_TABLE} SET PlatformID = '{pid}' "
                f"WHERE CourseID = '{cid}'"
            )
            print(f"    {cid} -> {pid}")

        # Verify
        print(f"\n  Verifying {PLATFORM_TABLE}:")
        print(livy.sql(f"SELECT * FROM {PLATFORM_TABLE}"))
        print(f"\n  Verifying {COURSE_TABLE} PlatformID:")
        print(livy.sql(f"SELECT CourseID, title, PlatformID FROM {COURSE_TABLE}"))

    print(f"\n{'=' * 60}")
    print("  TABLES READY!")
    print(f"{'=' * 60}")
    print()
    print("  NEXT STEPS:")
    print("  1. Refresh the graph from the Fabric UI")
    print("  2. Run: python runner.py case-01-online-courses --validate")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add CoursePlatform to OnlineCourses ontology")
    parser.add_argument("--definition-only", action="store_true",
                        help="Only update the ontology definition (no table changes)")
    parser.add_argument("--tables-only", action="store_true",
                        help="Only create/update tables and load data")
    args = parser.parse_args()

    if args.tables_only:
        setup_tables()
    elif args.definition_only:
        update_definition()
    else:
        update_definition()
        setup_tables()
