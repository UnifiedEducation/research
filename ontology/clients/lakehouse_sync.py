"""
Sync ontology entity types to Lakehouse tables and data bindings.

Workflow:
  1. Define/update entity properties in the ontology definition
  2. This module creates or alters the Lakehouse table(s) to match
  3. This module creates or updates the data binding(s) to connect them

Supports single-entity sync and batch sync of all entities in one API round trip.

Ontology valueType -> Spark SQL type mapping:
  String   -> STRING
  DateTime -> TIMESTAMP
  BigInt   -> BIGINT
  Double   -> DOUBLE
  Boolean  -> BOOLEAN
  Object   -> STRING
"""
import re
from definition_builder import (
    decode_definition, encode_definition,
    get_entity_type, list_entity_types, list_data_bindings,
    make_lakehouse_binding, make_property_binding,
    add_data_binding, update_data_binding,
)
from ontology_client import OntologyClient
from livy_client import LivyClient


ONTOLOGY_TYPE_TO_SPARK = {
    "String": "STRING",
    "DateTime": "TIMESTAMP",
    "BigInt": "BIGINT",
    "Double": "DOUBLE",
    "Boolean": "BOOLEAN",
    "Object": "STRING",
}


def _spark_type(ontology_type: str) -> str:
    return ONTOLOGY_TYPE_TO_SPARK.get(ontology_type, "STRING")


def entity_name_to_table(name: str) -> str:
    """Convert an entity type name to a Lakehouse table name (snake_case)."""
    # Insert underscore before uppercase letters, then lowercase everything
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    s = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", s)
    return s.lower().replace(" ", "_")


def _table_exists(livy: LivyClient, table_name: str) -> bool:
    result = livy.execute(
        f'print(spark.catalog.tableExists("{table_name}"))',
        kind="pyspark",
    )
    return result and "True" in result


def _get_table_columns(livy: LivyClient, table_name: str) -> set[str]:
    """Get existing column names from a Lakehouse table."""
    result = livy.execute(
        f'print([f.name for f in spark.table("{table_name}").schema.fields])',
        kind="pyspark",
    )
    if not result:
        return set()
    import ast
    try:
        return set(ast.literal_eval(result.strip()))
    except (ValueError, SyntaxError):
        return set()


def _sync_table(livy: LivyClient, entity: dict, table_name: str):
    """Create or alter a Lakehouse table to match an entity's properties."""
    all_props = entity.get("properties", []) + entity.get("timeseriesProperties", [])
    if not all_props:
        print(f"  SKIP {entity['name']} - no properties")
        return

    if _table_exists(livy, table_name):
        print(f"  Table '{table_name}' exists - checking for new columns...")
        existing_cols = _get_table_columns(livy, table_name)
        new_props = [p for p in all_props if p["name"] not in existing_cols]
        if new_props:
            for prop in new_props:
                spark_type = _spark_type(prop["valueType"])
                print(f"    ALTER TABLE: adding {prop['name']} ({spark_type})")
                livy.sql(f"ALTER TABLE {table_name} ADD COLUMN {prop['name']} {spark_type}")
            print(f"    Added {len(new_props)} column(s)")
        else:
            print(f"    Already in sync")
    else:
        cols = ", ".join(
            f"{p['name']} {_spark_type(p['valueType'])}" for p in all_props
        )
        print(f"  Creating table '{table_name}'...")
        livy.sql(f"CREATE TABLE {table_name} ({cols}) USING DELTA")
        print(f"    Created with {len(all_props)} columns")


def _build_binding(parts: list[dict], entity: dict, entity_type_id: str,
                   workspace_id: str, lakehouse_id: str,
                   table_name: str) -> tuple[list[dict], str]:
    """Build or update a data binding for an entity. Returns (updated_parts, binding_id)."""
    all_props = entity.get("properties", []) + entity.get("timeseriesProperties", [])

    prop_bindings = [
        make_property_binding(p["name"], p["id"]) for p in all_props
    ]

    # Find existing binding for this table
    existing_bindings = list_data_bindings(parts, entity_type_id)
    existing_binding_id = None
    for b in existing_bindings:
        src = b["content"].get("dataBindingConfiguration", {}).get("sourceTableProperties", {})
        if src.get("sourceTableName") == table_name:
            existing_binding_id = b["content"]["id"]
            break

    has_timeseries = len(entity.get("timeseriesProperties", [])) > 0
    binding_type = "TimeSeries" if has_timeseries else "NonTimeSeries"
    timestamp_col = None
    if has_timeseries:
        ts_props = entity["timeseriesProperties"]
        ts_datetime = next((p for p in ts_props if p["valueType"] == "DateTime"), None)
        timestamp_col = ts_datetime["name"] if ts_datetime else ts_props[0]["name"]

    bid, binding_def = make_lakehouse_binding(
        entity_type_id, prop_bindings,
        workspace_id, lakehouse_id, table_name,
        binding_type=binding_type,
        timestamp_column=timestamp_col,
        binding_id=existing_binding_id,
    )

    if existing_binding_id:
        print(f"    Updating binding ({bid})")
        parts = update_data_binding(parts, entity_type_id, bid, binding_def)
    else:
        print(f"    Creating binding ({bid})")
        parts = add_data_binding(parts, entity_type_id, bid, binding_def)

    return parts, bid


