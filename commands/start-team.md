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
