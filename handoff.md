# Agent Team Plugin — Test Handoff

## What Was Built

A Claude Code plugin (`agent-team`) that dynamically assembles and orchestrates AI agent teams to build Databricks applications end-to-end.

**Repo:** https://github.com/jesusr-db/agent_team.git

## Plugin Structure

```
agent-team/
├── .claude-plugin/plugin.json          # Plugin manifest
├── commands/
│   ├── create-team.md                  # /create-team <prd-path>
│   └── start-team.md                   # /start-team [--phase N] [--agent name] [--dry-run]
├── agents/                             # 7 registered agents with model/tools frontmatter
│   ├── pm-orchestrator.md              # Opus — coordinates phased execution
│   ├── data-engineer.md                # Sonnet — data ingestion/transformation
│   ├── data-scientist.md               # Sonnet — ML models
│   ├── genai-architect.md              # Opus — RAG/GenAI architecture
│   ├── app-developer.md                # Sonnet — FastAPI + React apps
│   ├── deploy-engineer.md              # Sonnet — DAB deployment
│   └── qa-engineer.md                  # Sonnet — progressive QA validation
├── skills/
│   ├── team-builder/SKILL.md           # PRD analysis → team assembly
│   └── phase-planner/SKILL.md          # Dependency analysis → phase structure
├── templates/
│   ├── core/                           # Metadata-only (capabilities, output_paths, registered_agent pointer)
│   │   ├── data-engineer.yaml
│   │   ├── data-scientist.yaml
│   │   ├── genai-architect.yaml
│   │   ├── app-developer.yaml
│   │   ├── deploy-engineer.yaml
│   │   └── qa-engineer.yaml
│   └── meta/                           # Generators for dynamic specialist agents
│       ├── domain-sme-generator.yaml
│       └── specialist-generator.yaml
├── lib/contract-schema.yaml            # Contract format reference
├── test/qa-chatbot-prd.md              # Test PRD for validation
└── docs/superpowers/
    ├── specs/2026-03-16-agent-team-plugin-design.md
    └── plans/2026-03-16-agent-team-plugin.md
```

## How to Install

```bash
# From any Claude Code session:
/install-plugin https://github.com/jesusr-db/agent_team.git
```

Or add to your Claude Code plugin config manually.

## Test Scenario: Q&A Chatbot

### Step 1: Run /create-team

```
/create-team test/qa-chatbot-prd.md
```

**Expected behavior:**
1. Reads the PRD and identifies capabilities: data-ingestion, data-transformation, genai-rag, vector-search, embeddings, web-app, api-backend, databricks-app, domain:documentation
2. Selects curated agents: data-engineer, genai-architect, app-developer, deploy-engineer, qa-engineer
3. Generates a dynamic agent: docs-domain-sme (via domain-sme-generator.yaml)
4. Does NOT select data-scientist (no ml-training/ml-serving capability needed)
5. Designs phase structure:
   - Phase 0: docs-domain-sme (haiku) — domain research
   - Phase 1: data-engineer (sonnet) — doc ingestion/chunking
   - Phase 2: genai-architect (opus) ∥ app-developer (sonnet) — RAG + chat UI in parallel
   - Phase 3: app-developer (sonnet) — integration wiring
   - Phase 4: deploy-engineer (sonnet) → qa-engineer (sonnet) — deploy + validate
6. Defines contracts: data-to-genai, genai-to-app, app-to-deploy
7. Writes everything to `.agent-team/`
8. Presents team roster and phase plan

**Verify:**
- `.agent-team/team-manifest.yaml` exists with all agents and correct model tiers
- `.agent-team/agents/*.md` has 6 agent definitions (5 curated + 1 dynamic SME)
- `.agent-team/phases/*.yaml` has 5 phase files
- `.agent-team/contracts/*.yaml` has 3 contract files
- `.agent-team/status/progress.yaml` initialized with all phases pending

### Step 2: Review generated team

Check that:
- The docs-domain-sme agent was dynamically generated with haiku model
- Contract schemas are reasonable (doc_chunks table with chunk_id, doc_source, chunk_text, etc.)
- Phase assignments match the expected plan above
- Agent prompts reference appropriate skills

### Step 3: Run /start-team --dry-run

```
/start-team --dry-run
```

**Expected:** Shows execution plan without dispatching any agents:
```
Execution Plan:
  Phase 0 (Planning): docs-domain-sme (haiku)
  Phase 1 (Data Ingestion): data-engineer (sonnet)
  Phase 2 (RAG + App): genai-architect (opus) ∥ app-developer (sonnet)
  Phase 3 (Integration): app-developer (sonnet)
  Phase 4 (Deploy): deploy-engineer (sonnet) → qa-engineer (sonnet)
```

### Step 4: Run /start-team (full execution)

```
/start-team
```

**Expected behavior:**
1. PM orchestrator (opus) takes over
2. Scaffolds DAB project structure (databricks.yml, src/, resources/, tests/)
3. Executes Phase 0: dispatches docs-domain-sme in a worktree
   - SME researches documentation Q&A best practices via WebSearch
   - Produces domain-playbook.md, data-requirements.yaml, success-criteria.yaml
   - PM merges worktree, QA reviews playbook
   - **Human touchpoint:** PM reports Phase 0 complete, asks to continue
4. Executes Phase 1: dispatches data-engineer in a worktree
   - Writes ingestion/chunking code to src/ingestion/, src/transformations/
   - Uses spark-declarative-pipelines skill
   - PM merges, QA validates code quality + data-to-genai contract
   - **Human touchpoint**
5. Executes Phase 2: dispatches genai-architect AND app-developer in parallel worktrees
   - GenAI architect builds RAG pipeline (src/genai/)
   - App developer builds chat UI (src/app/)
   - Both code against genai-to-app contract, not each other's artifacts
   - PM merges both, QA validates
   - **Human touchpoint**
6. Executes Phase 3: dispatches app-developer to wire everything together
   - Connects chat UI to RAG endpoint
   - Writes e2e tests
   - PM merges, QA validates full chain + `databricks bundle validate`
   - **Human touchpoint**
7. Executes Phase 4: deploy-engineer provisions via DAB, qa-engineer validates deployed state
   - **Human touchpoint:** Final report

### Key Things to Watch For

- **Curated agents dispatched via `subagent_type`** — PM should use `subagent_type: "data-engineer"` etc., not full prompt injection
- **Dynamic SME dispatched via general-purpose** — PM should use `model: "haiku"` + full prompt for the docs-domain-sme
- **Worktree isolation** — every agent dispatch should include `isolation: "worktree"`
- **Checkpoint recovery** — progress.yaml should be updated and committed after every step
- **Phase boundary human touchpoints** — PM should pause and report after each phase
- **Progressive QA** — QA scope should intensify by phase (code quality → contracts → e2e → deployed)

## Architecture Decisions

- **Curated agents = registered plugin agents** with model/tools in frontmatter, dispatched via `subagent_type`
- **Dynamic agents = general-purpose** with full prompt injection (can't register at runtime)
- **Templates = metadata-only** for `/create-team` capability matching, with `registered_agent` pointer
- **DAB-first project structure** — all agent artifacts go into Databricks Asset Bundle layout
- **Granular checkpoints** — 7 steps per phase, committed to git, auto-recoverable
- **Contracts** — YAML files defining producer→consumer data flow with validation rules
