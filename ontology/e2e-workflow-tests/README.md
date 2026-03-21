# E2E Ontology Workflow Tests

End-to-end tests validating the full ontology lifecycle:
**Competency Questions -> Ontology Definition -> Lakehouse Tables + Bindings -> GQL Validation**

## How It Works

Each `case-*` folder is a self-contained data package (no Python code):

```
case-01-online-courses/
  competency-questions.md    # Domain description + CQs
  ontology.json              # Entities, properties, relationships
  seed-data/                 # One CSV per entity type
  gql-queries/               # One .gql file per competency question
```

The shared `runner.py` orchestrates everything using the existing `clients/` modules.

## Usage

Three phases (graph refresh is manual between setup and validate):

```bash
# 1. Create ontology, tables, seed data, bindings, contextualizations
python runner.py case-01-online-courses --setup

# 2. Manually refresh the graph in Fabric UI:
#    - Open the auto-provisioned graph model
#    - Click "Refresh now" in the Schedule panel
#    - Wait for refresh to complete

# 3. Run GQL queries to validate competency questions
python runner.py case-01-online-courses --validate

# 4. Clean up when done (optional)
python runner.py case-01-online-courses --cleanup
```

### Batch operations

```bash
python runner.py --all --setup
python runner.py --all --cleanup
```

### Manual graph ID override

If the graph model can't be auto-detected:

```bash
python runner.py case-01-online-courses --validate --graph-id <graph-model-id>
```

## Adding a New Case

1. Create a `case-NN-name/` folder
2. Write `competency-questions.md` describing the domain and CQs
3. Create `ontology.json` with entities, properties, and relationships
4. Create `seed-data/{EntityName}.csv` for each entity (3-8 rows)
5. Create `gql-queries/cqNN.gql` for each competency question

### ontology.json format

```json
{
  "name": "E2E_CNN_DomainName",
  "description": "Brief description",
  "tablePrefix": "e2e_cNN",
  "entities": [
    {
      "name": "EntityName",
      "keyProperty": "EntityNameID",
      "properties": [
        {"name": "EntityNameID", "valueType": "String"},
        {"name": "otherProp", "valueType": "String"}
      ]
    }
  ],
  "relationships": [
    {
      "name": "relName",
      "source": "SourceEntity",
      "target": "TargetEntity"
    }
  ]
}
```

### Key conventions

- **keyProperty**: The property used as entity key AND display name
- **tablePrefix**: Prevents table collisions across cases (e.g., `e2e_c01`)
- **FK columns**: Include source entity key as a property in target entities
  (e.g., Course entity has InstructorID property for the teaches relationship)
- **contextEntity** (optional): Override which entity's table is used for the
  contextualization. Defaults to the target entity. Needed when the FK lives
  in a junction entity, not the target (e.g., Enrollment -> Course uses
  Enrollment table, not Course table)
- **Seed CSV names**: Must match entity names exactly (e.g., `Course.csv`)
- **Value types**: String, BigInt, Double, Boolean, DateTime

## Why Graph Refresh Is Manual

Programmatic refresh via API returns `InvalidJobType` for ontology-managed
graphs (auto-provisioned under an ontology). Only the Fabric UI "Refresh now"
button works. See `docs/ontology-feasibility-test-results.md` Hypothesis 39.