def sync_entity_to_lakehouse(ontology_client: OntologyClient,
                             ontology_id: str,
                             entity_type_id: str,
                             livy: LivyClient,
                             lakehouse_id: str,
                             table_name: str,
                             workspace_id: str = None):
    """
    Sync a single ontology entity type to a Lakehouse table and data binding.

    - If the table doesn't exist, creates it with all entity properties as columns.
    - If the table exists, adds any missing columns.
    - Creates or updates the data binding to map all properties.

    Returns the binding ID.
    """
    workspace_id = workspace_id or ontology_client.workspace_id

    print(f"Fetching ontology definition...")
    raw = ontology_client.get_definition(ontology_id)
    parts = decode_definition(raw)

    entity = get_entity_type(parts, entity_type_id)
    if not entity:
        raise ValueError(f"Entity type {entity_type_id} not found in ontology")

    all_props = entity.get("properties", []) + entity.get("timeseriesProperties", [])
    if not all_props:
        raise ValueError(f"Entity type {entity['name']} has no properties")

    print(f"Entity: {entity['name']} ({len(all_props)} properties)")

    _sync_table(livy, entity, table_name)
    parts, bid = _build_binding(parts, entity, entity_type_id,
                                workspace_id, lakehouse_id, table_name)

    print(f"Pushing ontology definition...")
    encoded = encode_definition(parts)
    ontology_client.update_definition(ontology_id, encoded)

    print(f"Done - entity '{entity['name']}' synced to table '{table_name}'")
    return bid


def sync_all_entities(ontology_client: OntologyClient,
                      ontology_id: str,
                      livy: LivyClient,
                      lakehouse_id: str,
                      workspace_id: str = None,
                      entity_ids: list[str] = None,
                      table_map: dict[str, str] = None):
    """
    Sync all (or specified) ontology entities to Lakehouse tables and bindings.

    Reads the ontology definition once, creates/alters all tables, builds all
    bindings in memory, then pushes a single updated definition.

    Args:
        ontology_client: OntologyClient instance
        ontology_id: The ontology to sync
        livy: Active LivyClient session
        lakehouse_id: Target Lakehouse ID
        workspace_id: Override workspace (defaults to client's workspace)
        entity_ids: Specific entity IDs to sync. If None, syncs all entities.
        table_map: Optional {entity_type_id: table_name} overrides.
                   If not provided, table names are derived from entity names
                   using snake_case conversion.

    Returns:
        dict mapping entity_type_id -> {"table": table_name, "binding_id": bid}
    """
    workspace_id = workspace_id or ontology_client.workspace_id
    table_map = table_map or {}

    # 1. Read ontology definition once
    print("Fetching ontology definition...")
    raw = ontology_client.get_definition(ontology_id)
    parts = decode_definition(raw)

    # 2. Determine which entities to sync
    all_entities = list_entity_types(parts)
    if entity_ids:
        entities = [e for e in all_entities if str(e["id"]) in entity_ids]
        if len(entities) != len(entity_ids):
            found = {str(e["id"]) for e in entities}
            missing = set(entity_ids) - found
            raise ValueError(f"Entity type(s) not found: {missing}")
    else:
        entities = all_entities

    if not entities:
        print("No entities to sync.")
        return {}

    print(f"Syncing {len(entities)} entity type(s) to Lakehouse...\n")

    # 3. Create/alter tables for each entity
    results = {}
    for entity in entities:
        et_id = str(entity["id"])
        table_name = table_map.get(et_id, entity_name_to_table(entity["name"]))
        all_props = entity.get("properties", []) + entity.get("timeseriesProperties", [])

        print(f"[{entity['name']}] ({len(all_props)} properties -> {table_name})")

        if not all_props:
            print(f"  SKIP - no properties")
            continue

        _sync_table(livy, entity, table_name)
        results[et_id] = {"table": table_name}

    # 4. Build all bindings in memory (single pass over parts)
    print(f"\nBuilding data bindings...")
    for et_id, info in results.items():
        entity = get_entity_type(parts, et_id)
        print(f"  [{entity['name']}]")
        parts, bid = _build_binding(parts, entity, et_id,
                                    workspace_id, lakehouse_id, info["table"])
        info["binding_id"] = bid

    # 5. Push updated definition once
    print(f"\nPushing ontology definition (single update)...")
    encoded = encode_definition(parts)
    ontology_client.update_definition(ontology_id, encoded)

    # 6. Summary
    print(f"\nSync complete:")
    for et_id, info in results.items():
        entity = get_entity_type(parts, et_id)
        print(f"  {entity['name']} -> {info['table']} (binding: {info['binding_id'][:8]}...)")

    return results


