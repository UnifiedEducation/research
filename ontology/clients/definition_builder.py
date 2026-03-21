"""
Helpers to build and manipulate ontology definitions.

The ontology definition is a list of base64-encoded parts. This module provides
functions to work with decoded parts (plain dicts) and convert to/from the
API's base64 format.

All entity type IDs, property IDs, and relationship IDs are positive 64-bit
integers represented as strings.
"""
import base64
import json
import random


def generate_id() -> str:
    """Generate a random positive 64-bit integer ID as a string."""
    return str(random.randint(10**15, 10**18))


# -- Decode / Encode ----------------------------------------------------------

def decode_definition(raw: dict) -> list[dict]:
    """Decode an API definition response into a list of {path, content} dicts."""
    parts = raw.get("definition", {}).get("parts", [])
    decoded = []
    for part in parts:
        payload_b64 = part.get("payload", "")
        try:
            payload_str = base64.b64decode(payload_b64).decode("utf-8")
            content = json.loads(payload_str) if payload_str.strip() else {}
        except (json.JSONDecodeError, Exception):
            content = base64.b64decode(payload_b64).decode("utf-8", errors="replace")
        decoded.append({"path": part["path"], "content": content})
    return decoded


def encode_definition(parts: list[dict]) -> dict:
    """Encode a list of {path, content} dicts back into the API format."""
    encoded_parts = []
    for part in parts:
        content = part["content"]
        if isinstance(content, dict):
            payload_str = json.dumps(content)
        else:
            payload_str = str(content)
        payload_b64 = base64.b64encode(payload_str.encode("utf-8")).decode("ascii")
        encoded_parts.append({
            "path": part["path"],
            "payload": payload_b64,
            "payloadType": "InlineBase64",
        })
    return {"parts": encoded_parts}


# -- Entity Type operations ---------------------------------------------------

def make_entity_type(name: str, properties: list[dict] = None,
                     entity_id: str = None, entity_id_parts: list[str] = None,
                     display_name_property_id: str = None,
                     timeseries_properties: list[dict] = None) -> tuple[str, dict]:
    """
    Build an entity type definition.

    Returns (entity_type_id, definition_dict).

    Properties should be dicts with keys: name, valueType.
    IDs will be generated automatically if not provided.
    """
    et_id = entity_id or generate_id()
    props = []
    for p in (properties or []):
        props.append({
            "id": p.get("id", generate_id()),
            "name": p["name"],
            "redefines": None,
            "baseTypeNamespaceType": None,
            "valueType": p["valueType"],
        })

    definition = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/entityType/1.0.0/schema.json",
        "id": et_id,
        "namespace": "usertypes",
        "baseEntityTypeId": None,
        "name": name,
        "entityIdParts": entity_id_parts or [],
        "displayNamePropertyId": display_name_property_id,
        "namespaceType": "Custom",
        "visibility": "Visible",
        "properties": props,
        "timeseriesProperties": timeseries_properties or [],
    }
    return et_id, definition


def make_property(name: str, value_type: str, prop_id: str = None) -> dict:
    """Build a property dict for use in make_entity_type."""
    return {
        "id": prop_id or generate_id(),
        "name": name,
        "valueType": value_type,
    }


def add_entity_type(parts: list[dict], et_id: str, definition: dict) -> list[dict]:
    """Add an entity type to the parts list."""
    path = f"EntityTypes/{et_id}/definition.json"
    return parts + [{"path": path, "content": definition}]


def get_entity_type(parts: list[dict], et_id: str) -> dict | None:
    """Get an entity type definition from the parts list."""
    path = f"EntityTypes/{et_id}/definition.json"
    for part in parts:
        if part["path"] == path:
            return part["content"]
    return None


def update_entity_type(parts: list[dict], et_id: str, definition: dict) -> list[dict]:
    """Replace an entity type definition in the parts list."""
    path = f"EntityTypes/{et_id}/definition.json"
    return [
        {"path": p["path"], "content": definition} if p["path"] == path else p
        for p in parts
    ]


