---
description: "Analyze a PRD and assemble a dynamic agent team to build a Databricks application"
---

# /create-team

You are creating a dynamic agent team to build a software project. The **target
profile** (`targets/<name>.yaml`) selects the technology stack; `databricks` is the
default and reproduces the original Databricks-only behavior.

## Input

The user provided a PRD path and optional flags: {{ARGUMENTS}}

Parse the following optional flags from `{{ARGUMENTS}}`:

- `--target <name>` — target profile to build for: `databricks` (default), `web-fullstack`,
  `docker`, `genai-finetuning`, or `generic`. Profiles live in `targets/<name>.yaml`.
  If omitted, auto-detect from the PRD (Step 1.4).
- `--catalog <name>` — Unity Catalog catalog to profile (databricks target only)
- `--schema <name>` — Unity Catalog schema/database to profile (databricks target only)
- `--max-tables N` — maximum tables to profile (default: 50; passed through to data-analyzer)

The PRD path is the first non-flag argument. Flags may appear before or after
the path.

## Execution

This command runs on **Opus** for complex analysis.

### Step 1: Read the PRD

Read the document at the provided path. If it's a Google Docs URL, use the
google-docs skill to read it. If it's a local file path, read it directly.

If no path was provided, ask the user for the PRD location.

### Step 1.4: Resolve the target profile

1. If `--target <name>` was provided, load `targets/<name>.yaml`. If the file does
   not exist, list available profiles (the stems of `targets/*.yaml`) and ask the user.
2. If `--target` was omitted, **auto-detect**: read every `targets/*.yaml`, count how
   many of each profile's `detect_keywords` appear (case-insensitive) in the PRD text.
   - Pick the highest-scoring profile.
   - On a tie, or if the top score is 0, fall back to `databricks` if any Databricks
     keyword matched at all, otherwise `generic`.
   - Tell the user which profile was auto-detected and the runner-up, e.g.
     `Target: web-fullstack (auto-detected; runner-up: docker). Override with --target.`
3. Load the chosen profile and keep its contents available as `active_profile` for
   Step 2 (passed to the team-builder skill).

This resolved profile drives capability vocabulary, agent selection, scaffold,
deploy, validation, and QA in every later step.

### Step 1.5: Analyze existing data (databricks target only)

**Applies only when `active_profile.name == "databricks"`.** For all other targets,
skip this step entirely (there is no Unity Catalog to profile).

**Trigger:** Run this step when either condition is true:
1. Both `--catalog` and `--schema` flags were provided in the arguments.
2. The PRD text contains references to existing tables in the form
   `catalog.schema.table` (three-part dot-separated identifiers).

**If triggered:**

Invoke the **data-analyzer** skill with:
- `catalog` — from `--catalog` flag, or inferred from the first
  `catalog.schema.table` reference found in the PRD
- `schema` — from `--schema` flag, or inferred from the PRD reference
- `max_tables` — from `--max-tables` flag, or default (50)

The skill produces `.agent-team/artifacts/data-profile.yaml`.

If the skill reports MCP unavailable or all tables return errors, emit a
warning and continue — do **not** block team assembly.

**If not triggered:** Skip this step entirely.

### Step 2: Invoke team-builder skill

Pass `active_profile` (from Step 1.4) to the team-builder skill — it is the
authoritative source for capability vocabulary, curated vs. generated agents,
tech SMEs, scaffold, deploy, validation, and QA assertions.

Use the team-builder skill to:
0. If `.agent-team/artifacts/data-profile.yaml` was produced in Step 1.5,
   pass it to the team-builder so real table schemas, column stats, sample
   rows, and inferred relationships are available during team assembly.
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
