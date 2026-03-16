# Agent Team Plugin — Three New Features Design Spec

**Date:** 2026-03-16
**Status:** Draft

## Overview

Three features extending the agent-team plugin:

1. **Data Catalog Analyzer** — Auto-profile existing UC tables during `/create-team`
2. **Incremental Feature Work** — `/add-feature` command for scoped changes to existing projects
3. **App UI Workflow Analyst** — New agent producing wireframes and UI specs before app-developer starts

---

## Feature 1: Data Catalog Analyzer

### Trigger

Activated automatically inside `/create-team` when:
- The PRD references existing tables/schemas, OR
- The user passes `--catalog <name> --schema <name>` flags

### New Skill: `skills/data-analyzer/SKILL.md`

Invoked by `/create-team` before `team-builder`.

**Algorithm:**

1. Detect table references in PRD text (regex for `catalog.schema.table` patterns, or explicit flags)
2. Connect to workspace via MCP tools:
   - `mcp__databricks-mcp__get_table_details` for each table
   - `mcp__databricks-mcp__execute_sql` for profiling queries
3. For each table in the schema:
   - **Schema metadata:** column names, types, descriptions, tags, partition columns
   - **Lightweight profiling:** row count, null rates per column, distinct counts, min/max for numeric columns
   - **Sample rows:** 5 representative rows via `SELECT * FROM table LIMIT 5`
4. Infer relationships:
   - Name-based: columns ending in `_id` matching other table names
   - FK constraints from UC metadata (if available)
   - Common columns across tables
5. Write output to `.agent-team/artifacts/data-profile.yaml`

### Failure Modes

- **MCP tools unavailable** (no Databricks connection): Skip profiling entirely, log a warning, proceed without `data-profile.yaml`. Team-builder infers schemas from PRD as before.
- **Tables not found** (typo or stale references): Mark table as `status: error` with reason, profile remaining tables.
- **Permission denied**: Mark table as `status: error`, continue with accessible tables.
- **Slow queries** (large tables): Cap profiling at 30 seconds per table. Use `TABLESAMPLE (1000 ROWS)` for sample rows on tables with >1M rows. If a profiling query times out, record `status: partial` with whatever completed.
- **Too many tables** (>50 in schema): Profile first 50, warn user. Accept `--max-tables N` flag to override.

### Output Schema: `data-profile.yaml`

```yaml
catalog: <catalog_name>
schema: <schema_name>
profiled_at: <ISO timestamp>

tables:
  - name: <table_name>
    description: <from UC metadata>
    status: profiled | partial | error | skipped
    error_message: <if status is error or partial>
    row_count: <int>
    columns:
      - name: <col_name>
        type: <spark_type>
        description: <from UC metadata>
        nullable: <bool>
        null_rate: <float 0-1>
        distinct_count: <int>
        min: <value>  # numeric/date only
        max: <value>
    sample_rows:
      - {col1: val1, col2: val2, ...}
      - ...
    tags: {key: value}

relationships:
  - from_table: <table>
    from_column: <column>
    to_table: <table>
    to_column: <column>
    type: inferred | foreign_key
    confidence: high | medium | low
```

### Changes to Existing Files

- **`commands/create-team.md`** — Add optional `--catalog` and `--schema` flags. When present (or detected from PRD), invoke `data-analyzer` skill before `team-builder`. Pass the data-profile.yaml path to team-builder.
- **`skills/team-builder/SKILL.md`** — If `data-profile.yaml` exists, incorporate it into:
  - Agent context (all agents see real table schemas)
  - Contract definitions (use actual column names/types instead of inferred ones)
  - Data-engineer prompt (profile informs ingestion strategy)
- **`agents/pm-orchestrator.md`** — Include data profile in contract resolution context for Phase 1+ agents.

---

## Feature 2: Incremental Feature Work

### New Command: `commands/add-feature.md`

**Usage:**
```
/add-feature "add CSV export to chat history"
/add-feature features/csv-export.md
```

Auto-detects file path vs inline text: check if the argument resolves to an existing file first. If the file exists, treat as file path. Otherwise, treat as inline text regardless of extension.