def remove_entity_type(parts: list[dict], et_id: str) -> list[dict]:
    """Remove an entity type and all its sub-parts (DataBindings, Documents, Overviews)."""
    prefix = f"EntityTypes/{et_id}/"
    return [p for p in parts if not p["path"].startswith(prefix)]


def list_entity_types(parts: list[dict]) -> list[dict]:
    """List all entity type definitions from the parts."""
    return [
        p["content"] for p in parts
        if "EntityTypes/" in p["path"]
        and p["path"].endswith("/definition.json")
        and "Overviews" not in p["path"]
    ]


# -- Relationship Type operations ---------------------------------------------

def make_relationship_type(name: str, source_entity_type_id: str,
                           target_entity_type_id: str,
                           relationship_id: str = None) -> tuple[str, dict]:
    """
    Build a relationship type definition.

    Returns (relationship_type_id, definition_dict).
    """
    rt_id = relationship_id or generate_id()
    definition = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/relationshipType/1.0.0/schema.json",
        "namespace": "usertypes",
        "id": rt_id,
        "name": name,
        "namespaceType": "Custom",
        "source": {"entityTypeId": source_entity_type_id},
        "target": {"entityTypeId": target_entity_type_id},
    }
    return rt_id, definition


def add_relationship_type(parts: list[dict], rt_id: str, definition: dict) -> list[dict]:
    """Add a relationship type to the parts list."""
    path = f"RelationshipTypes/{rt_id}/definition.json"
    return parts + [{"path": path, "content": definition}]


def get_relationship_type(parts: list[dict], rt_id: str) -> dict | None:
    """Get a relationship type definition from the parts list."""
    path = f"RelationshipTypes/{rt_id}/definition.json"
    for part in parts:
        if part["path"] == path:
            return part["content"]
    return None


def update_relationship_type(parts: list[dict], rt_id: str, definition: dict) -> list[dict]:
    """Replace a relationship type definition in the parts list."""
    path = f"RelationshipTypes/{rt_id}/definition.json"
    return [
        {"path": p["path"], "content": definition} if p["path"] == path else p
        for p in parts
    ]


def remove_relationship_type(parts: list[dict], rt_id: str) -> list[dict]:
    """Remove a relationship type and its contextualizations."""
    prefix = f"RelationshipTypes/{rt_id}/"
    return [p for p in parts if not p["path"].startswith(prefix)]


def list_relationship_types(parts: list[dict]) -> list[dict]:
    """List all relationship type definitions from the parts."""
    return [
        p["content"] for p in parts
        if "RelationshipTypes/" in p["path"]
        and p["path"].endswith("/definition.json")
    ]


# -- Contextualization operations (relationship data bindings) ----------------

def make_contextualization(workspace_id: str, lakehouse_id: str,
                           table_name: str,
                           source_key_bindings: list[dict],
                           target_key_bindings: list[dict],
                           source_schema: str = "dbo",
                           ctx_id: str = None) -> tuple[str, dict]:
    """
    Build a contextualization (relationship data binding).

    Contextualizations bind a junction/edge table to a relationship type,
    mapping columns to the source and target entity keys.

    source_key_bindings: [{"sourceColumnName": "col", "targetPropertyId": "id"}]
        Maps columns in the table to the SOURCE entity's key property IDs.

    target_key_bindings: [{"sourceColumnName": "col", "targetPropertyId": "id"}]
        Maps columns in the table to the TARGET entity's key property IDs.

    Returns (contextualization_id, definition_dict).
    """
    cid = ctx_id or generate_guid()
    definition = {
        "id": cid,
        "dataBindingTable": {
            "workspaceId": workspace_id,
            "itemId": lakehouse_id,
            "sourceTableName": table_name,
            "sourceSchema": source_schema,
            "sourceType": "LakehouseTable",
        },
        "sourceKeyRefBindings": source_key_bindings,
        "targetKeyRefBindings": target_key_bindings,
    }
    return cid, definition