# -- Config-driven table creation + CSV data loading --------------------------

def create_tables_from_config(livy: LivyClient, entities_config: list,
                              entity_map: dict):
    """
    Create Lakehouse tables from a config entity list and entity_map.

    entities_config: the "entities" list from the ontology config dict.
    entity_map:      {name: {table, ...}} as returned by build_from_config().
    """
    for entity_cfg in entities_config:
        name = entity_cfg["name"]
        table = entity_map[name]["table"]
        cols = ", ".join(
            f"{p['name']} {_spark_type(p['valueType'])}"
            for p in entity_cfg["properties"]
        )
        print(f"  Creating table {table}...")
        livy.sql(f"CREATE TABLE IF NOT EXISTS {table} ({cols}) USING DELTA")


def load_csv_data(livy: LivyClient, csv_dir, entities_config: list,
                  entity_map: dict):
    """
    Load seed data from CSV files into Lakehouse tables.

    csv_dir:         Path to directory containing {EntityName}.csv files.
    entities_config: the "entities" list from the ontology config dict.
    entity_map:      {name: {table, ...}} as returned by build_from_config().

    CSV column headers must match property names exactly. Files are named
    after the entity (e.g. Course.csv for entity "Course").
    """
    import csv as csv_mod
    from pathlib import Path
    csv_dir = Path(csv_dir)

    for entity_cfg in entities_config:
        name = entity_cfg["name"]
        table = entity_map[name]["table"]
        csv_path = csv_dir / f"{name}.csv"

        if not csv_path.exists():
            print(f"  SKIP {name} - no seed data file")
            continue

        type_map = {p["name"]: p["valueType"] for p in entity_cfg["properties"]}

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))

        if not rows:
            print(f"  SKIP {name} - empty CSV")
            continue

        columns = list(rows[0].keys())
        col_list = ", ".join(columns)

        value_rows = []
        for row in rows:
            values = []
            for col in columns:
                val = row[col].strip() if row[col] else ""
                vtype = type_map.get(col, "String")
                if val == "":
                    values.append("NULL")
                elif vtype == "String":
                    values.append(f"'{val.replace(chr(39), chr(39)*2)}'")
                elif vtype in ("BigInt", "Double"):
                    values.append(val)
                elif vtype == "Boolean":
                    values.append(val.lower())
                elif vtype == "DateTime":
                    values.append(f"TIMESTAMP '{val}'")
                else:
                    values.append(f"'{val.replace(chr(39), chr(39)*2)}'")
            value_rows.append(f"({', '.join(values)})")

        sql = f"INSERT INTO {table} ({col_list}) VALUES {', '.join(value_rows)}"
        print(f"  Loading {len(rows)} rows into {table}...")
        livy.sql(sql)