### New Skill: `skills/feature-scoper/SKILL.md`

Invoked by `/add-feature`. Responsible for analyzing the existing project and scoping the work.

**Algorithm:**

#### Step 1: Discover Current State

Read the codebase to build a project snapshot:

```yaml
project_snapshot:
  structure:
    src_dirs: [list of src/ subdirectories with descriptions]
    resources: [list of resource files]
    tests: [list of test directories]
    dab_config: {summary of databricks.yml}

  history:
    original_team: {from .agent-team/team-manifest.yaml}
    introspection: {from CLAUDE.md ## Introspection section}
    contracts: {from .agent-team/contracts/*.yaml}
    known_issues: [patterns from introspection that are still relevant]

  architecture:
    data_tables: [tables referenced in code]
    endpoints: [serving endpoints]
    app_routes: [API routes from backend]
    frontend_pages: [React components/routes]
```

#### Step 2: Analyze Feature Request

- Parse the feature description
- Map to capability tags (reuse team-builder's tag table)
- Diff against existing capabilities — what's new vs what's an extension of existing code

#### Step 3: Smart Agent Scoping

Select only needed agents:

| Capability Touched | Agents Selected |
|---|---|
| Data ingestion/transformation | data-engineer |
| GenAI/RAG/embeddings | genai-architect |
| UI/frontend/backend | app-developer |
| ML training/serving | data-scientist |
| UI/UX design changes | ui-ux-analyst |
| Resource config changes | deploy-engineer |
| Always included | qa-engineer |

Skip all others. No domain SME for incremental work (domain is already established).

#### Step 4: Generate Scoped `.agent-team/` Config

Archive the existing configuration, then write a new scoped config:

1. If `.agent-team/team-manifest.yaml` exists, copy it to `.agent-team/team-manifest.previous.yaml`
2. Write new `.agent-team/` configuration with:
   - `team-manifest.yaml` with `mode: incremental`, `feature_description` field, and `previous_manifest: team-manifest.previous.yaml`
   - Only the selected agents in `agents/` (keep existing agent files, add/update only the needed ones)
   - Only the needed phases (collapsed — e.g., if only app-developer + qa-engineer, just 2 phases)
   - Contracts reference existing artifacts as read-only inputs from prior work
   - `project_snapshot` embedded in manifest for agent context
3. Reset `status/progress.yaml` for the new feature's phases (prior phase history preserved in git)

If no `.agent-team/` directory exists (project built manually without the plugin), build the project snapshot from code analysis alone — skip history reading, set `history: null` in the snapshot.

#### Step 5: Hand Off to `/start-team`

`/add-feature` invokes `/start-team` after writing the config. `/start-team` detects `mode: incremental` in the manifest and:
- Skips DAB scaffolding (project already exists)
- Skips git init (already a repo)
- Proceeds directly to PM orchestrator dispatch

This avoids duplicating dispatch logic between `/add-feature` and `/start-team`.

### Rollback

Since the PM orchestrator commits after each phase, failed incremental work can be rolled back:

```bash
# Find the commit before /add-feature started
git log --oneline | grep "checkpoint: phase"

# Revert all incremental commits
git revert --no-commit <first-incremental-commit>..HEAD
git commit -m "rollback: revert feature '<feature_description>'"
```

The `/add-feature` command should tag the starting commit with `feature-start/<slug>` to make rollback easy.

### Changes to Existing Files

- **`agents/pm-orchestrator.md`** — When manifest has `mode: incremental`:
  - Pass project snapshot as context to all agents
  - Agents receive "you are modifying an existing project" framing
  - Introspection captures feature-specific learnings
- **`skills/team-builder/SKILL.md`** — Accept optional `project_snapshot` input; when present, use it to inform contract definitions

### Phase Scoping Rules

For incremental work, phases collapse based on selected agents:

- If only 1 agent type (+ QA): single implementation phase + QA
- If 2+ agents with dependencies: preserve dependency order but skip unused phases
- Deploy phase included only if `resources/` or `databricks.yml` changes are expected

---

## Feature 3: App UI Workflow Analyst

### New Agent: `agents/ui-ux-analyst.md`

```yaml
name: ui-ux-analyst
display_name: UI/UX Analyst
model: sonnet
tools: Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, WebSearch, WebFetch
```

**Role:** Design application user experience — workflows, wireframes, and component specifications — informed by domain research.

**Skills Used:** `ui-ux-pro-max` for style selection, palette, typography, wireframe generation. This is an existing skill from the superpowers plugin marketplace — it is a prerequisite dependency, not built as part of this spec.

### New Template: `templates/core/ui-ux-analyst.yaml`

```yaml
name: ui-ux-analyst
display_name: UI/UX Analyst
description: Designs app UX workflows, wireframes, and component specs
model: sonnet
registered_agent: agents/ui-ux-analyst.md
typical_phases: [1]

capabilities:
  - ui-design
  - ux-workflow
  - wireframing
  - frontend-planning

skills:
  - ui-ux-pro-max

mcp_tools: []

output_paths:
  - .agent-team/artifacts/ui-workflow.md
  - .agent-team/artifacts/ui-wireframes/
  - .agent-team/artifacts/ui-component-contract.yaml
```

### Agent Behavior

**Inputs:**
- Domain playbook (`.agent-team/artifacts/domain-playbook.md`) — required, from Phase 0 SME
- PRD features related to user interaction
- Data profile (`.agent-team/artifacts/data-profile.yaml`) — optional, from Feature 1 data-analyzer
- Existing wireframes (`.agent-team/artifacts/ui-wireframes/`) — optional, for incremental mode

**Process:**
1. Analyze the domain playbook for user-facing workflows
2. Invoke `ui-ux-pro-max` skill to:
   - Define user personas and journeys
   - Create screen inventory
   - Design navigation flow
   - Select visual style, color palette, typography
   - Generate HTML wireframe mockups per screen
3. Produce structured component contract

**Outputs:**

#### `.agent-team/artifacts/ui-workflow.md`
```markdown
# UI/UX Workflow Specification

## User Personas
- Persona 1: [role, goals, pain points]

## User Journeys
- Journey 1: [step-by-step flow]

## Screen Inventory
| Screen | Purpose | Key Components | Data Needed |
|--------|---------|----------------|-------------|

## Navigation Flow
[text-based flow diagram]

## Interaction Patterns
- [pattern: description]

## Visual Design Decisions
- Style: [chosen from ui-ux-pro-max catalog]
- Palette: [colors]
- Typography: [fonts]
```

#### `.agent-team/artifacts/ui-wireframes/`
Directory of HTML files, one per screen. Viewable in browser. Generated via `ui-ux-pro-max` skill.

#### `.agent-team/artifacts/ui-component-contract.yaml`
```yaml
pages:
  - name: <page_name>
    route: <url_path>
    components:
      - name: <component_name>
        type: <form | list | chart | card | modal | ...>
        data_source: <api_endpoint or prop>
        props:
          - name: <prop_name>
            type: <string | number | array | object>
    api_endpoints:
      - method: <GET | POST>
        path: <api_path>
        request_schema: {fields}
        response_schema: {fields}
```

### New Contract: `ui-to-app`

```yaml
name: ui-to-app
producer: ui-ux-analyst
consumer: app-developer
optional_inputs:
  - path: .agent-team/artifacts/data-profile.yaml
    description: Data profile from catalog analyzer (informs data-aware UI design)
artifacts:
  - path: .agent-team/artifacts/ui-workflow.md
    description: User journeys, screen inventory, navigation flow
  - path: .agent-team/artifacts/ui-wireframes/
    description: HTML wireframe mockups per screen
  - path: .agent-team/artifacts/ui-component-contract.yaml
    description: Structured page/component/API spec
validation:
  - type: artifact_exists
    description: All UI spec artifacts exist
```

### Contract Consumption Phase

The `ui-to-app` contract is consumed by app-developer in **Phase 2** (its first invocation, where it builds the UI shell). Phase 3 (integration) focuses on wiring, not UI design. The PM orchestrator must resolve the `ui-to-app` contract in Phase 2 context, not Phase 3.

### Incremental Mode Behavior

When `mode: incremental` and ui-ux-analyst is selected (e.g., `/add-feature "add a settings page"`):

1. **Receive existing artifacts as read-only context:** ui-workflow.md, ui-wireframes/, ui-component-contract.yaml
2. **Produce additive outputs:**
   - New wireframe files added to `ui-wireframes/` (e.g., `settings.html`), existing files untouched
   - `ui-component-contract.yaml` extended with new pages/components appended, existing entries preserved
   - `ui-workflow.md` updated with new journeys/screens added to existing sections
3. **App-developer receives a diff annotation:** The updated component contract includes a `status: new | modified | unchanged` field per page so the app-developer knows what to implement vs what already exists

### Artifact Path Isolation

Phase 1 parallel agents (data-engineer and ui-ux-analyst) must write to non-overlapping paths:
- data-engineer: `src/ingestion/`, `src/transformations/`, `resources/pipelines.yml`
- ui-ux-analyst: `.agent-team/artifacts/ui-*`

Neither agent writes to the other's output paths. The PM orchestrator should validate this before merge.

### Phase Structure Impact

When `ui-design` or `web-app` capabilities are detected AND a domain SME is selected, the phase-planner places ui-ux-analyst in the same phase as data-engineer (they have no dependency on each other):

```
Phase 0: domain-sme (haiku)
Phase 1: data-engineer (sonnet) || ui-ux-analyst (sonnet)  — parallel
Phase 2: genai-architect (opus) || app-developer (sonnet)  — parallel
Phase 3: app-developer (sonnet) — integration
Phase 4: deploy-engineer (sonnet) → qa-engineer (sonnet)
```

No new phases added — the dependency graph naturally puts ui-ux-analyst alongside data-engineer.

### Changes to Existing Files

- **`skills/team-builder/SKILL.md`** — Add `ui-design`, `ux-workflow`, `wireframing`, `frontend-planning` to capability tag table. When matched AND domain SME exists, select ui-ux-analyst. Wire `ui-to-app` contract.
- **`agents/app-developer.md`** — Add optional inputs: ui-workflow.md, ui-wireframes/, ui-component-contract.yaml. When present, app-developer codes against wireframes and component contract.
- **`skills/phase-planner/SKILL.md`** — No changes needed (dependency graph handles parallel placement automatically).

---

## New File Inventory

| File | Type | Feature |
|------|------|---------|
| `skills/data-analyzer/SKILL.md` | skill | F1 |
| `commands/add-feature.md` | command | F2 |
| `skills/feature-scoper/SKILL.md` | skill | F2 |
| `agents/ui-ux-analyst.md` | agent | F3 |
| `templates/core/ui-ux-analyst.yaml` | template | F3 |

## Modified File Inventory

| File | Features |
|------|----------|
| `commands/create-team.md` | F1 |
| `skills/team-builder/SKILL.md` | F1, F2, F3 |
| `agents/pm-orchestrator.md` | F1, F2 |
| `agents/app-developer.md` | F3 |
| `commands/start-team.md` | F2 (handle `mode: incremental`) |

---

## Test Scenarios

### Feature 1 Test
```
/create-team test/qa-chatbot-prd.md --catalog vdm_classic_rikfy0_catalog --schema qa_chatbot_dev
```
Expected: data-profile.yaml produced with table schemas, profiling stats, sample rows. Downstream agents reference real column names.

### Feature 2 Test
```
/add-feature "add a feedback thumbs up/down button to each assistant response, store feedback in a Delta table"
```
Expected: Only app-developer + data-engineer + deploy-engineer + qa-engineer selected. 3 phases instead of 5. Agents receive full project snapshot.

### Feature 3 Test
```
/create-team test/qa-chatbot-prd.md
```
Expected: ui-ux-analyst selected (PRD has web-app + frontend capabilities). Runs parallel with data-engineer in Phase 1. Produces wireframes. App-developer in Phase 2 references wireframe mockups and component contract.
