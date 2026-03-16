---
name: data-analyzer
description: Profiles existing Unity Catalog tables — schema metadata, column stats, sample rows, and inferred relationships. Invoked by /create-team when --catalog/--schema flags are provided or PRD references existing tables.
---

# Data Analyzer

You are profiling Unity Catalog tables to give downstream agents real schema
metadata, column statistics, sample data, and inferred relationships.

## Input

- **catalog** — Unity Catalog catalog name (required)
- **schema** — Unity Catalog schema/database name (required)
- **max_tables** — maximum number of tables to profile (default: 50)

## Step 1: List Tables

Execute the following SQL using `mcp__databricks-mcp__execute_sql`:

```sql
SHOW TABLES IN {catalog}.{schema}
```

Collect the list of table names. If the count exceeds `max_tables`, cap the
list at `max_tables` and emit a warning:

```
WARNING: {total_count} tables found in {catalog}.{schema}; profiling only the
first {max_tables}. Increase --max-tables to profile more.
```

## Step 2: Profile Each Table

For each table in the capped list, perform the following sub-steps. Track
status per table: `profiled`, `partial` (timeout), `error` (permission or not
found), `skipped` (over limit).

### 2a: Get table details

Call `mcp__databricks-mcp__get_table_details` with:

```
full_name: {catalog}.{schema}.{table}
```

Extract: description, column names, column types, column descriptions,
nullable flags, and any UC tags attached to the table.

### 2b: Run column-level profiling SQL

For each column, run profiling SQL via `mcp__databricks-mcp__execute_sql`.
Enforce a 30-second timeout per table — if the query does not complete, mark
the table as `partial` and record an `error_message`.

For tables with more than 1,000,000 rows, add `TABLESAMPLE (1000 ROWS)` to
keep profiling fast:

```sql
SELECT
  COUNT(*)                                    AS row_count,
  COUNT(DISTINCT {col})                       AS distinct_count,
  ROUND(SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 4)
                                              AS null_rate,
  MIN({col})                                  AS min_val,
  MAX({col})                                  AS max_val
FROM {catalog}.{schema}.{table}
-- TABLESAMPLE (1000 ROWS)  ← add this line when row_count > 1000000
```

Run this per column, or combine columns into a single query if the warehouse
supports it — prefer fewer round-trips.

### 2c: Get sample rows

```sql
SELECT * FROM {catalog}.{schema}.{table} LIMIT 5
```

Capture up to 5 rows as a list of dictionaries `{column: value}`.

### 2d: Assign table status

| Condition | Status |
|-----------|--------|
| All sub-steps succeeded | `profiled` |
| Profiling SQL timed out (>30s) | `partial` |
| Permission denied or table not found | `error` |
| Table index exceeded max_tables | `skipped` |

## Step 3: Infer Relationships

Scan all profiled tables for potential foreign-key style relationships:

1. **`_id` suffix heuristic** — for any column named `{X}_id`, check whether
   a table named `{X}` or `{X}s` exists in the profiled set. If so, record an
   inferred relationship with `confidence: medium`.

2. **Shared column names** — for columns that appear in more than one table
   with the same name and compatible types (e.g., `customer_id` in both
   `orders` and `customers`), record an inferred relationship with
   `confidence: high` when one side is a likely primary key (high distinct
   count relative to row count).

3. **Declared foreign keys** — if Unity Catalog metadata surfaces explicit
   foreign key constraints, mark those as `type: foreign_key` with
   `confidence: high`.

## Step 4: Write Output

Write the profile to `.agent-team/artifacts/data-profile.yaml` using the
following schema exactly:

```yaml
catalog: <name>
schema: <name>
profiled_at: <ISO 8601 timestamp, e.g. 2026-03-16T14:30:00Z>
tables:
  - name: <table_name>
    description: <description from UC, or null>
    status: profiled | partial | error | skipped
    error_message: <populated only when status is error or partial>
    row_count: <integer>
    columns:
      - name: <column_name>
        type: <Spark SQL type, e.g. STRING, BIGINT, TIMESTAMP>
        description: <description from UC, or null>
        nullable: <true | false>
        null_rate: <float, 0.0–1.0>
        distinct_count: <integer>
        min: <value or null>
        max: <value or null>
    sample_rows:
      - {col1: val1, col2: val2}
    tags: {key: value}
relationships:
  - from_table: <table_name>
    from_column: <column_name>
    to_table: <table_name>
    to_column: <column_name>
    type: inferred | foreign_key
    confidence: high | medium | low
```

Create the `.agent-team/artifacts/` directory if it does not already exist.

## Failure Modes

| Failure | Handling |
|---------|----------|
| MCP tool unavailable | Skip the affected table with a warning; continue profiling remaining tables. If MCP is fully unavailable, write an empty `tables: []` profile and emit a top-level warning. |
| Table not found | Mark table `status: error`, set `error_message: "Table not found"` |
| Permission denied | Mark table `status: error`, set `error_message: "Permission denied"` |
| Slow query (>30s) | Mark table `status: partial`, set `error_message: "Profiling timed out after 30s"`. Proceed to sample-rows step regardless. |
| Too many tables | Profile up to `max_tables`, mark remaining as `status: skipped`. Emit warning (see Step 1). |