def make_key_ref_binding(source_column: str, target_property_id: str) -> dict:
    """Build a key reference binding for a contextualization."""
    return {
        "sourceColumnName": source_column,
        "targetPropertyId": target_property_id,
    }


def add_contextualization(parts: list[dict], rt_id: str,
                          ctx_id: str, definition: dict) -> list[dict]:
    """Add a contextualization to a relationship type."""
    path = f"RelationshipTypes/{rt_id}/Contextualizations/{ctx_id}.json"
    return parts + [{"path": path, "content": definition}]


def list_contextualizations(parts: list[dict], rt_id: str = None) -> list[dict]:
    """List contextualizations. If rt_id given, list only for that relationship."""
    results = []
    for p in parts:
        if "/Contextualizations/" not in p["path"]:
            continue
        if rt_id and f"RelationshipTypes/{rt_id}/" not in p["path"]:
            continue
        results.append({"path": p["path"], "content": p["content"]})
    return results


def remove_contextualization(parts: list[dict], rt_id: str, ctx_id: str) -> list[dict]:
    """Remove a specific contextualization."""
    path = f"RelationshipTypes/{rt_id}/Contextualizations/{ctx_id}.json"
    return [p for p in parts if p["path"] != path]


# -- Data Binding operations --------------------------------------------------

def generate_guid() -> str:
    """Generate a UUID for data binding IDs."""
    import uuid
    return str(uuid.uuid4())


def make_lakehouse_binding(entity_type_id: str, property_bindings: list[dict],
                           workspace_id: str, lakehouse_id: str,
                           table_name: str, *,
                           binding_type: str = "NonTimeSeries",
                           timestamp_column: str = None,
                           source_schema: str = "dbo",
                           binding_id: str = None) -> tuple[str, dict]:
    """
    Build a Lakehouse data binding definition.

    property_bindings: list of {"sourceColumnName": "col", "targetPropertyId": "id"}
    binding_type: "NonTimeSeries" or "TimeSeries"
    timestamp_column: required if binding_type is "TimeSeries"

    Returns (binding_id, definition_dict).
    """
    bid = binding_id or generate_guid()
    config = {
        "dataBindingType": binding_type,
        "propertyBindings": property_bindings,
        "sourceTableProperties": {
            "sourceType": "LakehouseTable",
            "workspaceId": workspace_id,
            "itemId": lakehouse_id,
            "sourceTableName": table_name,
            "sourceSchema": source_schema,
        },
    }
    if binding_type == "TimeSeries":
        config["timestampColumnName"] = timestamp_column
    return bid, {"id": bid, "dataBindingConfiguration": config}


def make_warehouse_binding(entity_type_id: str, property_bindings: list[dict],
                           workspace_id: str, warehouse_id: str,
                           table_name: str, *,
                           source_schema: str = "dbo",
                           binding_id: str = None) -> tuple[str, dict]:
    """
    Build a Warehouse data binding definition.

    Warehouse bindings use the same LakehouseTable sourceType - the Fabric API
    treats SQL endpoint tables the same way. This is subject to validation
    during feasibility testing.

    Returns (binding_id, definition_dict).
    """
    bid = binding_id or generate_guid()
    config = {
        "dataBindingType": "NonTimeSeries",
        "propertyBindings": property_bindings,
        "sourceTableProperties": {
            "sourceType": "LakehouseTable",
            "workspaceId": workspace_id,
            "itemId": warehouse_id,
            "sourceTableName": table_name,
            "sourceSchema": source_schema,
        },
    }
    return bid, {"id": bid, "dataBindingConfiguration": config}


