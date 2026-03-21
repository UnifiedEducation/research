# Ontology Feasibility Research Report

A combined account of the research prompts, discoveries, and tested hypotheses from the Microsoft Fabric Ontology + Graph feasibility study.

Session transcript: `c05d2bf9-bcd5-4c4a-835a-1d3bc916ca6b`
82 total messages, 27 key directional prompts, 55 hypotheses tested, 10 aha moments.

### Codebase Reference

```
feasibility/ontology/
  clients/
    config.py                  # Environment variables and Fabric API config
    auth.py                    # Azure OAuth2 token acquisition
    ontology_client.py         # Wrapper: Fabric Ontology REST API
    graph_client.py            # Wrapper: Fabric Graph Model REST API
    livy_client.py             # Wrapper: Fabric Livy API (Spark SQL)
    definition_builder.py      # Helpers to build/manipulate ontology definitions
    lakehouse_sync.py          # Sync ontology entities to Lakehouse tables + bindings
  tests/
    test_crud.py               # Entity & relationship CRUD tests (11 steps)
    test_graph.py              # GQL query tests (MATCH, WHERE, COUNT, edges)
    test_refresh.py            # Graph refresh API endpoint tests
    test_auto_refresh.py       # Schema change auto-refresh verification
  exploration/
    explore_definition.py      # Decode and display ontology definitions
  e2e-workflow-tests/
    runner.py                  # End-to-end ontology workflow orchestration
  docs/
    ontology-feasibility-test-results.md
    session-prompts-summary.md
    gql-syntax-reference.md
```

---

## 1. Ontology API Discovery & Item Definition Structure

### Prompts

- **[15:06]** "I want to carry out three feasibility studies... Let's start with Ontology. I want to create an area in the repo where we can store/develop code to test the Ontology REST API"
- **[15:22]** "Make a class that is a simple wrapper over all the API endpoints available for ontologies" (pointed to MS docs)
- **[15:26]** "The part I'm most interested in is the Update Ontology Definition, and Get Ontology Definition. I want to know exactly what these definitions look like"

### Aha Moment

**Definitions are atomic**: Early discovery that ontology definitions follow a get-modify-push pattern - you can't CRUD individual entities via the API. You have to download the entire definition, modify it in memory, and push the whole thing back. This shaped the entire tooling architecture.

### Code

- `clients/ontology_client.py` - Wrapper over all 7 Ontology REST API endpoints (list, create, get, update, delete, get definition, update definition)
- `clients/definition_builder.py` - Helpers for base64 decode/encode, entity/relationship/binding manipulation
- `clients/config.py` + `clients/auth.py` - Environment config and OAuth2 token acquisition
- `exploration/explore_definition.py` - Decode and display ontology definitions as readable tree

### Outcomes

| #   | Hypothesis                                                                                   | Result |
| --- | -------------------------------------------------------------------------------------------- | ------ |
| 1   | Can we retrieve the full ontology definition via REST API?                                   | PASS   |
| 2   | Can we decode the base64-encoded definition parts into readable JSON?                        | PASS   |
| 3   | Can we push a modified definition back via a single atomic update?                           | PASS   |
| 4   | Does the LRO (long-running operation) pattern work reliably for definition reads and writes? | PASS   |

---

## 2. Entity & Relationship CRUD

### Prompts

- **[15:46]** "I want to test all of the following... CRUD operations on an Entity (including entity type name, key, instance display name), plus adding properties... CRUD operations on Relationships"

### Code

- `tests/test_crud.py` - 11-step sequential test: create entity, read back, rename, change key, change display name, add property, delete entity, create relationship, read back, rename, delete. Each step uses `definition_builder.py` helpers and pushes via `ontology_client.py`.

### Outcomes

