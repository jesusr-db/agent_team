---
name: team-builder
description: Analyzes a PRD to identify required capabilities and assemble an agent team. Invoked by /create-team.
---

## Optional Inputs

**`project_snapshot`** — when provided by the `feature-scoper` skill:

- **Use real names from existing code in contracts:**
  Use actual table names, column names, endpoint names, and artifact paths
  discovered from the codebase instead of inferring them from the PRD.
  These override any schema inferred from PRD text.

- **Skip fully-implemented capability tags:**
  If a capability tag is already implemented in the existing project
  (as indicated by `project_snapshot.history.contracts` or the previous
  manifest), do not generate a new agent or contract for it.
  Mark it as `status: existing` in the team roster.

- **Reference existing artifacts as read-only contract inputs:**
  For any producer→consumer contract where the producer artifact already
  exists in the project, set `access: read-only` on that contract input.
  This prevents agents from overwriting existing work and signals that the
  artifact is a stable dependency, not something to regenerate.

# Team Builder

You are assembling a team of AI agents to build a Databricks application.
Given a PRD document, you will analyze it and produce a complete team configuration.

## Step 1: Parse the PRD

Read the PRD document and extract:
- **Project description**: One-paragraph summary
- **Features**: List of features/capabilities the app needs
- **Data sources**: What data the app ingests or produces
- **User interactions**: How users interact with the app
- **Technical constraints**: Platform, performance, compliance requirements
- **Success criteria**: How to measure if the app works
- **Data profile** — if `.agent-team/artifacts/data-profile.yaml` exists,
  read it and use it as the authoritative source for real table schemas,
  column names and types, column statistics, sample data, and inferred
  relationships. This overrides any table structure inferred from PRD text
  alone.

## Step 2: Map to Capability Tags

Map each PRD requirement to one or more capability tags:

| Capability Tag | Triggered By |
|---------------|-------------|
| data-profiling | Existing data sources, tables, or schemas mentioned; --catalog/--schema provided; any ETL/ML/RAG requirement (always profile before building) |
| catalog-exploration | PRD references existing catalog/schema structure or asks to understand the data |
| data-ingestion | Any data loading, ETL, file processing |
| data-transformation | Data cleaning, feature engineering, aggregation |
| etl | Batch or streaming data pipelines |
| streaming | Real-time data processing |
| ml-training | Model training, experiment tracking |
| ml-serving | Model deployment, inference endpoints |
| feature-engineering | Feature store, feature tables |
| genai-rag | RAG pipelines, document Q&A, retrieval |
| genai-prompt-engineering | Prompt design, few-shot learning |
| vector-search | Embedding storage, similarity search |
| embeddings | Text/image embedding generation |
| llm-integration | LLM API calls, chain-of-thought |
| web-app | Web UI, dashboard, interactive app |
| api-backend | REST API, GraphQL, backend services |
| frontend | React, UI components, user experience |
| ui-design | UI mockups, wireframes, visual design |
| ux-workflow | User journeys, personas, interaction patterns |
| wireframing | Screen layouts, component placement |
| frontend-planning | Component architecture, page structure |
| databricks-app | Databricks Apps deployment |
| deployment | DAB configuration, CI/CD |
| domain:* | Industry-specific expertise (e.g., domain:retail, domain:healthcare) |

## Step 3: Select Curated Agents

For each capability tag, check if a curated template in `templates/core/` covers it.
Read each template's `capabilities` field to match.

**`data-discovery` selection rule:** Include `data-discovery` whenever ANY of
these conditions is true:
- `data-profiling` or `catalog-exploration` capability tag is present
- `--catalog/--schema` flags were passed to `/create-team`
- The PRD mentions existing tables, schemas, or data sources by name
- Any of these capability tags are present: `data-ingestion`, `data-transformation`,
  `etl`, `ml-training`, `genai-rag`, `vector-search`, `embeddings`
  (rationale: any agent that consumes data benefits from real schema context)

When selected, `data-discovery` always runs in **Phase 0**, before all
data-producing agents. Its outputs (`.agent-team/artifacts/data-profile.yaml`,
`sample_data/`, `data-dictionary.md`) are broadcast to ALL downstream agents
as read-only inputs — add a `broadcast` contract for it (see Step 6).

When `ui-design`, `ux-workflow`, `wireframing`, or `frontend-planning` is matched,
select the `ui-ux-analyst` template. Only select `ui-ux-analyst` when a domain SME
agent is also present on the team (it depends on the domain playbook as required input).