def make_kql_binding(entity_type_id: str, property_bindings: list[dict],
                     workspace_id: str, eventhouse_id: str,
                     cluster_uri: str, database_name: str,
                     table_name: str, *,
                     timestamp_column: str = None,
                     binding_id: str = None) -> tuple[str, dict]:
    """
    Build a KQL (Eventhouse) data binding definition.

    KQL bindings use sourceType "KustoTable" and are always TimeSeries.
    timestamp_column: required - the timestamp column in the KQL table.

    Returns (binding_id, definition_dict).
    """
    bid = binding_id or generate_guid()
    config = {
        "dataBindingType": "TimeSeries",
        "timestampColumnName": timestamp_column,
        "propertyBindings": property_bindings,
        "sourceTableProperties": {
            "sourceType": "KustoTable",
            "workspaceId": workspace_id,
            "itemId": eventhouse_id,
            "clusterUri": cluster_uri,
            "databaseName": database_name,
            "sourceTableName": table_name,
        },
    }
    return bid, {"id": bid, "dataBindingConfiguration": config}


def make_property_binding(source_column: str, target_property_id: str) -> dict:
    """Build a property binding mapping a source column to an entity property."""
    return {
        "sourceColumnName": source_column,
        "targetPropertyId": target_property_id,
    }


def add_data_binding(parts: list[dict], entity_type_id: str,
                     binding_id: str, definition: dict) -> list[dict]:
    """Add a data binding to an entity type."""
    path = f"EntityTypes/{entity_type_id}/DataBindings/{binding_id}.json"
    return parts + [{"path": path, "content": definition}]


def get_data_binding(parts: list[dict], entity_type_id: str,
                     binding_id: str) -> dict | None:
    """Get a specific data binding from the parts."""
    path = f"EntityTypes/{entity_type_id}/DataBindings/{binding_id}.json"
    for part in parts:
        if part["path"] == path:
            return part["content"]
    return None


def update_data_binding(parts: list[dict], entity_type_id: str,
                        binding_id: str, definition: dict) -> list[dict]:
    """Replace a data binding definition."""
    path = f"EntityTypes/{entity_type_id}/DataBindings/{binding_id}.json"
    return [
        {"path": p["path"], "content": definition} if p["path"] == path else p
        for p in parts
    ]


def remove_data_binding(parts: list[dict], entity_type_id: str,
                        binding_id: str) -> list[dict]:
    """Remove a specific data binding."""
    path = f"EntityTypes/{entity_type_id}/DataBindings/{binding_id}.json"
    return [p for p in parts if p["path"] != path]


def list_data_bindings(parts: list[dict], entity_type_id: str = None) -> list[dict]:
    """
    List data bindings. If entity_type_id is given, list only bindings for that entity.
    Otherwise list all bindings across all entities.
    """
    results = []
    for p in parts:
        if "/DataBindings/" not in p["path"]:
            continue
        if entity_type_id and f"EntityTypes/{entity_type_id}/" not in p["path"]:
            continue
        results.append({"path": p["path"], "content": p["content"]})
    return results


# -- High-level config-driven builders ----------------------------------------