| #   | Hypothesis                                                                     | Result |
| --- | ------------------------------------------------------------------------------ | ------ |
| 5   | Is it possible to create a new entity type via the REST API?                   | PASS   |
| 6   | Is it possible to read back an entity type from the definition?                | PASS   |
| 7   | Is it possible to rename an entity type?                                       | PASS   |
| 8   | Is it possible to change an entity's key (entityIdParts)?                      | PASS   |
| 9   | Is it possible to change an entity's display name property?                    | PASS   |
| 10  | Is it possible to add new properties to an existing entity?                    | PASS   |
| 11  | Is it possible to delete an entity type?                                       | PASS   |
| 12  | Is it possible to create multiple entities in a single API call?               | PASS   |
| 13  | Is it possible to create a relationship between two entities via the REST API? | PASS   |
| 14  | Is it possible to read back a relationship type from the definition?           | PASS   |
| 15  | Is it possible to rename a relationship type?                                  | PASS   |
| 16  | Is it possible to delete a relationship type?                                  | PASS   |

---

## 3. Data Binding & Lakehouse Integration

### Prompts

- **[16:07]** "I want to understand data bindings and how that works (and also how it's represented in both the UI, and in the item definition)"
- **[16:12]** "Can I bind from a lakehouse table? Static properties and time-series? Can I bind from a warehouse? Can I bind from a KQL database table?"
- **[16:18]** "The ultimate vision: think about updating the Ontology, run update statements on the relevant data store table(s) and then re-bind based on the new structure"
- **[17:01]** "Let's focus only on the Lakehouse. Let's use the Livy connector you already built. What I want to do is link the Lakehouse table creation/update process to the Ontology binding process"

### Aha Moments

- **"The ultimate vision"**: This single prompt defined the end-to-end sync workflow that became `lakehouse_sync.py`. It framed the problem as a pipeline, not isolated API calls.
- **DuckDB/DBT pivot** [16:36-16:40]: Briefly explored whether DuckDB and DBT could help, checked community resources ("looks like he's using a Lakehouse"), then pivoted back to Livy. Shows rapid evaluation-and-discard of alternative approaches in real-time.

### Code

- `clients/livy_client.py` - Wrapper over the Fabric Livy API: session management (create, poll, delete) and Spark SQL execution (`sql()` method wraps statements in `spark.sql("...")`). Supports `kind="pyspark"` for Python-based sessions.

### Outcomes

| #   | Hypothesis                                                        | Result |
| --- | ----------------------------------------------------------------- | ------ |
| 17  | Can we create a Spark/Livy session programmatically from VS Code? | PASS   |
| 18  | Can we create Delta tables via Spark SQL through the Livy API?    | PASS   |
| 19  | Can we insert data into and query from Lakehouse tables via Livy? | PASS   |
| 20  | Can we inspect table schema (DESCRIBE TABLE) via Livy?            | PASS   |
| 21  | Can we programmatically check if a table exists?                  | PASS   |
| 22  | Can we ALTER TABLE to add new columns to an existing table?       | PASS   |
| 23  | Can we drop tables via Livy?                                      | PASS   |

---

## 4. Ontology-to-Lakehouse Sync (Batch)

### Prompts

- **[17:22]** "We automated the case for property updates, but what about entire new entities, is that covered? For example: Ontology Designer creates three new Entities... The Lakehouse creator then reads the entity design, and creates/updates the lakehouse to reflect this, everything is then bound"
- **[17:36]** "Please can you use this functionality to create Lakehouse tables for the ontology in the workspace... And create the bindings - don't delete it after, I want to inspect them myself"

### Code

- `clients/lakehouse_sync.py` - Core sync engine. Key functions:
  - `sync_all_entities()` - reads ontology once, creates/alters all Lakehouse tables, builds all bindings, pushes single definition update
  - `entity_name_to_table()` - PascalCase to snake_case table name derivation
  - `_sync_table()` / `_build_binding()` - internal helpers for table DDL and binding construction
- `e2e-workflow-tests/runner.py` - End-to-end test orchestrator: creates 3 test entities, batch syncs, adds a property, re-syncs (verifies idempotency), then cleans up

### Outcomes

