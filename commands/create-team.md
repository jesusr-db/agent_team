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
