---
name: ux-scoper
description: Scopes a UX/UI-focused improvement pass on an existing app. Snapshots the current UI, derives a ux-brief if none exists, and writes a scoped incremental .agent-team/ config (audit, redesign, rebuild, critic gate). Invoked by /improve-ux.
---

# UX Scoper

You are scoping a UX-focused pass on an existing Databricks application. Output is a
minimal `.agent-team/` configuration; you write config only, never application code.
This mirrors `feature-scoper` (reuse its Step 1 discovery approach) but fixes the team
shape around the UI.

## Step 1: Discover Current State

Same scan as `feature-scoper` Step 1 (`src/`, `resources/`, `tests/`, `databricks.yml`,
CLAUDE.md `## Introspection`, existing `.agent-team/` history; copy an existing manifest
to `.agent-team/team-manifest.previous.yaml`). Additionally record:

- `frontend_pages`: routes/pages and their components
- `app_run`: how to start the app locally and a health URL. Look in `app.yaml`,
  `package.json` scripts, README, `src/app/backend`. If you cannot determine them, ask
  the user once; do not guess.
- `existing_ux_artifacts`: any of `ux-brief.yaml`, `ui-design-spec.yaml`,
  `ui-component-contract.yaml`, `ui-wireframes/`, `ui-workflow.md`
- `app_genre` guess (analytic-dashboard, report, chat-data-assistant, form-workflow, ...)

## Step 2: Parse Direction

Take the user's direction (free text or file). Extract concrete asks (e.g. "denser
overview", "add empty states") into a `direction` string preserved verbatim, plus a short
`direction_summary` list. Do not reinterpret or expand it. Empty direction is valid.

## Step 3: Derive a Lightweight UX Brief (only if none exists)

If `.agent-team/artifacts/ux-brief.yaml` is missing, write one from CLAUDE.md
introspection, the PRD/README if present, the code (routes, labels, API shapes) and the
direction, using the keys in the domain SME generator (`personas`, `decisions`,
`vocabulary`, `data_density`, `trust_needs`, `risky_flows`, `domain_mental_models`).
Add top-level `derived: true` and `confidence: low|medium` and list what you inferred
vs. what was stated. Never invent compliance requirements. No SME agent runs in this
mode, so tell the user the brief is derived and invite correction at the confirm step.

## Step 4: Fixed Team Shape

Write `.agent-team/team-manifest.yaml`:

```yaml
mode: incremental
focus: ux
feature_description: "UX improvement: <direction_summary or 'audit-driven'>"
direction: "<verbatim direction>"
previous_manifest: ".agent-team/team-manifest.previous.yaml"
project_snapshot: <from Step 1>
app_run: {run_command: "...", health_url: "..."}
ux_review: {human: <flag or async>, wait_minutes: 5}
```

Agents (write only these definitions to `.agent-team/agents/`, reusing existing ones):

| Phase | Agents | Notes |
|---|---|---|
| 0 | `ux-critic` | ordinary agent, `mode: audit`, not a gate |
| 1 | `ui-ux-analyst` | inputs: audit findings, ux-brief, direction, existing design artifacts (incremental mode: status new/modified/unchanged per page) |
| 2 | `app-developer`, `qa-engineer`; gates `[qa-engineer, ux-critic]` | rebuild only pages with `status: new|modified` |
| 3 | `deploy-engineer` | redeploys AFTER the UX gate approves the design; omit with `--no-deploy` |
| 4 | `qa-engineer` | journey validation (`app-validation-loop`) against the deployed `app_url`; omit with `--no-deploy` |

Deploy and validation run only once the design is approved: the Phase 2 `ux-critic` gate
passing (and, in `checkpoint` mode, the user's explicit go-ahead) is the approval. Do not
deploy a design the gate has not passed.

Journeys: if `.agent-team/artifacts/user-journeys.yaml` exists, append journeys for the
changed pages and never drop existing ones; if it does not, derive 3-5 journeys per
`lib/journey-schema.yaml` from the routes, the brief and the direction. Each sets `maps_to`
to the direction item or audit finding it protects against regressing. Phase 4 follows the
normal `app_url` / journey rules in pm-orchestrator Step 2 and Step 7.

No data agents, no domain SME, no adversarial-reviewer by default (offer it at the
confirm step if the UI change touched auth, data access, or a Genie surface).

Phase 0 and Phase 2 YAMLs follow `phase-planner`; Phase 2 carries the `gates:` list so the
orchestrator triggers Step 7.4. Initialize `progress.yaml` with each phase's steps; the
Phase 2 steps include `ux_gate: pending`.

## Step 5: Contracts

- `ux-audit-to-design`: producer `ux-critic`, consumer `ui-ux-analyst`; artifact
  `.agent-team/status/ux-findings-audit.yaml`; validation `artifact_exists`.
- `ui-to-app` (existing pattern): producer `ui-ux-analyst`, consumer `app-developer`;
  existing app code and APIs are `access: read-only` for the analyst, and the developer may
  change backend only where a finding requires it.

## Step 6: Rollback Point

Create the tag on the current commit: `git tag ux-focus/<slug>` where `<slug>` is a
short kebab-case summary of the direction (or `audit-<date>`). If the working tree is
dirty, tell the user to commit first rather than tagging uncommitted work.
