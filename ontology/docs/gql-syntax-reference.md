# Fabric GQL Syntax Reference

GQL (Graph Query Language) as implemented in Microsoft Fabric's Graph Model
(preview, March 2026). Documented from feasibility testing against live APIs.

## Critical Syntax Rules

### 1. Labels MUST be backtick-quoted

```gql
-- CORRECT
MATCH (n:`Course`) RETURN n.title;

-- WRONG (error: label expression does not match any node type)
MATCH (n:Course) RETURN n.title;
```

Fabric GQL requires backtick quoting for all node and edge type labels.
Unquoted labels silently fail to match any node type.

### 2. String literals use single quotes

```gql
-- CORRECT
MATCH (n:`Course`) WHERE n.topic = 'Programming' RETURN n.title;

-- WRONG
MATCH (n:`Course`) WHERE n.topic = "Programming" RETURN n.title;
```

### 3. Queries end with a semicolon

```gql
-- CORRECT
MATCH (n:`Course`) RETURN n.title LIMIT 1;

-- May fail without it
MATCH (n:`Course`) RETURN n.title LIMIT 1
```

## API Endpoint

```
POST /v1/workspaces/{workspaceId}/graphModels/{graphModelId}/executeQuery?beta=true
Content-Type: application/json

{"query": "MATCH (n:`Book`) RETURN n.BookID LIMIT 1;"}
```

The `beta=true` query parameter is required.

## Response Format

### Success (code "00000")

```json
{
  "status": {
    "code": "00000",
    "description": "Success"
  },
  "result": {
    "columns": [
      {"name": "c.CourseID", "gqlType": "STRING", "jsonType": "string"},
      {"name": "c.title", "gqlType": "STRING", "jsonType": "string"}
    ],
    "data": [
      {"c.CourseID": "C001", "c.title": "Intro to Python"},
      {"c.CourseID": "C003", "c.title": "Web Development"}
    ]
  }
}
```

- `columns` is an array of objects with `name`, `gqlType`, and `jsonType`
- `data` is an array of row objects keyed by column name (not positional arrays)
```

### Error

```json
{
  "status": {
    "code": "42000",
    "description": "error: syntax error or access rule violation",
    "cause": {
      "code": "22000",
      "description": "error: data exception; The label expression (Course) does not match any node type."
    }
  }
}
```

The `cause.description` field contains the actual diagnostic - always check it.

## Proven Query Patterns

All patterns below were tested and confirmed working against live Fabric APIs.

### Basic node query

```gql
MATCH (n:`Library`) RETURN n.LibraryID, n.Location, n.NoOfFloors LIMIT 10;
```

### COUNT aggregation

```gql
MATCH (n:`Book`) RETURN COUNT(n) AS cnt;
```

### WHERE filter (string equality)

```gql
MATCH (n:`Library`) WHERE n.Location = 'London' RETURN n.LibraryID, n.Location;
```

### WHERE filter (boolean)

```gql
MATCH (n:`Library`) WHERE n.closed = true RETURN n.LibraryID;
```

### WHERE filter (numeric comparison)

```gql
MATCH (n:`Library`) WHERE n.NoOfFloors >= 3 RETURN n.LibraryID, n.NoOfFloors;
```

### ORDER BY

```gql
MATCH (n:`Library`) RETURN n.LibraryID, n.NoOfFloors ORDER BY n.NoOfFloors DESC;
```

### LIMIT

```gql
MATCH (n:`Book`) RETURN n.BookID LIMIT 5;
```

### Full node as JSON

```gql
MATCH (n:`Library`) RETURN TO_JSON_STRING(n) AS lib LIMIT 1;
```

### Edge traversal

```gql
MATCH (l:`Library`)-[r]->(b:`Book`) RETURN l.LibraryID, b.BookName LIMIT 5;
```

### Named edge type traversal

```gql
MATCH (l:`Library`)-[r:`hasBook`]->(b:`Book`) RETURN l.LibraryID, b.BookName;
```

### Multi-hop traversal

```gql
MATCH (s:`Student`)-[:`hasEnrollment`]->(e:`Enrollment`)-[:`enrolledIn`]->(c:`Course`)
WHERE s.name = 'Alice'
RETURN c.CourseID, c.title;
```

### GROUP BY (explicit required)

```gql
-- CORRECT: GROUP BY references RETURN aliases (not dotted property refs)
MATCH (e:`Enrollment`)-[:`enrolledIn`]->(c:`Course`)
RETURN c.CourseID AS CourseID, c.title AS title, COUNT(e) AS enrollmentCount
GROUP BY CourseID, title;

-- WRONG: dotted property refs in GROUP BY (syntax error on '.')
MATCH (e:`Enrollment`)-[:`enrolledIn`]->(c:`Course`)
RETURN c.CourseID, c.title, COUNT(e) AS enrollmentCount
GROUP BY c.CourseID, c.title;
-- Error: "mismatched input '.' expecting {<EOF>, WHITESPACE}"

-- WRONG: no GROUP BY at all (Cypher-style implicit grouping)
MATCH (e:`Enrollment`)-[:`enrolledIn`]->(c:`Course`)
RETURN c.CourseID, c.title, COUNT(e) AS enrollmentCount;
-- Error: "The identifier 'c.CourseID' cannot be used, as it is neither
--         part of the GROUP BY nor an aggregation"
```

Key rules:
- Unlike Cypher, Fabric GQL does NOT implicitly group by non-aggregated columns
- Every non-aggregated column in RETURN must appear in an explicit GROUP BY clause
- GROUP BY comes AFTER RETURN (not before it like in SQL)
- GROUP BY must reference RETURN **aliases**, not dotted property references (`c.prop`)

## Not Yet Tested

- HAVING
- Subqueries
- OPTIONAL MATCH
- Edge property queries
- CREATE / SET / DELETE (mutation operations)
- Variable-length paths (e.g., `-[*1..3]->`)
- UNION / INTERSECT

## Common Pitfalls

| Mistake | Error | Fix |
|---------|-------|-----|
| Unquoted labels `(n:Foo)` | "label expression does not match any node type" | Use backticks: `` (n:`Foo`) `` |
| Double-quoted strings `"val"` | Syntax error | Use single quotes: `'val'` |
| Missing semicolon | May cause silent failure | Always end with `;` |
| Query before graph refresh | "GraphIsNotLoaded" | Refresh graph from Fabric UI first |
| Querying empty graph | Empty queryable schema | Ensure data bindings + contextualizations are pushed before refresh |
| Missing GROUP BY with aggregation | "identifier cannot be used, as it is neither part of the GROUP BY nor an aggregation" | Add explicit `GROUP BY` with RETURN aliases |
| Dotted refs in GROUP BY `GROUP BY c.id` | "mismatched input '.' expecting {<EOF>}" | Use RETURN aliases: `RETURN c.id AS id ... GROUP BY id` |

## Graph Refresh Requirements

- Programmatic refresh via API does NOT work for ontology-managed graphs (returns `InvalidJobType`)
- Must use Fabric UI: Graph Model -> Schedule panel -> "Refresh now"
- After ontology definition changes, a new refresh is required
- `queryReadiness: "Full"` in the graph model metadata confirms the graph is loaded
- But `getQueryableGraphType` returning empty `nodeTypes`/`edgeTypes` means data wasn't loaded