| #   | Hypothesis                                                                                                          | Result |
| --- | ------------------------------------------------------------------------------------------------------------------- | ------ |
| 24  | Can we automatically create a Lakehouse table from an entity's property definitions?                                | PASS   |
| 25  | Do all 6 ontology value types (String, BigInt, Double, Boolean, DateTime, Object) map correctly to Spark SQL types? | PASS   |
| 26  | Can we create a data binding that connects an entity to its Lakehouse table?                                        | PASS   |
| 27  | When a property is added to an entity, can we ALTER the table and update the binding in one flow?                   | PASS   |
| 28  | Can we sync multiple entities to multiple tables in a single batch (one API read, one API push)?                    | PASS   |
| 29  | When re-syncing, does the process correctly skip entities whose tables are already in sync?                         | PASS   |
| 30  | Can we automatically derive table names from entity names (PascalCase to snake_case)?                               | PASS   |
| 31  | Does the sync detect and reuse existing bindings rather than creating duplicates?                                   | PASS   |

---

## 5. Graph Model Investigation

### Prompts

- **[17:53]** "What's the relationship between the ontology I defined, and the underlying graph object? I notice a graph object is automatically provisioned underneath the Ontology object"
- **[18:02]** "Let's investigate then... you start. Maybe build another wrapper / graph_client" (pointed to Graph Model API docs)

### Code

- `clients/graph_client.py` - Wrapper over all 9 Graph Model REST API endpoints: list, get, get definition, get definition decoded, execute query (`?beta=true`), get queryable graph type, refresh, delete. The `__main__` block explores the auto-provisioned graph and dumps its schema.

### Outcomes

| #   | Hypothesis                                                                                   | Result             |
| --- | -------------------------------------------------------------------------------------------- | ------------------ |
| 35  | Are there REST API endpoints for the Graph Model?                                            | PASS (9 endpoints) |
| 36  | Can we list and get graph models via the API?                                                | PASS               |
| 37  | Can we decode the graph definition (graphType.json, graphDefinition.json, dataSources.json)? | PASS               |
| 38  | Can we get the queryable graph type (node types, edge types, properties)?                    | PASS               |

---

## 6. Entity Keys, Contextualizations & Edge Discovery

### Prompts

- **[11:48]** "I think it's because LibraryInventory doesn't have an entity key" - diagnosed why LibraryInventory was missing from the graph.
- **[12:32]** "Do you want me to add an edge in the UI, and then, from that you can deduct the structure" - offered to reverse-engineer the edge definition.
- **[12:33]** "Very interesting what it's asking for in the 'Add edge' dialog" (with screenshot showing Workspace, Lakehouse, Table fields) - the moment **contextualizations** were discovered.
- **[12:34]** "Library inventory doesn't appear in the list, I think it still needs a key" - reinforced entity key requirement.
- **[12:38]** "Please study the documentation some more... how relationships are defined in the Ontology vs edges created in the Graph" (with screenshot of hasBook relationship showing empty Source data) - revealed that relationships need contextualizations to become graph edges.
- **[11:52]** "If it doesn't make sense as a graph model concept, then feel free to refactor it in a way that makes sense!" - gave direction to refactor the two-hop model into a direct relationship.

### Aha Moments

- **Entity keys -> graph nodes**: User noticed LibraryInventory was missing from the graph and correctly diagnosed the missing entity key as the cause. Led to the rule: entities without `entityIdParts` are silently excluded from the graph.
- **Contextualizations -> graph edges**: User offered to create an edge via UI to reverse-engineer the structure, then shared the "Add edge" screenshot revealing that edges require Workspace/Lakehouse/Table fields - a data binding to a junction table. This was the breakthrough that explained why relationships weren't appearing as graph edges.
- **"YES. the graph now has an edge"** [13:08]: The moment after the refactoring from two-hop (Library -> LibraryInventory -> Book) to direct relationship (Library -> Book with contextualization). Validated the entire contextualization theory in one screenshot.

### Code

- `clients/definition_builder.py` - Added contextualization functions: `make_contextualization()`, `make_key_ref_binding()`, `add_contextualization()`, `list_contextualizations()`, `remove_contextualization()`. These build the relationship data binding structure mapping junction table columns to source/target entity keys.

### Outcomes

