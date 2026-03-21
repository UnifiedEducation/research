"""
Step-by-step CRUD tests against the Ontology REST API.

Tests entity types (create, read, update name/key/displayName, add properties, delete)
and relationship types (create, read, update, delete).

Each step: modify local parts -> push via update_definition -> get_definition to verify.
"""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clients"))
from ontology_client import OntologyClient
from definition_builder import (
    decode_definition, encode_definition, generate_id,
    make_entity_type, make_property,
    add_entity_type, get_entity_type, update_entity_type, remove_entity_type, list_entity_types,
    make_relationship_type,
    add_relationship_type, get_relationship_type, update_relationship_type,
    remove_relationship_type, list_relationship_types,
)

client = OntologyClient()

# We'll use the first ontology in the workspace
ONTOLOGY_ID = None


def setup():
    global ONTOLOGY_ID
    ontologies = client.list_ontologies()
    if not ontologies:
        print("No ontologies found")
        sys.exit(1)
    ONTOLOGY_ID = ontologies[0]["id"]
    print(f"Using ontology: {ontologies[0]['displayName']} ({ONTOLOGY_ID})")


def get_parts() -> list[dict]:
    """Fetch and decode the current definition."""
    raw = client.get_definition(ONTOLOGY_ID)
    return decode_definition(raw)


def push_parts(parts: list[dict]):
    """Encode and push the definition back to the API."""
    encoded = encode_definition(parts)
    client.update_definition(ONTOLOGY_ID, encoded)


def step(name: str):
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


def show_entities(parts: list[dict]):
    entities = list_entity_types(parts)
    print(f"  Entity types ({len(entities)}):")
    for e in entities:
        key_parts = e.get("entityIdParts", [])
        display = e.get("displayNamePropertyId")
        props = [f"{p['name']}({p['valueType']})" for p in e.get("properties", [])]
        print(f"    - {e['name']} (id={e['id']})")
        print(f"      key={key_parts}, displayName={display}")
        print(f"      props: {', '.join(props)}")


def show_relationships(parts: list[dict]):
    rels = list_relationship_types(parts)
    print(f"  Relationship types ({len(rels)}):")
    for r in rels:
        print(f"    - {r['name']} (id={r['id']})")
        print(f"      {r['source']['entityTypeId']} -> {r['target']['entityTypeId']}")


def pause():
    print()


# =============================================================================
# TESTS
# =============================================================================

def test_entity_create():
    step("1. CREATE ENTITY TYPE")
    parts = get_parts()
    print("\n  Before:")
    show_entities(parts)

    # Create a new entity type with properties
    name_prop = make_property("CustomerName", "String")
    email_prop = make_property("Email", "String")
    joined_prop = make_property("JoinedDate", "DateTime")
    active_prop = make_property("IsActive", "Boolean")

    et_id, et_def = make_entity_type(
        "TestCustomer",
        properties=[name_prop, email_prop, joined_prop, active_prop],
        entity_id_parts=[name_prop["id"]],
        display_name_property_id=name_prop["id"],
    )

    parts = add_entity_type(parts, et_id, et_def)
    print(f"\n  Pushing new entity type: TestCustomer (id={et_id})...")
    push_parts(parts)

    # Verify
    parts = get_parts()
    print("\n  After:")
    show_entities(parts)

    return et_id


def test_entity_read(et_id: str):
    step("2. READ ENTITY TYPE")
    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    print(f"\n  Entity: {entity['name']}")
    print(f"  Full definition:")
    print(json.dumps(entity, indent=4))


def test_entity_update_name(et_id: str):
    step("3. UPDATE ENTITY TYPE - rename")
    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    old_name = entity["name"]
    entity["name"] = "TestCustomerRenamed"
    parts = update_entity_type(parts, et_id, entity)
    print(f"\n  Renaming: {old_name} -> {entity['name']}...")
    push_parts(parts)

    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    print(f"  Verified: name is now '{entity['name']}'")


def test_entity_update_key(et_id: str):
    step("4. UPDATE ENTITY TYPE - change key (entityIdParts)")
    parts = get_parts()
    entity = get_entity_type(parts, et_id)

    # Change key to Email property instead of CustomerName
    email_prop = next(p for p in entity["properties"] if p["name"] == "Email")
    old_key = entity["entityIdParts"]
    entity["entityIdParts"] = [email_prop["id"]]
    parts = update_entity_type(parts, et_id, entity)
    print(f"\n  Changing key from {old_key} to [{email_prop['id']}] (Email)...")
    push_parts(parts)

    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    print(f"  Verified: entityIdParts = {entity['entityIdParts']}")


def test_entity_update_display_name(et_id: str):
    step("5. UPDATE ENTITY TYPE - change displayNamePropertyId")
    parts = get_parts()
    entity = get_entity_type(parts, et_id)

    email_prop = next(p for p in entity["properties"] if p["name"] == "Email")
    old_display = entity["displayNamePropertyId"]
    entity["displayNamePropertyId"] = email_prop["id"]
    parts = update_entity_type(parts, et_id, entity)
    print(f"\n  Changing displayNamePropertyId from {old_display} to {email_prop['id']} (Email)...")
    push_parts(parts)

    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    print(f"  Verified: displayNamePropertyId = {entity['displayNamePropertyId']}")


