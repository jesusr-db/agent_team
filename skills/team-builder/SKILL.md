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

You are assembling a team of AI agents to build a software project for a specific
**target profile**. Given a PRD document and an `active_profile` (the parsed
contents of `targets/<name>.yaml`, passed by `/create-team`), you will analyze the
PRD and produce a complete team configuration for that target.

**`active_profile` is authoritative.** Source the capability vocabulary from
`active_profile.capabilities`, the curated agents from `active_profile.curated_agents`,
the technical SMEs from `active_profile.tech_smes`, and the scaffold/deploy/validation/
QA choices from the corresponding profile keys. When `active_profile.name ==
"databricks"`, this reproduces the original behavior exactly. If no profile was passed
(legacy invocation), default to `targets/databricks.yaml`.

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

## Step 1.7: Derive User Journeys (app teams only)

If — and only if — the team will include a `web-app` or `databricks-app`
capability (decided in Step 2/Step 3), derive user journeys that exercise the
PRD's goal and write them to `.agent-team/artifacts/user-journeys.yaml`.

(If no app capability is present, skip this step — there is no app to drive.)

**Ordering note:** the capability set is determined in Step 2/Step 3, which run
after this step. Complete Step 2/Step 3 first to learn whether an app capability
is present, then return here to write the artifact. (`/add-feature` also generates
journeys for `frontend` / `api-backend` features — see feature-scoper Step 4.)

**Source material:** the PRD's overall goal, the **User interactions** and
**Success criteria** extracted in Step 1, plus the **Data profile** if available.

**Output format:** follow `lib/journey-schema.yaml` exactly. Produce 3–5 journeys
covering, where applicable:
1. Happy single-action path through the most common interaction.
2. A multi-step / multi-tool path that exercises the core product flow.
3. A high-risk confirmation flow, if the PRD describes gated/destructive actions.
4. A known-bad input or known-bad data path (negative path).
5. A negative-auth path, if the PRD describes authorization boundaries.

Every journey MUST set `success_criteria` (falsifiable) and
`maps_to: <the PRD success criterion it validates>`.

These journeys are consumed in **Phase 4** by the QA engineer via the
`app-validation-loop` skill. Note the artifact in the team summary (Step 8).

## Step 2: Map to Capability Tags

Map each PRD requirement to one or more capability tags from **`active_profile.capabilities`**. Each profile entry has `tag`, `triggered_by`
(the PRD phrasing that implies it), and `satisfy` (`curated:<agent>` or
`generate:<role>`). Match PRD requirements against `triggered_by` to select tags.

`domain:*` tags (industry expertise, e.g. `domain:retail`) are always available
regardless of profile and are satisfied by an industry SME (Step 4).

> The capability vocabulary is no longer hardwired here — it lives in the target
> profile so new stacks are added by authoring a profile, not editing this skill.
> For the canonical Databricks vocabulary, see `targets/databricks.yaml`.

## Step 3: Select Curated Agents

For each matched capability whose `satisfy` is `curated:<agent>`, select that curated
registered agent (its template is in `templates/core/`). Only the `databricks` profile
uses curated agents; other profiles leave `curated_agents` empty and satisfy every
capability via `generate:<role>` (Step 4).

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

Always include these gate/role agents regardless of capabilities:
- **qa-engineer** (always — validation; its assertions come from
  `active_profile.qa_assertions`)
- **adversarial-reviewer** (always — independent red-team gate in the final phase
  after the qa-engineer gate; see Step 5. Pass `active_profile.security_focus` to it.)
- **deploy/ship agent** (always — satisfied by `active_profile.deploy.satisfy`:
  for `databricks` this is the curated `deploy-engineer`; for other profiles,
  generate a deploy specialist via Step 4 using `active_profile.deploy.verb`)

`qa-engineer` and `adversarial-reviewer` are registered agents reused across all
targets (their tools are generic / read-only, so no per-target tool binding is needed).

## Step 4: Generate Dynamic Specialists and SMEs