Always include these agents regardless of capabilities:
- **qa-engineer** (always needed for validation)
- **deploy-engineer** (always needed for deployment)

## Step 4: Generate Dynamic Specialists

For capability tags not covered by any curated template:
1. Read the appropriate meta-template from `templates/meta/`
   - `domain:*` tags → use `domain-sme-generator.yaml`
   - All other uncovered tags → use `specialist-generator.yaml`
2. Fill in the meta-template variables with PRD context
3. Generate the full agent definition
4. Write to `.agent-team/agents/<name>.md`

## Step 5: Design Phase Structure

Apply the phase structure algorithm:
1. `data-discovery` + Domain SME agents → Phase 0 (no dependencies, run in parallel if both present)
2. Data-producing agents → Phase 1 (depend on data-profile.yaml from Phase 0)
3. Agents consuming data outputs → Phase 2 (depend on Phase 1)
4. Integration work → Phase 3 (depends on all producers)
5. Deploy → Phase 4 (always last)

`data-discovery` and domain SME agents share Phase 0 and can run in the same
`parallel_group` — neither depends on the other.

Within each phase, group agents that don't depend on each other into
the same `parallel_group`.

Use the phase-planner skill for detailed dependency analysis.

## Step 6: Define Contracts

For each producer→consumer edge:
1. Read the producer's `outputs` and consumer's `inputs`
2. Generate a contract YAML following `lib/contract-schema.yaml` format
3. Include table schemas inferred from PRD data requirements
4. Include artifact paths from agent template `output_paths`
5. Include validation rules (schema_match, artifact_exists at minimum)
6. Mark uncertain columns as `required: false` — agents will refine
7. **If `.agent-team/artifacts/data-profile.yaml` is available:** use the
   actual column names and types from the profile instead of inferring them
   from the PRD. Mark every column sourced from the profile as
   `required: true`. For profiled tables, also propagate `null_rate`,
   `distinct_count`, and `row_count` into the contract as informational
   hints so consuming agents can plan accordingly.

**`data-discovery` broadcast contract** (add whenever `data-discovery` is on the team):
- Producer: `data-discovery`, Consumer: `broadcast` (all agents receive it)
- Artifacts:
  - `.agent-team/artifacts/data-profile.yaml` — machine-readable profile (schema, stats, quality flags)
  - `.agent-team/artifacts/sample_data/` — per-table CSV files (20 rows each)
  - `.agent-team/artifacts/data-dictionary.md` — human-readable reference
- `access: read-only` for all consumers
- `consumed_in_phase: 1` — all Phase 1+ agents receive it as context
- Validation: `artifact_exists` for all three paths
- When resolving contracts for any Phase 1+ agent, PM orchestrator must include
  the data-profile contents in the agent's prompt context (via `resolve_contracts`
  Step 2 in pm-orchestrator). This replaces PRD-inferred schemas with ground truth.

**`ui-to-app` contract pattern** (add when `ui-ux-analyst` is on the team):
- Producer: `ui-ux-analyst`, Consumer: `app-developer`
- Artifacts:
  - `.agent-team/artifacts/ui-workflow.md`
  - `.agent-team/artifacts/ui-wireframes/`
  - `.agent-team/artifacts/ui-component-contract.yaml`
- Optional input: `.agent-team/artifacts/data-profile.yaml`
- `consumed_in_phase: 2` — this is app-developer's first invocation, NOT Phase 3
- Validation: `artifact_exists`

## Step 7: Write .agent-team/ Directory

Write all files:
- `.agent-team/team-manifest.yaml` — team roster, phases, model tiers
- `.agent-team/agents/*.md` — one per agent (customized from templates)
- `.agent-team/phases/*.yaml` — one per phase
- `.agent-team/contracts/*.yaml` — one per producer→consumer edge
- `.agent-team/status/progress.yaml` — initialized with all phases pending
  - Each phase's `steps` must include: read_phase_config, resolve_contracts,
    dispatch_agents, await_agents, merge_worktrees, qa_gate, update_progress,
    introspection — all set to `pending`

## Step 8: Present Team Summary

Display to the user:
1. Team roster table: agent name, model tier, phase, parallel group
2. Phase plan with agent assignments
3. Contract chain visualization (text-based)
4. Instruction: "Review and edit files in .agent-team/ before running /start-team"
