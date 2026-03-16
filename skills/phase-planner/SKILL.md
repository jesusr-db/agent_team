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
