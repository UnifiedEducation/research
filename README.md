# Fabric Ontology & Graph Research

> **Warning:** This code is experimental and has not been tested or validated beyond initial research. It exists solely to test hypotheses about Microsoft Fabric Ontologies and Graph. **Use at your own risk.**

## Overview

A research repository exploring Microsoft Fabric's Ontology and Graph Model APIs. The work covers ontology definition, lakehouse sync, and GQL query capabilities through a series of 55 tested hypotheses (50 pass, 5 fail).

## Repository Structure

```
research/
├── ontology/
│   ├── clients/               # Python API wrapper libraries
│   │   ├── auth.py            # Azure OAuth2 token acquisition (client credentials)
│   │   ├── config.py          # Environment config loader (.env)
│   │   ├── ontology_client.py # Fabric Ontology REST API wrapper
│   │   ├── graph_client.py    # Fabric Graph Model REST API wrapper
│   │   ├── livy_client.py     # Fabric Livy API for Spark SQL execution
│   │   ├── definition_builder.py # Ontology definition encode/decode & CRUD helpers
│   │   └── lakehouse_sync.py  # Lakehouse table creation, schema sync & bindings
│   │
│   ├── docs/                  # Research findings & reference material
│   │   ├── ontology-feasibility-research-report.md  # Full research report (55 hypotheses)
│   │   └── gql-syntax-reference.md                  # Fabric GQL syntax guide
│   │
│   ├── e2e-workflow-tests/    # Data-driven end-to-end test framework
│   │   ├── runner.py          # Test orchestrator (--setup / --validate / --cleanup)
│   │   ├── case-01-online-courses/  # Test case: online learning platform
│   │   │   ├── ontology.json        # Entity & relationship definitions
│   │   │   ├── competency-questions.md
│   │   │   ├── seed-data/           # CSV test data
│   │   │   └── gql-queries/         # GQL queries (cq01–cq07)
│   │   └── README.md
│   │
│   └── tests/                 # Unit & integration tests
│       ├── test_crud.py       # Ontology entity/relationship CRUD workflow
│       ├── test_graph.py      # GQL query validation
│       ├── test_refresh.py    # Graph refresh API testing
│       └── test_auto_refresh.py # Schema-change auto-refresh testing
└── README.md
```

## Tooling

| Tool                    | Purpose                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------ |
| `ontology_client.py`    | CRUD operations against the Fabric Ontology REST API                                       |
| `graph_client.py`       | Graph model queries, refresh, and status via REST API                                      |
| `livy_client.py`        | Spark SQL execution through the Fabric Livy API                                            |
| `definition_builder.py` | Base64 encode/decode of ontology definitions, entity & relationship manipulation           |
| `lakehouse_sync.py`     | Creates/alters Lakehouse Delta tables to match ontology entities and manages bindings      |
| `runner.py`             | End-to-end test orchestrator: provisions ontology, loads data, runs GQL queries, cleans up |

## Configuration

Requires a `.env` file with:

```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
FABRIC_WORKSPACE_ID=...
FABRIC_LAKEHOUSE_ID=...
```

## Key Findings

- Ontology CRUD, lakehouse sync, and GQL queries all work end-to-end via the REST API.
- **Graph refresh cannot be triggered programmatically** — the API returns `InvalidJobType`; only the Fabric UI works.
- Entities without `entityIdParts` are silently excluded from the graph.
- Relationships require contextualizations (data bindings) to appear as graph edges.
- Only two parameters (`workspaceId`, `lakehouseId`) need swapping for DEV-to-PROD promotion.

See `ontology/docs/ontology-feasibility-research-report.md` for the full research report.
