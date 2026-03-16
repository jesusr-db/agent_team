# Agent Team Plugin Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin with `/create-team` and `/start-team` commands that dynamically assemble and orchestrate AI agent teams to build Databricks applications end-to-end.

**Architecture:** Two slash commands backed by a prompt-template engine. `/create-team` analyzes a PRD, selects/generates agents, and writes definitions to `.agent-team/`. `/start-team` dispatches a PM orchestrator that runs phased execution with worktree-isolated agents, progressive QA, and granular checkpoint recovery.

**Tech Stack:** Claude Code plugin system (plugin.json, commands/*.md, agents/*.md, skills/), YAML for templates/contracts/manifests, Markdown for agent prompts. Runtime uses the Agent() tool with model parameter and worktree isolation.

**Spec:** `docs/superpowers/specs/2026-03-16-agent-team-plugin-design.md`

---

## File Structure

```
agent-team/
├── .claude-plugin/
│   └── plugin.json                    # Plugin manifest
├── commands/
│   ├── create-team.md                 # /create-team slash command
│   └── start-team.md                 # /start-team slash command
├── agents/
│   └── pm-orchestrator.md            # PM orchestrator agent definition
├── skills/
│   ├── team-builder/
│   │   └── SKILL.md                  # PRD analysis → team assembly
│   └── phase-planner/
│       └── SKILL.md                  # Dependency analysis → phase structure
├── templates/
│   ├── core/
│   │   ├── data-engineer.yaml        # Curated agent template
│   │   ├── data-scientist.yaml       # Curated agent template
│   │   ├── genai-architect.yaml      # Curated agent template
│   │   ├── app-developer.yaml        # Curated agent template
│   │   ├── deploy-engineer.yaml      # Curated agent template
│   │   └── qa-engineer.yaml          # Curated agent template
│   └── meta/
│       ├── domain-sme-generator.yaml # Meta-template for domain SMEs
│       └── specialist-generator.yaml # Meta-template for novel specialists
├── lib/
│   └── contract-schema.yaml          # Contract format reference
└── test/
    └── qa-chatbot-prd.md             # Validation PRD for end-to-end test
```

---

## Chunk 1: Plugin Foundation

### Task 1: Plugin Manifest & Directory Structure

**Files:**
- Create: `.claude-plugin/plugin.json`

- [ ] **Step 1: Create plugin.json**

```json
{
  "name": "agent-team",
  "description": "Dynamically assemble and orchestrate AI agent teams to build Databricks applications end-to-end. Use /create-team to analyze a PRD and assemble a team, then /start-team to execute.",
  "version": "0.1.0",
  "author": {
    "name": "Databricks Field Engineering"
  },
  "skills": "./skills/",
  "commands": "./commands/"
}
```

- [ ] **Step 2: Create all required directories**

```bash
mkdir -p .claude-plugin commands agents skills/team-builder skills/phase-planner templates/core templates/meta lib test
```

- [ ] **Step 3: Commit scaffold**

```bash
git add .claude-plugin/ commands/ agents/ skills/ templates/ lib/ test/
git commit -m "feat: scaffold agent-team plugin directory structure"
```

### Task 2: Contract Schema Reference

**Files:**
- Create: `lib/contract-schema.yaml`

- [ ] **Step 1: Write contract schema**

```yaml
# Contract Schema Reference
# Defines the valid structure for all inter-agent contracts.
# Contracts are written to .agent-team/contracts/*.yaml

# Required fields
# name: string                    - Unique contract identifier (e.g., "data-to-genai")
# producer: string                - Agent name that produces the output
# consumer: string | "broadcast"  - Agent name or "broadcast" for all agents

# Optional: table definitions
# tables:
#   - name: string                - Table name in Unity Catalog
#     catalog: string             - UC catalog (supports {{template_vars}})
#     schema: string              - UC schema (supports {{template_vars}})
#     description: string         - What this table contains
#     columns:
#       - name: string            - Column name
#         type: string            - Spark SQL type (STRING, INT, DOUBLE, BOOLEAN, etc.)
#         required: boolean       - Whether this column must be present
#     min_rows: integer           - Minimum expected row count for validation

# Optional: file artifact definitions
# artifacts:
#   - path: string                - Glob or directory path relative to project root
#     description: string         - What this artifact contains

# Optional: validation rules
# validation:
#   - type: string                - One of: schema_match, artifact_exists, code_references, sql_check
#     description: string         - Human-readable description of what this validates
#     query: string               - SQL query (for sql_check type only)
#     expect: string              - Expected result (for sql_check type only, e.g. "> 0")

# Example:
name: data-to-genai
producer: data-engineer
consumer: genai-architect

tables:
  - name: doc_chunks
    catalog: "{{project_catalog}}"
    schema: "{{project_schema}}"
    description: Chunked and cleaned documentation for embedding
    columns:
      - name: chunk_id
        type: STRING
        required: true
      - name: doc_source
        type: STRING
        required: true
      - name: chunk_text
        type: STRING
        required: true
      - name: chunk_index
        type: INT
        required: true
      - name: metadata
        type: STRING
        required: false
    min_rows: 50

artifacts:
  - path: src/ingestion/
    description: Document ingestion and chunking pipelines
  - path: src/transformations/
    description: Text cleaning and chunk processing
  - path: resources/pipelines.yml
    description: SDP pipeline definitions

validation:
  - type: schema_match
    description: Consumer can read all required columns
  - type: artifact_exists
    description: All listed artifacts exist in project
  - type: sql_check
    query: "SELECT COUNT(*) FROM {{catalog}}.{{schema}}.doc_chunks"
    expect: "> 0"
```

- [ ] **Step 2: Commit**

```bash
git add lib/contract-schema.yaml
git commit -m "feat: add contract schema reference with example"
```

---

## Chunk 2: Curated Agent Templates

### Task 3: Data Engineer Template

**Files:**
- Create: `templates/core/data-engineer.yaml`

- [ ] **Step 1: Write data engineer template**

```yaml
name: data-engineer
display_name: Data Engineer
description: Builds data ingestion and transformation pipelines on Databricks
model: sonnet
typical_phases: [1]

capabilities:
  - data-ingestion
  - data-transformation
  - etl
  - streaming

skills:
  - spark-declarative-pipelines
  - databricks-unity-catalog
  - databricks-query
  - asset-bundles
  - synthetic-data-generation

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:get_table_details
  - databricks-mcp:manage_uc_objects
  - databricks-mcp:create_or_update_pipeline

output_paths:
  - src/ingestion/
  - src/transformations/
  - resources/pipelines.yml
  - tests/data_engineering/

prompt_template: |
  # Role
  You are a Senior Databricks Data Engineer on a cross-functional
  team building {{project_description}}.

  # Objective
  {{objective}}

  # Context
  {{phase_context}}
  {{domain_playbook}}
  {{contract_inputs}}

  # Technical Stack
  - Spark Declarative Pipelines (Lakeflow) for ingestion
  - Unity Catalog for governance
  - Auto Loader for incremental file ingestion
  - Delta Lake for storage
  - Use the spark-declarative-pipelines skill for pipeline patterns
  - Use the databricks-unity-catalog skill for UC operations
  - Use the databricks-query skill to validate SQL
  - Use the asset-bundles skill for DAB resource configuration

  # Output Requirements
  - Write pipeline code to src/ingestion/ and src/transformations/
  - Define pipeline resources in resources/pipelines.yml
  - Produce tables matching your output contracts
  - Write unit tests to tests/data_engineering/
  - Use synthetic-data-generation skill if real data is unavailable

  # Constraints
  {{constraints}}
  - Write code to src/ and resources/ only
  - Do not provision infrastructure directly
  - All tables in Unity Catalog under project catalog/schema
  - Follow DAB project structure

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    concerns: [if any]
    blockers: [if any]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/data-engineer.yaml
git commit -m "feat: add data engineer curated template"
```

### Task 4: Data Scientist Template

**Files:**
- Create: `templates/core/data-scientist.yaml`

- [ ] **Step 1: Write data scientist template**

```yaml
name: data-scientist
display_name: Data Scientist
description: Builds and deploys ML models on Databricks
model: sonnet
typical_phases: [1]

capabilities:
  - ml-training
  - ml-serving
  - feature-engineering
  - model-evaluation

skills:
  - databricks-query
  - databricks-unity-catalog
  - model-serving
  - asset-bundles

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:get_table_details
  - databricks-mcp:query_serving_endpoint

output_paths:
  - src/models/
  - resources/serving.yml
  - tests/data_science/

prompt_template: |
  # Role
  You are a Senior Databricks Data Scientist on a cross-functional
  team building {{project_description}}.

  # Objective
  {{objective}}

  # Context
  {{phase_context}}
  {{domain_playbook}}
  {{contract_inputs}}

  # Technical Stack
  - MLflow for experiment tracking and model registry
  - Unity Catalog for model governance
  - Databricks Model Serving for deployment
  - Use the model-serving skill for endpoint configuration
  - Use the databricks-query skill to explore training data

  # Output Requirements
  - Write training code to src/models/
  - Register models in Unity Catalog
  - Define serving endpoints in resources/serving.yml
  - Produce model outputs matching your output contracts
  - Write evaluation tests to tests/data_science/

  # Constraints
  {{constraints}}
  - Write code to src/ and resources/ only
  - Do not provision infrastructure directly
  - Follow DAB project structure

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    concerns: [if any]
    blockers: [if any]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/data-scientist.yaml
git commit -m "feat: add data scientist curated template"
```

### Task 5: GenAI Architect Template

**Files:**
- Create: `templates/core/genai-architect.yaml`

- [ ] **Step 1: Write GenAI architect template**

```yaml
name: genai-architect
display_name: GenAI Architect
description: Designs and implements GenAI solutions including RAG pipelines, prompt engineering, and model selection
model: opus
typical_phases: [2]

capabilities:
  - genai-rag
  - genai-prompt-engineering
  - vector-search
  - embeddings
  - llm-integration

skills:
  - databricks-unity-catalog
  - databricks-query
  - model-serving
  - asset-bundles

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:create_or_update_vs_endpoint
  - databricks-mcp:create_or_update_vs_index
  - databricks-mcp:query_serving_endpoint
  - databricks-mcp:query_vs_index

output_paths:
  - src/genai/
  - resources/serving.yml
  - tests/genai/

prompt_template: |
  # Role
  You are a Senior GenAI Architect on a cross-functional
  team building {{project_description}}.

  # Objective
  {{objective}}

  # Context
  {{phase_context}}
  {{domain_playbook}}
  {{contract_inputs}}

  # Technical Stack
  - Databricks Vector Search for similarity retrieval
  - Databricks Foundation Model API or external LLM endpoints
  - Databricks Model Serving for hosting RAG chains
  - Unity Catalog for managing embeddings and vector indexes
  - Use the model-serving skill for endpoint patterns
  - Use the databricks-query skill to validate data access

  # Architecture Decisions
  You are responsible for choosing:
  - Embedding model (e.g., databricks-bge-large-en, OpenAI ada-002)
  - Chunking strategy (size, overlap, method)
  - Retrieval approach (vector search, hybrid, reranking)
  - Generation model (DBRX, Llama, Claude, GPT-4)
  - Prompt engineering strategy

  Document all architecture decisions in src/genai/README.md.

  # Output Requirements
  - Write RAG pipeline code to src/genai/
  - Configure Vector Search index and serving endpoints in resources/serving.yml
  - Define prompt templates in src/genai/prompts/
  - Produce endpoints matching your output contracts
  - Write evaluation tests to tests/genai/

  # Constraints
  {{constraints}}
  - Write code to src/ and resources/ only
  - Do not provision infrastructure directly
  - Follow DAB project structure

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    concerns: [if any]
    blockers: [if any]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/genai-architect.yaml
git commit -m "feat: add genai architect curated template"
```

### Task 6: App Developer Template

**Files:**
- Create: `templates/core/app-developer.yaml`

- [ ] **Step 1: Write app developer template**

```yaml
name: app-developer
display_name: App Developer
description: Builds Databricks Apps with Node.js/React frontends and FastAPI backends
model: sonnet
typical_phases: [2, 3]

capabilities:
  - web-app
  - api-backend
  - frontend
  - databricks-app

skills:
  - databricks-app-apx
  - databricks-query
  - asset-bundles

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:create_or_update_app
  - databricks-mcp:query_serving_endpoint

output_paths:
  - src/app/backend/
  - src/app/frontend/
  - tests/app/

prompt_template: |
  # Role
  You are a Senior Full-Stack Developer specializing in Databricks Apps
  on a cross-functional team building {{project_description}}.

  # Objective
  {{objective}}

  # Context
  {{phase_context}}
  {{domain_playbook}}
  {{contract_inputs}}

  # Technical Stack
  - FastAPI for backend API
  - React with TypeScript for frontend
  - Databricks Apps for deployment (app.yaml configuration)
  - Databricks SQL for data queries
  - Use the databricks-app-apx skill for APX framework patterns
  - Use the databricks-query skill to validate backend SQL

  # Output Requirements
  - Write backend API to src/app/backend/ (FastAPI with proper routes)
  - Write frontend to src/app/frontend/ (React with TypeScript)
  - Code against contract definitions for endpoint shapes — not live artifacts
  - Write tests to tests/app/

  # Constraints
  {{constraints}}
  - Write code to src/app/ only
  - Do not provision infrastructure directly
  - Follow DAB project structure
  - Use environment variables for configuration, never hardcode secrets

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    concerns: [if any]
    blockers: [if any]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/app-developer.yaml
git commit -m "feat: add app developer curated template"
```

### Task 7: Deploy Engineer Template

**Files:**
- Create: `templates/core/deploy-engineer.yaml`

- [ ] **Step 1: Write deploy engineer template**

```yaml
name: deploy-engineer
display_name: Deploy Engineer
description: Finalizes DAB configuration and deploys to Databricks workspace
model: sonnet
typical_phases: [4]

capabilities:
  - deployment
  - infrastructure
  - dab-configuration

skills:
  - asset-bundles
  - databricks-config
  - databricks-query

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:get_best_warehouse
  - databricks-mcp:get_best_cluster
  - databricks-mcp:get_cluster_status

output_paths:
  - databricks.yml
  - resources/

prompt_template: |
  # Role
  You are a Senior DevOps/Deploy Engineer specializing in Databricks
  on a cross-functional team building {{project_description}}.

  # Objective
  {{objective}}

  # Context
  {{phase_context}}
  {{domain_playbook}}
  {{contract_inputs}}

  # Technical Stack
  - Databricks Asset Bundles (DABs) for deployment
  - databricks CLI for bundle operations
  - Use the asset-bundles skill for DAB configuration patterns
  - Use the databricks-config skill for workspace authentication

  # Output Requirements
  - Finalize databricks.yml with all resource references
  - Ensure all resources/*.yml files are valid and complete
  - Run `databricks bundle validate` to verify configuration
  - Run `databricks bundle deploy --target dev` to provision resources
  - Document deployment results in .agent-team/status/deploy-engineer.yaml

  # Constraints
  {{constraints}}
  - Only modify databricks.yml and resources/ files
  - Do not modify source code in src/
  - Validate before deploying
  - Target dev environment only unless explicitly told otherwise

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    concerns: [if any]
    blockers: [if any]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/deploy-engineer.yaml
git commit -m "feat: add deploy engineer curated template"
```

### Task 8: QA Engineer Template

**Files:**
- Create: `templates/core/qa-engineer.yaml`

- [ ] **Step 1: Write QA engineer template**

```yaml
name: qa-engineer
display_name: QA Engineer
description: Validates code quality, contract compliance, and integration correctness
model: sonnet
typical_phases: [1, 2, 3, 4]

capabilities:
  - testing
  - code-review
  - contract-validation
  - integration-testing

skills:
  - databricks-query
  - asset-bundles

mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:get_table_details

output_paths:
  - tests/
  - .agent-team/status/

prompt_template: |
  # Role
  You are a Senior QA Engineer on a cross-functional team
  building {{project_description}}.

  # Objective
  {{objective}}

  # QA Scope for This Phase
  {{qa_scope}}

  # Context
  {{phase_context}}
  {{contract_inputs}}

  # Progressive QA Checklist

  ## Code Quality (Phase 1+)
  - [ ] All Python files pass syntax check
  - [ ] No hardcoded secrets or credentials
  - [ ] Unit tests exist and pass for new code
  - [ ] Code follows project conventions

  ## Contract Validation (Phase 1+)
  For each contract in scope:
  - [ ] artifact_exists: All listed files/directories exist
  - [ ] schema_match: Producer's code produces columns matching contract
  - [ ] code_references: Consumer's code references the contracted tables/endpoints

  ## Integration Testing (Phase 2+)
  - [ ] Cross-agent interfaces match (API shapes, table schemas)
  - [ ] No circular dependencies between components

  ## E2E Validation (Phase 3+)
  - [ ] `databricks bundle validate` passes
  - [ ] E2E test scenarios cover PRD success criteria
  - [ ] Security review: no secrets, proper auth patterns

  ## Deployed Validation (Phase 4)
  - [ ] Pipeline executes successfully
  - [ ] Serving endpoints respond correctly
  - [ ] App loads and basic smoke test passes

  # Output Requirements
  - Write validation results to .agent-team/status/qa-phase-{{phase}}.yaml
  - Include: status (PASS/FAIL), checks (list with name/status/details), recommendations

  # Constraints
  {{constraints}}
  - Do not modify source code — only read and validate
  - Write test files to tests/ only
  - Write status to .agent-team/status/ only

  # Status Protocol
  When finished, write your status to .agent-team/status/{{agent_name}}.yaml:
    status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
    artifacts: [list of files created/modified]
    checks: [{name, status, details}]
    recommendations: [suggested fixes for failures]
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/qa-engineer.yaml
git commit -m "feat: add QA engineer curated template"
```

---

## Chunk 3: Meta-Templates & Dynamic Generation

### Task 9: Domain SME Generator Meta-Template

**Files:**
- Create: `templates/meta/domain-sme-generator.yaml`

- [ ] **Step 1: Write domain SME generator**

```yaml
type: generator
output_format: agent-definition-md
description: >
  Generates a Domain Subject Matter Expert agent definition.
  The SME researches the project domain and produces a domain-playbook.md
  that all downstream agents reference.

generator_prompt: |
  Given the PRD domain "{{domain}}" and project "{{project_description}}",
  generate a Domain Subject Matter Expert agent definition as a Markdown
  file with YAML frontmatter.

  The agent definition MUST follow this exact format:

  ---
  name: {{domain_slug}}-sme
  display_name: {{domain_display}} SME
  model: haiku
  phase: [0]
  parallel_group: planning
  skills: []
  mcp_tools: []
  inputs: []
  outputs:
    - contract: domain-playbook
      consumer: broadcast
      artifacts:
        - .agent-team/artifacts/domain-playbook.md
        - .agent-team/artifacts/data-requirements.yaml
        - .agent-team/artifacts/success-criteria.yaml
  constraints:
    - Write only to .agent-team/artifacts/
    - Do not write any application code
    - Focus on research and documentation
  ---

  The prompt body MUST instruct the SME to:
  1. Research {{domain}} using WebSearch and WebFetch tools
  2. Document industry-standard workflows relevant to the project
  3. Identify key data sources and their typical schemas
  4. Define success metrics and KPIs for this type of application
  5. Note regulatory or compliance considerations
  6. Document common pitfalls and how to avoid them
  7. Write findings to .agent-team/artifacts/domain-playbook.md
  8. Write data requirements to .agent-team/artifacts/data-requirements.yaml
  9. Write success criteria to .agent-team/artifacts/success-criteria.yaml

  Make the SME's prompt specific to the {{domain}} domain.
  Reference real industry frameworks, standards, and best practices.

defaults:
  model: haiku
  phase: [0]
  skills: []
  mcp_tools: []
```

- [ ] **Step 2: Commit**

```bash
git add templates/meta/domain-sme-generator.yaml
git commit -m "feat: add domain SME generator meta-template"
```

### Task 10: Specialist Generator Meta-Template

**Files:**
- Create: `templates/meta/specialist-generator.yaml`

- [ ] **Step 1: Write specialist generator**

```yaml
type: generator
output_format: agent-definition-md
description: >
  Generates a novel specialist agent definition for capabilities
  not covered by curated templates. Used when /create-team identifies
  a capability gap that requires domain-specific expertise.

generator_prompt: |
  The PRD for "{{project_description}}" requires a capability that
  is not covered by the curated agent templates: "{{capability}}".

  Generate a specialist agent definition as a Markdown file with YAML
  frontmatter.

  The agent definition MUST follow this exact format:

  ---
  name: {{capability_slug}}-specialist
  display_name: {{capability_display}} Specialist
  model: {{recommended_model}}
  phase: [{{recommended_phase}}]
  parallel_group: {{recommended_group}}
  skills: [{{relevant_skills}}]
  mcp_tools: [{{relevant_mcp_tools}}]
  inputs:
    - contract: domain-playbook
      from: {{domain_sme_name}}
  outputs:
    - contract: {{output_contract_name}}
      artifacts: [{{output_paths}}]
  constraints:
    - {{relevant_constraints}}
  ---

  Guidelines for the agent prompt:
  1. Give the specialist a clear, focused role
  2. Define specific technical stack and tools
  3. Set clear output requirements with exact file paths
  4. Include the standard status protocol
  5. Constrain the specialist to its area of expertise

  Model selection guide:
  - haiku: Research, search, summarization tasks
  - sonnet: Implementation, coding, testing tasks
  - opus: Architecture, design, complex reasoning tasks

  Choose the model that matches the specialist's primary activity.

defaults:
  model: sonnet
  phase: [1]
  skills: []
  mcp_tools: []
```

- [ ] **Step 2: Commit**

```bash
git add templates/meta/specialist-generator.yaml
git commit -m "feat: add specialist generator meta-template"
```

---

## Chunk 4: /create-team Command

### Task 11: Team Builder Skill

**Files:**
- Create: `skills/team-builder/SKILL.md`

- [ ] **Step 1: Write team builder skill**

This skill is invoked by the `/create-team` command. It contains the full logic for PRD analysis, capability mapping, agent selection, and dynamic generation.

```markdown
---
name: team-builder
description: Analyzes a PRD to identify required capabilities and assemble an agent team. Invoked by /create-team.
---

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

## Step 7: Write .agent-team/ Directory

Write all files:
- `.agent-team/team-manifest.yaml` — team roster, phases, model tiers
- `.agent-team/agents/*.md` — one per agent (customized from templates)
- `.agent-team/phases/*.yaml` — one per phase
- `.agent-team/contracts/*.yaml` — one per producer→consumer edge
- `.agent-team/status/progress.yaml` — initialized with all phases pending

## Step 8: Present Team Summary

Display to the user:
1. Team roster table: agent name, model tier, phase, parallel group
2. Phase plan with agent assignments
3. Contract chain visualization (text-based)
4. Instruction: "Review and edit files in .agent-team/ before running /start-team"
```

- [ ] **Step 2: Commit**

```bash
git add skills/team-builder/
git commit -m "feat: add team-builder skill for PRD analysis and team assembly"
```

### Task 12: Phase Planner Skill

**Files:**
- Create: `skills/phase-planner/SKILL.md`

- [ ] **Step 1: Write phase planner skill**

```markdown
---
name: phase-planner
description: Analyzes agent dependencies to create an optimal phase structure with parallel groups. Used by team-builder.
---

# Phase Planner

Given a set of agent definitions with their input/output contracts,
produce an optimal phase structure that maximizes parallelism while
respecting dependencies.

## Algorithm

### 1. Build Dependency Graph

For each agent, read its `inputs` field. Each input contract creates
a dependency edge: this agent depends on the agent named in `from`.

### 2. Topological Sort

Sort agents by dependency depth:
- Depth 0: Agents with no inputs (or only external inputs)
- Depth 1: Agents depending only on depth-0 agents
- Depth N: Agents depending on agents at depth N-1 or lower

### 3. Assign Phases

Map depths to phases:
- Depth 0 → Phase 0 (planning/research agents)
- Depth 1 → Phase 1 (first implementation wave)
- Depth 2 → Phase 2 (second implementation wave)
- Continue as needed...
- Always reserve the last two phases for Integration and Deploy

Special rules:
- QA Engineer participates in ALL phases (added to each phase config)
- Deploy Engineer always in the final phase
- If an agent appears in multiple phases (e.g., App Developer in Phase 2 and Phase 3), list all phases in its `phase` field

### 4. Assign Parallel Groups

Within each phase, agents that have NO dependency on each other
are assigned to the same `parallel_group`. Use descriptive names:
- "planning" for Phase 0 agents
- "data" for data-producing agents
- "app" for application-building agents
- Custom names for other groupings

### 5. Output Format

Write one YAML file per phase to `.agent-team/phases/`:

```yaml
# .agent-team/phases/phase-1-data-ingestion.yaml
phase: 1
name: Data Ingestion
description: Ingest and transform raw data into feature tables

agents:
  - name: data-engineer
    parallel_group: data
    model: sonnet
    inputs:
      - contract: domain-playbook
    outputs:
      - contract: data-to-genai

qa_scope: |
  - Code quality: lint, type check, unit tests
  - Contract validation: data-to-genai schema match, artifact exists
```

### 6. Validation

Verify:
- No circular dependencies
- All referenced contracts exist
- All agents are assigned to at least one phase
- Deploy phase is always last
```

- [ ] **Step 2: Commit**

```bash
git add skills/phase-planner/
git commit -m "feat: add phase-planner skill for dependency analysis"
```

### Task 13: /create-team Command

**Files:**
- Create: `commands/create-team.md`

- [ ] **Step 1: Write create-team command**

```markdown
---
description: "Analyze a PRD and assemble a dynamic agent team to build a Databricks application"
---

# /create-team

You are creating a dynamic agent team to build a Databricks application.

## Input

The user provided a PRD path: {{ARGUMENTS}}

## Execution

This command runs on **Opus** for complex analysis.

### Step 1: Read the PRD

Read the document at the provided path. If it's a Google Docs URL, use the
google-docs skill to read it. If it's a local file path, read it directly.

If no path was provided, ask the user for the PRD location.

### Step 2: Invoke team-builder skill

Use the team-builder skill to:
1. Parse the PRD and extract requirements
2. Map requirements to capability tags
3. Select curated agent templates from `templates/core/`
4. Generate dynamic specialist agents using `templates/meta/`
5. Design the phase structure using the phase-planner skill
6. Define inter-agent contracts
7. Write everything to `.agent-team/`

### Step 3: Present the team

Display the assembled team to the user:

#### Team Roster
| Agent | Model | Phase | Parallel Group | Skills |
|-------|-------|-------|----------------|--------|
| ... | ... | ... | ... | ... |

#### Phase Plan
- **Phase 0 (Planning):** [agents]
- **Phase 1 (...):** [agents — parallel group: ...]
- ...

#### Contract Chain
```
Agent A ──contract-name──→ Agent B ──contract-name──→ Agent C
```

#### Next Steps
> Team assembled and written to `.agent-team/`. Review and edit any agent
> definitions, phase configs, or contracts before running `/start-team`.
>
> Key files to review:
> - `.agent-team/team-manifest.yaml` — team configuration
> - `.agent-team/agents/*.md` — individual agent prompts
> - `.agent-team/contracts/*.yaml` — inter-agent data contracts
> - `.agent-team/phases/*.yaml` — phase execution plan
```

- [ ] **Step 2: Commit**

```bash
git add commands/create-team.md
git commit -m "feat: add /create-team slash command"
```

---

## Chunk 5: PM Orchestrator & /start-team

### Task 14: PM Orchestrator Agent

**Files:**
- Create: `agents/pm-orchestrator.md`

This is the core runtime engine — the most complex file in the plugin.

- [ ] **Step 1: Write PM orchestrator agent**

```markdown
---
name: pm-orchestrator
description: >
  Orchestrates phased execution of an agent team. Reads the team manifest,
  dispatches agents in worktree-isolated parallel groups, runs progressive QA
  gates, manages checkpoint recovery, and escalates blockers to the human.
  Dispatched by /start-team.
model: opus
---

# PM Orchestrator

You are the Project Manager orchestrating a team of AI agents building a
Databricks application. You coordinate phased execution, ensure quality
gates pass, and manage recovery from failures.

## Your Tools

- **Agent()** tool to dispatch subagents with `isolation: "worktree"` and `model` parameter
- **Read/Write/Edit** tools to manage `.agent-team/status/progress.yaml`
- **Bash** tool for git operations (merge worktree branches)
- All tools needed to resolve template variables

## Inputs

You receive:
- Team manifest: `.agent-team/team-manifest.yaml`
- Agent definitions: `.agent-team/agents/*.md`
- Phase configs: `.agent-team/phases/*.yaml`
- Contracts: `.agent-team/contracts/*.yaml`
- Current progress: `.agent-team/status/progress.yaml`

## Startup: Check Resume State

1. Read `.agent-team/status/progress.yaml`
2. Find `current_state` — this tells you exactly where to resume
3. Display resume status to the user:
   ```
   ⟳ Resuming from checkpoint...
     Phase 0 (Planning):       ✓ completed
     Phase 1 (Data Ingestion): ▸ interrupted at dispatch_agents
     ...
   ```
4. Resume at the exact interrupted step (see Auto-Recovery Logic below)

If `progress.yaml` shows all phases pending, this is a fresh start.

## Main Loop: For Each Phase

### Step 1: read_phase_config
- Read `.agent-team/phases/phase-N-*.yaml`
- Identify agents, parallel groups, QA scope
- **Checkpoint:** Write `phases[N].steps.read_phase_config: in_progress` → then `completed`

### Step 2: resolve_contracts
- For each agent in this phase, read its `inputs` field
- For each input contract, read the contract YAML and resolve `{{template_vars}}`
- Read upstream agent artifacts (e.g., domain-playbook.md from Phase 0)
- Build the full prompt for each agent by resolving all `{{variables}}`:
  - `{{project_description}}` — from team manifest
  - `{{objective}}` — from phase config + agent definition
  - `{{phase_context}}` — current phase description and goals
  - `{{domain_playbook}}` — contents of .agent-team/artifacts/domain-playbook.md
  - `{{contract_inputs}}` — resolved input contract details
  - `{{constraints}}` — from agent definition + phase-specific constraints
  - `{{agent_name}}` — the agent's name field
  - `{{qa_scope}}` — QA scope for this phase (QA agent only)
- **Checkpoint:** Write step status

### Step 3: dispatch_agents
- Group agents by `parallel_group`
- For each group, dispatch ALL agents in a single message:
  ```
  Agent(
    description: "<agent_name> - Phase N <phase_name>"
    model: "<from agent definition>"
    prompt: "<fully resolved agent prompt>"
    isolation: "worktree"
    run_in_background: true  # for all but the last in the group
  )
  ```
- **Checkpoint:** Write per-agent status as `dispatched` with `worktree_branch`
- Commit progress.yaml after all dispatches

### Step 4: await_agents
- Wait for all dispatched agents to return
- For each returned agent, read their status file from the worktree
- **Checkpoint:** Update per-agent status

### Step 5: Handle agent statuses

For each agent:
- **DONE:** Proceed to merge
- **DONE_WITH_CONCERNS:** Read concerns. If they affect correctness, address before merge. If observational, note and proceed.
- **NEEDS_CONTEXT:** Provide the missing context and re-dispatch the same agent (same worktree). Update checkpoint.
- **BLOCKED:** Try to unblock:
  1. Provide more context and re-dispatch with same model
  2. If still blocked, re-dispatch with a more capable model
  3. If still blocked, escalate to human:
     - Write blocker details to `.agent-team/status/escalation.md`
     - Return control to main session with summary

### Step 6: merge_worktrees
- For each completed agent, merge their worktree branch into main:
  ```bash
  git merge agent/<agent-name> --no-edit
  ```
- If merge conflicts:
  - Trivial (different sections of same file): resolve automatically
  - Semantic (overlapping logic): escalate to human
- **Checkpoint:** Update per-agent `merged: true`
- Commit progress.yaml

### Step 7: qa_gate
- Dispatch QA Engineer agent with the phase's `qa_scope`
- Read QA results from `.agent-team/status/qa-phase-N.yaml`
- If **PASS:** Proceed to next phase
- If **FAIL:**
  - Dispatch a fix agent for the specific issues (use the original agent's model)
  - Re-run QA
  - After 3 failed attempts: escalate to human
- **Checkpoint:** Write QA attempt count and result
- Track in `qa_attempts` field

### Step 8: update_progress
- Mark phase as `completed` with timestamp
- Commit progress.yaml to git:
  ```bash
  git add .agent-team/status/progress.yaml
  git commit -m "checkpoint: phase N completed"
  ```
- Advance to next phase

## Phase Boundary: Human Touchpoint

At the end of each phase, report to the user:
```
Phase N (Name) completed ✓
  Agents: [list with statuses]
  Artifacts: [files created/modified]
  QA: PASS (attempt N)

Next: Phase N+1 (Name) — agents: [list]
Continue? (yes / pause / adjust)
```

Wait for user confirmation before proceeding to the next phase.

## All Phases Complete

When all phases are done:
```
All phases completed ✓

Final Report:
  Phase 0: [summary]
  Phase 1: [summary]
  ...

Artifacts: [full list of created files]
QA Results: [summary per phase]
Deploy Status: [if Phase 4 ran]

The project is ready for review.
```

## Auto-Recovery Logic

When resuming from a checkpoint, use this logic per step:

| Interrupted Step | Recovery Action |
|-----------------|-----------------|
| read_phase_config | Re-read config (idempotent) |
| resolve_contracts | Re-resolve (idempotent) |
| dispatch_agents | Check worktree branches — agents with commits = completed, dispatch remaining |
| await_agents | Read status files from returned agents, re-dispatch any with no status |
| merge_worktrees | Check git log for merged branches, merge only unmerged |
| qa_gate | Re-run QA from scratch (stateless) |
| update_progress | Write progress and commit (idempotent) |

## Checkpoint Write Protocol

CRITICAL: Write checkpoint BEFORE and AFTER every step.

1. Before starting a step: write `in_progress`
2. During step: update per-agent statuses as they change
3. After step completes: write `completed`
4. After every step completion: `git commit .agent-team/status/progress.yaml`

This ensures `/start-team` can always recover from the last committed state.

## Rules

- NEVER skip QA gates
- NEVER proceed with unresolved agent blockers
- NEVER merge conflicting worktrees without resolution
- ALWAYS checkpoint before and after each step
- ALWAYS wait for user confirmation at phase boundaries
- ALWAYS escalate to human after 3 failed QA attempts
- ALWAYS use worktree isolation for every agent dispatch
```

- [ ] **Step 2: Commit**

```bash
git add agents/pm-orchestrator.md
git commit -m "feat: add PM orchestrator agent with phased execution and checkpoint recovery"
```

### Task 15: /start-team Command

**Files:**
- Create: `commands/start-team.md`

- [ ] **Step 1: Write start-team command**

```markdown
---
description: "Execute the agent team plan — dispatches PM orchestrator for phased execution with auto-recovery"
---

# /start-team

You are launching the agent team to build the Databricks application.

## Input

Flags (optional): {{ARGUMENTS}}
- `--phase N` — Override: restart from phase N
- `--agent <name>` — Re-run a single agent
- `--dry-run` — Show execution plan without dispatching

## Pre-Flight Checks

### 1. Validate .agent-team/

Verify these files exist and parse correctly:
- `.agent-team/team-manifest.yaml`
- `.agent-team/agents/*.md` (at least one agent)
- `.agent-team/phases/*.yaml` (at least one phase)
- `.agent-team/contracts/*.yaml` (at least one contract)

If any are missing, tell the user: "Run /create-team first to assemble the team."

### 2. Initialize Git

If this directory is not a git repository:
```bash
git init
git add .
git commit -m "Initial commit: agent team project"
```

### 3. Scaffold DAB Project

If `databricks.yml` doesn't exist, create the base DAB structure:
```
databricks.yml
src/
resources/
tests/
```

### 4. Initialize or Read Progress

If `.agent-team/status/progress.yaml` doesn't exist, create it with all
phases set to `pending`.

If it exists, read it to determine resume state.

## Handle Flags

### --dry-run
Display the execution plan and exit:
```
Execution Plan:
  Phase 0 (Planning): docs-domain-sme (haiku)
  Phase 1 (Data Ingestion): data-engineer (sonnet)
  Phase 2 (RAG + App): genai-architect (opus) ∥ app-developer (sonnet)
  Phase 3 (Integration): app-developer (sonnet)
  Phase 4 (Deploy): deploy-engineer (sonnet) → qa-engineer (sonnet)
```

### --phase N
Override the resume point: set `current_state.phase` to N and all prior
phases to `completed` in progress.yaml. Then proceed to dispatch.

### --agent <name>
Re-run a single agent:
1. Read the agent's phase from its definition
2. Read phase context from progress.yaml
3. Dispatch the agent in a fresh worktree with the current agent definition
4. On completion, merge the worktree branch
5. Re-run QA gate for that agent's phase
6. Update progress.yaml

### Default (no flags)
Auto-resume from checkpoint. Display resume status and proceed.

## Dispatch PM Orchestrator

Read the full team manifest, all agent definitions, phase configs, and
contracts. Then dispatch the PM orchestrator:

```
Agent(
  description: "PM Orchestrator - phased execution"
  subagent_type: "pm-orchestrator"
  model: "opus"
  prompt: |
    Execute the agent team plan.

    Team manifest: [contents of team-manifest.yaml]
    Progress: [contents of progress.yaml]
    Phases: [list of phase files]
    Agents: [list of agent files]
    Contracts: [list of contract files]

    Resume from: [current_state from progress.yaml]

    All agent definitions, phase configs, and contracts are in
    the .agent-team/ directory. Read them as needed.
)
```

The PM orchestrator takes over from here. It will:
- Execute phases sequentially
- Dispatch agents in parallel within phases
- Run QA gates at phase boundaries
- Checkpoint progress after every step
- Escalate blockers back to this session
```

- [ ] **Step 2: Commit**

```bash
git add commands/start-team.md
git commit -m "feat: add /start-team slash command with auto-recovery and flag handling"
```

---

## Chunk 6: Validation

### Task 16: Q&A Chatbot Test PRD

**Files:**
- Create: `test/qa-chatbot-prd.md`

- [ ] **Step 1: Write test PRD**

```markdown
# Q&A Chatbot over Documentation — PRD

## Overview

Build an intelligent Q&A chatbot that can answer questions about a
documentation corpus. Users interact through a simple chat interface
where they type questions and receive accurate, sourced answers.

## Target Users

- Technical writers seeking information across large doc sets
- Support engineers answering customer questions
- New team members onboarding to a codebase or product

## Features

### Document Ingestion
- Load documentation from a set of Markdown/text files
- Extract and clean text content
- Chunk documents into appropriate segments for embedding
- Store chunks in a Delta table with metadata (source, position)

### RAG Pipeline
- Generate embeddings for all document chunks
- Store embeddings in Databricks Vector Search index
- Retrieve relevant chunks for user queries
- Generate answers using an LLM with retrieved context
- Include source references in responses

### Chat Interface
- Simple web-based chat UI
- Message history within a session
- Display source documents for each answer
- Loading indicators during retrieval/generation

## Data Sources

- A collection of Markdown documentation files (provided at deploy time)
- No external APIs or databases required beyond Databricks services

## Technical Constraints

- Databricks workspace with Unity Catalog enabled
- Databricks Vector Search available
- Foundation Model API or external LLM endpoint accessible
- Deploy as a Databricks App

## Success Criteria

1. Documents are ingested and chunked into a Delta table
2. Vector Search index is populated with embeddings
3. Chat UI loads and accepts user input
4. Questions receive relevant, sourced answers within 10 seconds
5. Deployed as a Databricks App accessible via workspace URL
```

- [ ] **Step 2: Commit**

```bash
git add test/qa-chatbot-prd.md
git commit -m "feat: add Q&A chatbot test PRD for end-to-end validation"
```

### Task 17: End-to-End Validation

This task validates the plugin works by running both commands.

- [ ] **Step 1: Install the plugin locally**

```bash
# From the agent-team directory
cd /Users/jesus.rodriguez/Documents/ItsAVibe/gitrepos_FY27/agent_team
# The plugin should be installable by pointing Claude Code at this directory
```

Verify: Plugin appears in Claude Code with `/create-team` and `/start-team` commands listed.

- [ ] **Step 2: Run /create-team with the test PRD**

```
/create-team test/qa-chatbot-prd.md
```

Expected output:
- `.agent-team/` directory created with all files
- Team roster displayed with: Docs Domain SME, Data Engineer, GenAI Architect, App Developer, Deploy Engineer, QA Engineer
- Phase plan with 5 phases (0-4)
- Contract chain: Data Engineer → GenAI Architect → App Developer → Deploy Engineer

Verify:
- All agent `.md` files exist in `.agent-team/agents/`
- All phase `.yaml` files exist in `.agent-team/phases/`
- All contract `.yaml` files exist in `.agent-team/contracts/`
- `team-manifest.yaml` lists all agents with correct model tiers

- [ ] **Step 3: Review generated team**

Read each file in `.agent-team/` and verify:
- Agent prompts are specific to the Q&A chatbot domain
- Contracts have reasonable schemas for document chunks
- Phase assignments match the spec (SME→Phase 0, Data Eng→Phase 1, etc.)
- Model tiers are correct (Opus for GenAI Architect, Sonnet for implementation, Haiku for SME)

- [ ] **Step 4: Run /start-team --dry-run**

```
/start-team --dry-run
```

Expected: Display execution plan without dispatching any agents. Verify phase structure and agent assignments look correct.

- [ ] **Step 5: Commit validation artifacts**

```bash
git add .agent-team/
git commit -m "test: validate /create-team produces correct team for Q&A chatbot PRD"
```