def build_from_config(config: dict, table_namer=None):
    """
    Build an ontology definition from a config dict.

    Config format:
        entities:      [{name, keyProperty, displayProperty?, properties: [{name, valueType}]}]
        relationships: [{name, source, target, contextEntity?}]
        tablePrefix:   string prefix for Lakehouse table names

    table_namer: optional callable(entity_name) -> table_name. Defaults to
        "{tablePrefix}_{snake_case(name)}" using entity_name_to_table().

    Returns (parts, entity_map, relationship_map) where:
        parts:            list of {path, content} dicts ready for encode_definition
        entity_map:       {name: {id, key_prop_id, key_prop_name, prop_ids, table}}
        relationship_map: {name: {id, source, target, contextEntity}}
    """
    from lakehouse_sync import entity_name_to_table

    prefix = config.get("tablePrefix", "ont")
    if table_namer is None:
        def table_namer(name):
            return f"{prefix}_{entity_name_to_table(name)}"

    parts = [{"path": "definition.json", "content": {}}]
    entity_map = {}

    for entity_cfg in config["entities"]:
        name = entity_cfg["name"]
        key_prop_name = entity_cfg["keyProperty"]
        display_prop_name = entity_cfg.get("displayProperty", key_prop_name)

        properties = [
            make_property(p["name"], p["valueType"])
            for p in entity_cfg["properties"]
        ]

        key_prop_id = None
        display_prop_id = None
        for p in properties:
            if p["name"] == key_prop_name:
                key_prop_id = p["id"]
            if p["name"] == display_prop_name:
                display_prop_id = p["id"]

        if not key_prop_id:
            raise ValueError(
                f"Entity '{name}': keyProperty '{key_prop_name}' not in properties"
            )

        et_id, et_def = make_entity_type(
            name, properties=properties,
            entity_id_parts=[key_prop_id],
            display_name_property_id=display_prop_id,
        )
        parts = add_entity_type(parts, et_id, et_def)

        entity_map[name] = {
            "id": et_id,
            "key_prop_id": key_prop_id,
            "key_prop_name": key_prop_name,
            "prop_ids": {p["name"]: p["id"] for p in et_def["properties"]},
            "table": table_namer(name),
        }

    relationship_map = {}
    for rel_cfg in config["relationships"]:
        rel_name = rel_cfg["name"]
        source_name = rel_cfg["source"]
        target_name = rel_cfg["target"]
        context_entity = rel_cfg.get("contextEntity", target_name)

        rt_id, rt_def = make_relationship_type(
            rel_name,
            entity_map[source_name]["id"],
            entity_map[target_name]["id"],
        )
        parts = add_relationship_type(parts, rt_id, rt_def)

        relationship_map[rel_name] = {
            "id": rt_id,
            "source": source_name,
            "target": target_name,
            "contextEntity": context_entity,
        }

    return parts, entity_map, relationship_map


def add_all_bindings(parts: list, entity_map: dict, entities_config: list,
                     workspace_id: str, lakehouse_id: str) -> list:
    """
    Add data bindings for all entities in one pass.

    entities_config: the "entities" list from the config dict.
    entity_map:      the map returned by build_from_config().
    """
    for entity_cfg in entities_config:
        name = entity_cfg["name"]
        info = entity_map[name]

        prop_bindings = [
            make_property_binding(p["name"], info["prop_ids"][p["name"]])
            for p in entity_cfg["properties"]
        ]

        bid, binding_def = make_lakehouse_binding(
            info["id"], prop_bindings,
            workspace_id, lakehouse_id, info["table"],
        )
        parts = add_data_binding(parts, info["id"], bid, binding_def)

    return parts


def add_all_contextualizations(parts: list, relationship_map: dict,
                                entity_map: dict,
                                workspace_id: str,
                                lakehouse_id: str) -> list:
    """
    Add contextualizations for all relationships in one pass.

    Uses entity key property names to auto-derive column mappings.
    The contextualization table is determined by each relationship's
    contextEntity (defaults to the target entity).
    """
    for rel_name, rel_info in relationship_map.items():
        source_info = entity_map[rel_info["source"]]
        target_info = entity_map[rel_info["target"]]
        context_info = entity_map[rel_info["contextEntity"]]

        source_bindings = [make_key_ref_binding(
            source_info["key_prop_name"], source_info["key_prop_id"]
        )]
        target_bindings = [make_key_ref_binding(
            target_info["key_prop_name"], target_info["key_prop_id"]
        )]

        ctx_id, ctx_def = make_contextualization(
            workspace_id, lakehouse_id, context_info["table"],
            source_bindings, target_bindings,
        )
        parts = add_contextualization(parts, rel_info["id"], ctx_id, ctx_def)

    return parts
