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
| databricks-app | Databricks Apps deployment |
| deployment | DAB configuration, CI/CD |
| domain:* | Industry-specific expertise (e.g., domain:retail, domain:healthcare) |

## Step 3: Select Curated Agents

For each capability tag, check if a curated template in `templates/core/` covers it.
Read each template's `capabilities` field to match.

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
1. Domain SME agents → Phase 0 (no dependencies)
2. Data-producing agents → Phase 1 (depend on domain playbook)
3. Agents consuming data outputs → Phase 2 (depend on Phase 1)
4. Integration work → Phase 3 (depends on all producers)
5. Deploy → Phase 4 (always last)

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