def test_entity_add_properties(et_id: str):
    step("6. UPDATE ENTITY TYPE - add properties")
    parts = get_parts()
    entity = get_entity_type(parts, et_id)

    print(f"\n  Before: {len(entity['properties'])} properties")
    for p in entity["properties"]:
        print(f"    - {p['name']} ({p['valueType']})")

    # Add two new properties
    new_props = [
        {"id": generate_id(), "name": "PhoneNumber", "redefines": None,
         "baseTypeNamespaceType": None, "valueType": "String"},
        {"id": generate_id(), "name": "MonthlySpend", "redefines": None,
         "baseTypeNamespaceType": None, "valueType": "Double"},
    ]
    entity["properties"].extend(new_props)
    parts = update_entity_type(parts, et_id, entity)
    print(f"\n  Adding PhoneNumber (String) and MonthlySpend (Double)...")
    push_parts(parts)

    parts = get_parts()
    entity = get_entity_type(parts, et_id)
    print(f"\n  After: {len(entity['properties'])} properties")
    for p in entity["properties"]:
        print(f"    - {p['name']} ({p['valueType']})")


def test_entity_delete(et_id: str):
    step("7. DELETE ENTITY TYPE")
    parts = get_parts()
    print(f"\n  Before: {len(list_entity_types(parts))} entity types")

    parts = remove_entity_type(parts, et_id)
    print(f"  Removing TestCustomerRenamed (id={et_id})...")
    push_parts(parts)

    parts = get_parts()
    print(f"  After: {len(list_entity_types(parts))} entity types")
    entity = get_entity_type(parts, et_id)
    print(f"  Verified: entity exists = {entity is not None}")


def test_relationship_create() -> tuple[str, str, str]:
    step("8. CREATE RELATIONSHIP TYPE")
    parts = get_parts()

    # Create two small entity types to relate
    a_id_prop = make_property("AId", "String")
    a_id, a_def = make_entity_type("TestEntityA", properties=[a_id_prop],
                                    entity_id_parts=[a_id_prop["id"]])
    parts = add_entity_type(parts, a_id, a_def)

    b_id_prop = make_property("BId", "String")
    b_id, b_def = make_entity_type("TestEntityB", properties=[b_id_prop],
                                    entity_id_parts=[b_id_prop["id"]])
    parts = add_entity_type(parts, b_id, b_def)

    # Create relationship A -> B
    rt_id, rt_def = make_relationship_type("ArelatestoB", a_id, b_id)

    parts = add_relationship_type(parts, rt_id, rt_def)
    print(f"\n  Creating: TestEntityA --ArelatestoB--> TestEntityB...")
    push_parts(parts)

    parts = get_parts()
    show_entities(parts)
    show_relationships(parts)

    return rt_id, a_id, b_id


def test_relationship_read(rt_id: str):
    step("9. READ RELATIONSHIP TYPE")
    parts = get_parts()
    rel = get_relationship_type(parts, rt_id)
    print(f"\n  Relationship: {rel['name']}")
    print(f"  Full definition:")
    print(json.dumps(rel, indent=4))


def test_relationship_update(rt_id: str):
    step("10. UPDATE RELATIONSHIP TYPE - rename")
    parts = get_parts()
    rel = get_relationship_type(parts, rt_id)
    old_name = rel["name"]
    rel["name"] = "AcontainsB"
    parts = update_relationship_type(parts, rt_id, rel)
    print(f"\n  Renaming: {old_name} -> {rel['name']}...")
    push_parts(parts)

    parts = get_parts()
    rel = get_relationship_type(parts, rt_id)
    print(f"  Verified: name is now '{rel['name']}'")


def test_relationship_delete(rt_id: str, a_id: str, b_id: str):
    step("11. DELETE RELATIONSHIP TYPE (and cleanup test entities)")
    parts = get_parts()
    print(f"\n  Before: {len(list_relationship_types(parts))} relationships, "
          f"{len(list_entity_types(parts))} entities")

    # Remove relationship first, then the test entities
    parts = remove_relationship_type(parts, rt_id)
    parts = remove_entity_type(parts, a_id)
    parts = remove_entity_type(parts, b_id)
    print(f"  Removing AcontainsB, TestEntityA, TestEntityB...")
    push_parts(parts)

    parts = get_parts()
    print(f"  After: {len(list_relationship_types(parts))} relationships, "
          f"{len(list_entity_types(parts))} entities")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    setup()

    # Entity CRUD
    et_id = test_entity_create()
    pause()
    test_entity_read(et_id)
    pause()
    test_entity_update_name(et_id)
    pause()
    test_entity_update_key(et_id)
    pause()
    test_entity_update_display_name(et_id)
    pause()
    test_entity_add_properties(et_id)
    pause()
    test_entity_delete(et_id)
    pause()

    # Relationship CRUD
    rt_id, a_id, b_id = test_relationship_create()
    pause()
    test_relationship_read(rt_id)
    pause()
    test_relationship_update(rt_id)
    pause()
    test_relationship_delete(rt_id, a_id, b_id)

    print(f"\n{'=' * 60}")
    print("  ALL TESTS COMPLETE")
    print(f"{'=' * 60}")