**4a. Technical SMEs (Phase 0).** For each entry in `active_profile.tech_smes`,
generate a technical SME using `templates/meta/tech-sme-generator.yaml` (set
`tech_domain` to the entry). For the `generic` profile, if `tech_smes` is empty,
derive 1–3 tech domains from the PRD's primary technologies and generate SMEs for
those. Each writes `.agent-team/artifacts/tech-playbook-<slug>.md`, broadcast to all
builders (add a broadcast contract per Step 6). This is how non-Databricks targets
recover the deep stack specificity that the curated Databricks agents have built in.

**4b. Industry SMEs (Phase 0).** For each `domain:*` tag, generate a domain SME using
`domain-sme-generator.yaml` (unchanged behavior).

**4c. Builder/deploy specialists.** For each capability whose `satisfy` is
`generate:<role>` (including the deploy specialist from
`active_profile.deploy.satisfy` when it is `generate:…`), generate a specialist using
`specialist-generator.yaml`. Fill the generator with PRD context AND the relevant
`tech-playbook-<slug>.md` as required input (so the specialist inherits the SME's
guidance). Default `mcp_tools: []` — generated specialists use generic tools and are
dispatched via the PM's dynamic-agent path. Write each to `.agent-team/agents/<name>.md`.

## Step 5: Design Phase Structure

Apply the phase structure algorithm:
1. `data-discovery` + Domain SME agents → Phase 0 (no dependencies, run in parallel if both present)
2. Data-producing agents → Phase 1 (depend on data-profile.yaml from Phase 0)
3. Agents consuming data outputs → Phase 2 (depend on Phase 1)
4. Integration work → Phase 3 (depends on all producers)
5. Deploy → Phase 4 (always last)

The **adversarial-reviewer** is assigned to the final phase (the same phase as
`deploy-engineer`/`qa-engineer`) but is NOT placed in a parallel group with the
builders. It is a *gate*, not a producer: the PM orchestrator dispatches it in
Step 7.5 only after the final-phase qa-engineer gate passes. In the phase config,
list `adversarial-reviewer` under a dedicated `gates:` key rather than
`parallel_groups:` so the PM knows to run it as a post-QA gate, not a build agent:

```yaml
# in the final phase YAML
gates:
  - qa-engineer          # functional gate (existing)
  - adversarial-reviewer # falsification gate (runs after qa passes)
```

The `adversarial-reviewer` template declares `typical_phases: [final]` as a sentinel
— resolve `final` to the ACTUAL highest phase number when you write the phase configs
and the roster, and emit the `gates:` key (above) into that final phase's YAML. The
PM triggers the adversarial gate off this `gates:` key, not off phase position.
The `gates:` key lives in the **phase YAML** (the PM reads it in Step 1
`read_phase_config`); the team-manifest roster only marks the reviewer's role as a
gate. Do not place `gates:` on non-final phases.

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
- `.agent-team/team-manifest.yaml` — team roster, phases, model tiers. **Also record
  `target: <active_profile.name>` and embed the resolved `scaffold`, `deploy`,
  `validation`, and `qa_assertions` blocks from the profile so `/start-team`, the
  deploy agent, the QA agent, and the validation loop read them without re-loading
  the profile file.**
- `.agent-team/agents/*.md` — one per agent (customized from templates)
- `.agent-team/phases/*.yaml` — one per phase
- `.agent-team/contracts/*.yaml` — one per producer→consumer edge
- `.agent-team/status/progress.yaml` — initialized with all phases pending
  - Each phase's `steps` must include: read_phase_config, resolve_contracts,
    dispatch_agents, await_agents, merge_worktrees, qa_gate, update_progress,
    introspection — all set to `pending`
  - The FINAL phase's `steps` must ALSO include `adversarial_gate: pending`
    (between `qa_gate` and `update_progress`). Non-final phases must NOT include
    `adversarial_gate` in their steps.
- `.agent-team/artifacts/user-journeys.yaml` — only if generated in Step 1.7 (app teams)

## Step 8: Present Team Summary

Display to the user:
1. Team roster table: agent name, model tier, phase, parallel group
   (list `adversarial-reviewer` in the final phase with role "gate: falsification")
2. Phase plan with agent assignments
3. Contract chain visualization (text-based)
4. Generated artifacts: if `user-journeys.yaml` was written in Step 1.7, list it
   with its journey count and the app-capability gating note
5. Instruction: "Review and edit files in .agent-team/ before running /start-team"