if __name__ == "__main__":
    from config import FABRIC_WORKSPACE_ID
    from definition_builder import (
        make_entity_type, make_property, add_entity_type,
        get_entity_type, update_entity_type, list_entity_types,
        remove_entity_type, remove_data_binding,
        decode_definition, encode_definition, generate_id,
    )

    ONTOLOGY_ID = "332becaa-8a40-4d98-b1df-5be777480792"
    LAKEHOUSE_ID = "7c750a97-d839-4166-9ef7-177d2c1622d9"

    ont = OntologyClient()

    # === STEP 1: Design 3 entities with properties ===
    print("=" * 60)
    print("  STEP 1: Design 3 entities in the ontology")
    print("=" * 60)

    # Entity 1: TestChannel
    channel_name = make_property("ChannelName", "String")
    channel_subs = make_property("SubscriberCount", "BigInt")
    channel_active = make_property("IsActive", "Boolean")
    ch_id, ch_def = make_entity_type(
        "TestChannel",
        properties=[channel_name, channel_subs, channel_active],
        entity_id_parts=[channel_name["id"]],
        display_name_property_id=channel_name["id"],
    )

    # Entity 2: TestVideo
    video_title = make_property("Title", "String")
    video_views = make_property("ViewCount", "BigInt")
    video_duration = make_property("DurationSeconds", "Double")
    video_published = make_property("PublishedAt", "DateTime")
    vid_id, vid_def = make_entity_type(
        "TestVideo",
        properties=[video_title, video_views, video_duration, video_published],
        entity_id_parts=[video_title["id"]],
        display_name_property_id=video_title["id"],
    )

    # Entity 3: TestCommunity
    comm_name = make_property("CommunityName", "String")
    comm_members = make_property("MemberCount", "BigInt")
    comm_price = make_property("MonthlyPrice", "Double")
    comm_id, comm_def = make_entity_type(
        "TestCommunity",
        properties=[comm_name, comm_members, comm_price],
        entity_id_parts=[comm_name["id"]],
        display_name_property_id=comm_name["id"],
    )

    test_entities = [
        (ch_id, ch_def),
        (vid_id, vid_def),
        (comm_id, comm_def),
    ]

    # Push all 3 entities to the ontology in one go
    raw = ont.get_definition(ONTOLOGY_ID)
    parts = decode_definition(raw)
    for et_id, et_def in test_entities:
        parts = add_entity_type(parts, et_id, et_def)
    ont.update_definition(ONTOLOGY_ID, encode_definition(parts))
    print(f"Created 3 entities: TestChannel, TestVideo, TestCommunity")

    # Show table name convention
    for et_id, et_def in test_entities:
        print(f"  {et_def['name']} -> {entity_name_to_table(et_def['name'])}")

    with LivyClient(FABRIC_WORKSPACE_ID, LAKEHOUSE_ID) as livy:

        # === STEP 2: Sync all entities to Lakehouse ===
        print("\n" + "=" * 60)
        print("  STEP 2: Sync all entities (batch)")
        print("=" * 60)

        entity_ids = [et_id for et_id, _ in test_entities]
        results = sync_all_entities(ont, ONTOLOGY_ID, livy, LAKEHOUSE_ID,
                                    entity_ids=entity_ids)

        # Verify tables
        print("\nVerify tables:")
        for et_id, info in results.items():
            print(f"\n  --- {info['table']} ---")
            print(livy.sql(f"DESCRIBE TABLE {info['table']}"))

        # === STEP 3: Add a property to TestVideo and re-sync all ===
        print("\n" + "=" * 60)
        print("  STEP 3: Add property to TestVideo, re-sync all")
        print("=" * 60)

        raw = ont.get_definition(ONTOLOGY_ID)
        parts = decode_definition(raw)
        video_entity = get_entity_type(parts, vid_id)
        video_entity["properties"].append({
            "id": generate_id(),
            "name": "LikeCount",
            "redefines": None,
            "baseTypeNamespaceType": None,
            "valueType": "BigInt",
        })
        parts = update_entity_type(parts, vid_id, video_entity)
        ont.update_definition(ONTOLOGY_ID, encode_definition(parts))
        print("Added 'LikeCount' property to TestVideo")

        results = sync_all_entities(ont, ONTOLOGY_ID, livy, LAKEHOUSE_ID,
                                    entity_ids=entity_ids)

        # Verify test_video now has LikeCount
        print("\nVerify test_video table:")
        print(livy.sql("DESCRIBE TABLE test_video"))

        # === CLEANUP ===
        print("\n" + "=" * 60)
        print("  CLEANUP")
        print("=" * 60)

        for et_id, info in results.items():
            livy.sql(f"DROP TABLE IF EXISTS {info['table']}")
            print(f"Dropped {info['table']}")

        raw = ont.get_definition(ONTOLOGY_ID)
        parts = decode_definition(raw)
        for et_id, info in results.items():
            parts = remove_data_binding(parts, et_id, info["binding_id"])
            parts = remove_entity_type(parts, et_id)
        ont.update_definition(ONTOLOGY_ID, encode_definition(parts))
        print("Removed all test entities and bindings from ontology")

        print("\nAll done.")
