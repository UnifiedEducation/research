"""Test: Does an ontology schema change auto-trigger a graph refresh?

Strategy: Add a simple entity type matching exact structure of existing ones,
then poll for new graph refresh jobs.
"""
import json
import os
import time
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clients"))

from ontology_client import OntologyClient
from definition_builder import (
    decode_definition, encode_definition, generate_id,
    list_entity_types, remove_entity_type,
)
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID
import requests
from auth import get_headers

ONT_ID = "332becaa-8a40-4d98-b1df-5be777480792"
GM_ID = "f8c9a893-b106-4d26-bea8-dfee710bd694"
WS_ID = FABRIC_WORKSPACE_ID

oc = OntologyClient()

def get_job_instances():
    url = f"{FABRIC_API_BASE}/workspaces/{WS_ID}/items/{GM_ID}/jobs/instances"
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    return resp.json().get("value", [])

print("=" * 60)
print("  TEST: SCHEMA CHANGE AUTO-REFRESH")
print("=" * 60)

# Step 1: Baseline
print("\n--- Step 1: Baseline job count ---")
baseline_jobs = get_job_instances()
baseline_count = len(baseline_jobs)
latest_job_id = baseline_jobs[0]["id"] if baseline_jobs else None
print(f"  Current job count: {baseline_count}")
print(f"  Latest job ID: {latest_job_id}")
print(f"  Latest job started: {baseline_jobs[0].get('startTimeUtc', '?') if baseline_jobs else '?'}")

# Step 2: Add entity - build manually to match exact structure
print("\n--- Step 2: Add dummy entity type ---")
raw_def = oc.get_definition(ONT_ID)
parts = decode_definition(raw_def)

dummy_et_id = generate_id()
prop_id = generate_id()

# Match exact structure of existing entity types
dummy_et_def = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/entityType/1.0.0/schema.json",
    "id": dummy_et_id,
    "namespace": "usertypes",
    "baseEntityTypeId": None,
    "name": "RefreshTest",
    "entityIdParts": [],
    "displayNamePropertyId": None,
    "namespaceType": "Custom",
    "visibility": "Visible",
    "properties": [
        {
            "id": prop_id,
            "name": "TestId",
            "redefines": None,
            "baseTypeNamespaceType": None,
            "valueType": "String",
        }
    ],
    "timeseriesProperties": [],
}

path = f"EntityTypes/{dummy_et_id}/definition.json"
parts.append({"path": path, "content": dummy_et_def})

print(f"  Adding entity: RefreshTest (id: {dummy_et_id})")
print(f"  Entities: {[et['name'] for et in list_entity_types(parts)]}")

encoded = encode_definition(parts)
try:
    oc.update_definition(ONT_ID, encoded)
    print("  Ontology definition pushed successfully.")
except Exception as e:
    print(f"  PUSH FAILED: {e}")
    # Try without the .platform part
    print("\n  Retrying without .platform part...")
    parts_no_platform = [p for p in parts if p["path"] != ".platform"]
    encoded = encode_definition(parts_no_platform)
    try:
        oc.update_definition(ONT_ID, encoded)
        print("  SUCCESS without .platform!")
    except Exception as e2:
        print(f"  ALSO FAILED: {e2}")
        print("\n  Cannot push changes. Aborting test.")
        sys.exit(1)

# Step 3: Poll for new job
print("\n--- Step 3: Polling for new graph refresh job ---")
print("  (Checking every 10s for up to 3 minutes)")

new_job_found = False
new_job = None
for i in range(18):
    time.sleep(10)
    current_jobs = get_job_instances()
    current_count = len(current_jobs)

    if current_count > baseline_count or (current_jobs and current_jobs[0]["id"] != latest_job_id):
        new_job = current_jobs[0]
        print(f"\n  NEW JOB DETECTED after {(i+1)*10}s!")
        print(f"    Job ID: {new_job['id']}")
        print(f"    Type: {new_job['jobType']}")
        print(f"    InvokeType: {new_job['invokeType']}")
        print(f"    Status: {new_job['status']}")
        print(f"    Started: {new_job.get('startTimeUtc', '?')}")
        new_job_found = True

        if new_job["status"] not in ("Completed", "Failed", "Cancelled"):
            print("  Waiting for job to complete...")
            for j in range(18):
                time.sleep(15)
                updated_jobs = get_job_instances()
                updated_job = next((x for x in updated_jobs if x["id"] == new_job["id"]), None)
                if updated_job:
                    print(f"    Status: {updated_job['status']}")
                    if updated_job["status"] in ("Completed", "Failed", "Cancelled"):
                        new_job = updated_job
                        if updated_job.get("failureReason"):
                            print(f"    Failure: {json.dumps(updated_job['failureReason'], indent=2)}")
                        break
        break
    else:
        print(f"  [{(i+1)*10}s] No new job yet (count: {current_count})")

if not new_job_found:
    print("\n  NO NEW JOB after 3 minutes.")

# Step 4: Clean up
print("\n--- Step 4: Clean up ---")
raw_def = oc.get_definition(ONT_ID)
parts = decode_definition(raw_def)
parts = remove_entity_type(parts, dummy_et_id)
print(f"  Entities after cleanup: {[et['name'] for et in list_entity_types(parts)]}")
encoded = encode_definition(parts)
oc.update_definition(ONT_ID, encoded)
print("  Cleanup complete.")

print("\n" + "=" * 60)
if new_job_found:
    print(f"  RESULT: Schema change DID auto-trigger graph refresh")
    print(f"  invokeType: {new_job.get('invokeType')}")
    print(f"  status: {new_job.get('status')}")
else:
    print("  RESULT: Schema change did NOT auto-trigger graph refresh")
print("=" * 60)
