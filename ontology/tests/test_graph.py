"""Test GQL queries against the auto-provisioned graph model."""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "clients"))
from graph_client import GraphClient

GM_ID = "f8c9a893-b106-4d26-bea8-dfee710bd694"
gc = GraphClient()


def run_query(label, gql):
    """Run a GQL query and print a compact result."""
    print(f"\n--- {label} ---")
    print(f"  GQL: {gql}")
    result = gc.execute_query(GM_ID, gql)
    status = result.get("status", {})
    code = status.get("code", "?")
    desc = status.get("description", "?")
    data = result.get("result", {}).get("data", [])
    cols = result.get("result", {}).get("columns", [])

    if code != "00000":
        cause = status.get("cause", {})
        print(f"  STATUS: {code} - {desc}")
        if cause:
            print(f"  CAUSE: {cause.get('description', cause)}")
        return None

    print(f"  STATUS: OK ({len(data)} rows)")
    for row in data:
        print(f"    {row}")
    return data


print("=" * 60)
print("  GQL QUERY TESTS")
print("=" * 60)

# --- Basic node queries ---
run_query("All Library nodes", "MATCH (n:`Library`) RETURN n.LibraryID, n.Location, n.NoOfFloors LIMIT 10;")
run_query("All Book nodes", "MATCH (n:`Book`) RETURN n.BookID, n.BookName, n.BookAuthor LIMIT 10;")

# --- Aggregation ---
run_query("COUNT Libraries", "MATCH (n:`Library`) RETURN COUNT(n) AS cnt;")
run_query("COUNT Books", "MATCH (n:`Book`) RETURN COUNT(n) AS cnt;")

# --- WHERE filter ---
run_query("Library in London", "MATCH (n:`Library`) WHERE n.Location = 'London' RETURN n.LibraryID, n.Location, n.NoOfFloors;")
run_query("Books by Alice Zhang", "MATCH (n:`Book`) WHERE n.BookAuthor = 'Alice Zhang' RETURN n.BookID, n.BookName;")

# --- Boolean filter ---
run_query("Closed libraries", "MATCH (n:`Library`) WHERE n.closed = true RETURN n.LibraryID, n.Location;")
run_query("Current books", "MATCH (n:`Book`) WHERE n.IsCurrent = true RETURN n.BookID, n.BookName;")

# --- Numeric comparison ---
run_query("Libraries with 3+ floors", "MATCH (n:`Library`) WHERE n.NoOfFloors >= 3 RETURN n.LibraryID, n.NoOfFloors;")

# --- Return all properties (TO_JSON_STRING) ---
run_query("Library as JSON", "MATCH (n:`Library`) RETURN TO_JSON_STRING(n) AS lib LIMIT 1;")
run_query("Book as JSON", "MATCH (n:`Book`) RETURN TO_JSON_STRING(n) AS book LIMIT 1;")

# --- ORDER BY ---
run_query("Libraries ordered by floors DESC", "MATCH (n:`Library`) RETURN n.LibraryID, n.NoOfFloors ORDER BY n.NoOfFloors DESC;")

# --- Edge traversal (expect empty - no edges configured yet) ---
run_query("Edge traversal attempt", "MATCH (l:`Library`)-[r]->(b:`Book`) RETURN l.LibraryID, b.BookName LIMIT 5;")

print("\n" + "=" * 60)
print("  DONE")
print("=" * 60)