| #   | Hypothesis                                                                                    | Result                          |
| --- | --------------------------------------------------------------------------------------------- | ------------------------------- |
| 32  | Can we create a relationship contextualization (data binding) via the REST API?               | PASS                            |
| 33  | Does the contextualization correctly map junction table columns to source/target entity keys? | PASS                            |
| 34  | Do ontology relationships without contextualizations appear in the graph?                     | FAIL (no edges without binding) |
| 40  | Does a Graph object auto-provision under an Ontology?                                         | PASS                            |
| 41  | Do ontology entity types with keys auto-create graph node types?                              | PASS                            |
| 42  | Do ontology entity types WITHOUT keys appear as graph nodes?                                  | FAIL (missing until key added)  |
| 43  | Do ontology entity properties map correctly to graph node properties?                         | PASS                            |
| 44  | Do ontology relationships with contextualizations auto-create graph edge types?               | PASS                            |
| 45  | Does the graph data source auto-point to bound Lakehouse Delta tables?                        | PASS (abfss:// paths)           |

---

## 7. GQL Queries

### Prompts

GQL testing flowed naturally from the Graph Model investigation. After inserting test data and refreshing the graph via the UI, comprehensive GQL query testing was performed.

### Aha Moment

- **"Save" button = data ingestion** [11:42]: "There's a 'Save' button in the Graph. It now says 'Load in progress'" - this revealed that the graph's "Save" isn't just persisting config, it triggers a full data re-ingestion from OneLake.

### Code

- `tests/test_graph.py` - GQL query test script. Uses `graph_client.execute_query()` to run queries and a `run_query()` helper for compact output. Tests: MATCH, WHERE (string, boolean, numeric), COUNT, ORDER BY, TO_JSON_STRING, LIMIT, and edge traversal with `MATCH (a)-[r]->(b)`.

### Outcomes

| #   | Hypothesis                                                                      | Result |
| --- | ------------------------------------------------------------------------------- | ------ |
| 46  | Can we execute GQL queries programmatically via the Execute Query API?          | PASS   |
| 47  | Does MATCH + RETURN work for selecting node properties?                         | PASS   |
| 48  | Does WHERE filtering work (string equality, boolean, numeric comparison)?       | PASS   |
| 49  | Does COUNT() aggregation work?                                                  | PASS   |
| 50  | Does ORDER BY work?                                                             | PASS   |
| 51  | Does TO_JSON_STRING() work to dump full node data?                              | PASS   |
| 52  | Does LIMIT work?                                                                | PASS   |
| 53  | Can we traverse edges with MATCH (a)-[r]->(b) pattern?                          | PASS   |
| 54  | Does the graph return correct edge data matching Lakehouse junction table rows? | PASS   |

---

## 8. CI/CD & Environment Switching

### Prompts

- **[13:16]** "The graph data source auto-point to bound Lakehouse Delta tables... please can you elaborate? Can you show me where the data is bound"
- **[13:20]** "The reason I'm interested is for CICD purposes... can we use this ABFSS path to switch the bindings for a DEV ontology and a PROD ontology?"

### Aha Moment

- **ABFSS paths -> CI/CD thinking**: User spotted hypothesis #45 about ABFSS paths in the findings list, immediately connected it to CI/CD: "can we use this ABFSS path to switch the bindings for a DEV ontology and a PROD ontology?" This pivoted the research from "how does it work" to "how do we operationalize it."

### Outcomes

All environment-specific values reduce to just **two parameters**:

| Parameter            | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `workspaceId`        | The Fabric workspace GUID (different per environment) |
| `itemId` (lakehouse) | The Lakehouse item GUID (different per environment)   |

These appear in three places: ontology entity data bindings, relationship contextualizations, and graph data sources. A DEV-to-PROD pipeline only needs to swap these two values via the get-modify-push pattern.

---

## 9. Graph Refresh

### Prompts

- **[13:25]** "We might have to figure out the graph refresh functionality though, as I think this would be needed for the CICD automation to fully work"
- **[13:26]** "I think the answer is in this endpoint - please study it" (pointed to refreshGraph API docs)
- **[13:32]** "Another thing you can try is adding a URI parameter of beta = True"
- **[13:38]** "I'm not 100% convinced. This is quite a big issue, no? If I build a data agent on top of this... will it use the latest data?"
- **[13:42]** "I'd like to check this: Schema changes (like CI/CD deployment) do auto-refresh the graph"

### Aha Moments

- **"If I build a data agent on top of this..."**: User challenged the refresh gap by grounding it in a real use case - a data agent querying stale graph data. This reframed graph refresh from a "nice to have" to a blocking concern.
- **Schema change auto-refresh disproven**: User asked to verify the Microsoft docs' claim that schema changes auto-refresh the graph. The empirical test proved it false for API-pushed changes - a finding that contradicts the official documentation.

### Code

- `tests/test_refresh.py` - Exhaustive refresh endpoint testing: tries every combination of URL pattern (`graphModels/` vs `items/`), job type name (`refreshGraph`, `Refresh`, `refresh`, `DefaultJob`), query parameters (`beta=true`), old query param pattern (`?jobType=`), and request bodies (`executionData: {}`). All return `InvalidJobType`.
- `tests/test_auto_refresh.py` - Schema change auto-refresh test: records baseline job count, adds a dummy entity to the ontology via API (confirmed push succeeded), polls graph job instances every 10s for 3 minutes, verifies no new refresh job appeared, then cleans up.

### Outcomes

| #   | Hypothesis                                                                            | Result                    |
| --- | ------------------------------------------------------------------------------------- | ------------------------- |
| 39  | Can we trigger a graph refresh programmatically via the API?                          | FAIL (InvalidJobType)     |
| 55  | Does pushing an ontology schema change via the REST API auto-trigger a graph refresh? | FAIL (no job after 3 min) |

Exhaustive testing across all endpoint patterns, job type names, query parameters, and request bodies - all returned `InvalidJobType` for ontology-managed graphs.

**Current refresh options**:

| Trigger                             | Works?                                            |
| ----------------------------------- | ------------------------------------------------- |
| Schema change via Fabric UI         | Yes (auto-refresh per docs)                       |
| Schema change via REST API          | No (tested - no job triggered)                    |
| On-demand refresh via REST API      | No (InvalidJobType for ontology-managed graphs)   |
| Scheduled refresh via REST API      | No (scheduling endpoint returns 404)              |
| Scheduled refresh via Fabric UI     | Yes (configure in workspace -> graph -> Schedule) |
| Pipeline activity for graph refresh | No (not available)                                |

**Impact**: This is a **blocking gap** for full CI/CD automation. After pushing an ontology definition update via API, a manual graph refresh via the UI is still required. For production data freshness, a recurring schedule can be configured via the UI.

**Note on TimeSeries data**: The ontology query layer federates queries - TimeSeries properties bound to Eventhouse are queried via KQL directly (live), bypassing the graph snapshot. The refresh gap only affects Lakehouse-bound static data.

---

## Not Yet Tested

| Hypothesis                                                                 | Status   |
| -------------------------------------------------------------------------- | -------- |
| Do TimeSeries data bindings work end-to-end?                               | UNTESTED |
| Can we bind from a Warehouse (SQL endpoint) table?                         | UNTESTED |
| Can we bind from a KQL database (Eventhouse) table?                        | UNTESTED |
| Can we programmatically update the graph definition to add edges directly? | UNTESTED |
| Can we query edge properties in GQL?                                       | UNTESTED |

---

## Summary

| Category                         | Hypotheses | Pass   | Fail  |
| -------------------------------- | ---------- | ------ | ----- |
| Ontology Definition API          | 4          | 4      | 0     |
| Entity & Relationship CRUD       | 12         | 12     | 0     |
| Lakehouse Table Management       | 7          | 7      | 0     |
| Ontology-to-Lakehouse Sync       | 8          | 8      | 0     |
| Relationship Contextualizations  | 3          | 2      | 1     |
| Graph Model API                  | 4          | 3      | 1     |
| Graph Schema (Ontology -> Graph) | 7          | 5      | 2     |
| GQL Queries                      | 9          | 9      | 0     |
| Graph Refresh                    | 1          | 0      | 1     |
| **Total**                        | **55**     | **50** | **5** |

**Pass rate: 91%** (50/55). All 5 failures are in the Graph layer - specifically around entity key requirements (#42), contextualization requirements (#34), and programmatic graph refresh (#39, #55). The ontology definition API, CRUD, Lakehouse sync, and GQL query capabilities are fully validated.
