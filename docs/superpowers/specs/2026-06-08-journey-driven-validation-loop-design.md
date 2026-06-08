# Journey-Driven Validation Loop — Design

**Date:** 2026-06-08
**Status:** Approved (pending implementation plan)
**Branch:** `feat/journey-driven-validation-loop`

## Goal

Add a journey-driven validation loop to the `agent-team` plugin. The QA agent
drives the **deployed app** through **PRD-derived user journeys** in a real
browser, reports issues with reproduction steps and severity, and the PM
orchestrator drives fix iterations. This closes the gap between "code passes
contract/unit checks" and "the product actually does what the PRD promised."

Today the QA agent runs a one-shot progressive checklist (Phases 1–4) whose only
deployed-app check is a single weak line: *"App loads and basic smoke test
passes."* There is no concept of user journeys and no iterative, behavior-level
validation against the product goal.

## Decisions (locked)

| # | Decision |
|---|----------|
| Skill | Vendor the installed `test-deployed-app` skill into the plugin. |
| Vendored name | `app-validation-loop` (namespaced `agent-team:app-validation-loop`). |
| Journey source | `team-builder` generates product journeys from the PRD; `feature-scoper` generates feature-scoped journeys for `/add-feature` (each feature has its own success criteria). PM passes them to QA. |
| Iteration model | PM-orchestrated fix loop. QA stays read-only: it runs journeys and reports. Journey FAIL is treated as a `qa_gate` failure → fix agent → re-run → max 3 attempts → escalate. |
| When it runs | Phase 4 only (post-deploy), and only when the team has a `web-app` or `databricks-app` capability. Pure data/ML teams skip it. |
| deploy-engineer | Emit `app_url` + `app_resource_name` in its status so QA knows what to drive. |

## Components / Changes (7 touch points)

### 1. Vendor the skill → `skills/app-validation-loop/`

Copy from `~/.claude/skills/test-deployed-app/`:
- `SKILL.md`
- `references/journey-definition.md`
- `references/findings-template.md`
- `scripts/drive_journeys.py`

Exclude `scripts/__pycache__/`.

Plugin skills are auto-discovered from `skills/` and namespaced by plugin, so the
vendored copy (`agent-team:app-validation-loop`) does not collide with the user's
global `test-deployed-app`.

**Adaptations to the vendored `SKILL.md`:**
- Rename to `app-validation-loop`; update the `name:` frontmatter and title.
- Add a **"Consume structured journeys"** section: when
  `.agent-team/artifacts/user-journeys.yaml` exists, drive *those* journeys
  directly (skip the "derive journeys from project notes" step), and write
  results to `.agent-team/status/journey-test-results-phase-4.md`. The
  derive-from-notes path remains as a fallback when no structured file exists.
- Lightly genericize the most app-specific framing (e.g. the baseline
  `FILTER_REGEX`, generic agent-app language). Crustopher examples remain as
  illustrative worked examples, clearly marked as examples.
- Keep the dual-channel (UI + backend-log) testing methodology intact — it is the
  highest-value part of the skill.

### 2. New `lib/journey-schema.yaml`

A structured journey contract that bridges PRD text → the `drive_journeys.py`
driver. Fields per journey:

```yaml
journeys:
  - id: J1                         # short id for filenames / log correlation
    name: <human-readable name>
    persona: <who is doing this>
    goal: <what the user is trying to accomplish>
    preconditions: [<state/data needed>]
    steps:
      - action: <navigate|click|type|confirm|...>
        prompt: <verbatim text if a chat/input action>
        expected: <what should happen / which tool/path should fire>
    success_criteria: <falsifiable: a human or grep can check it>
    failure_risk: <what this journey specifically guards against>
    maps_to: <PRD success criterion, or feature name for add-feature journeys>
```

`maps_to` ties every journey back to a product/feature goal so coverage is
auditable and feature journeys are attributable.

### 3. `skills/team-builder/SKILL.md`

Add a step (after PRD parsing) that derives user journeys from the PRD's goal,
"User interactions", and "Success criteria", writing
`.agent-team/artifacts/user-journeys.yaml` per the `lib/journey-schema.yaml`
format.

**Gate:** only generate journeys when the team includes a `web-app` or
`databricks-app` capability. Otherwise skip (no app to drive).

Wire the artifact into Phase 4 so the PM and QA know it exists (see §6).

### 4. `skills/feature-scoper/SKILL.md`

When the scoped feature touches app/UI capabilities (`web-app`, `frontend`,
`databricks-app`, `api-backend` that surfaces UI behavior), generate journeys
scoped to **that feature's** success criteria and append them to
`user-journeys.yaml`, tagging each with `maps_to: <feature_description>`.
Existing product-level journeys are preserved. If the feature touches no app
behavior, skip journey generation.

### 5. `agents/qa-engineer.md` + `templates/core/qa-engineer.yaml`

**Agent (`qa-engineer.md`):** expand the Phase 4 checklist with a **Journey
Validation** block:
- Invoke the `app-validation-loop` skill.
- Read `.agent-team/artifacts/user-journeys.yaml` and the deployed `app_url`
  (provided by the PM in context).
- Drive each journey with dual-channel (UI + backend-log) capture.
- Emit per-journey `PASS | PARTIAL | FAIL` with verbatim prompt, reproduction,
  severity (demo-blocker / intermittent / cosmetic), and evidence into the QA
  status file.
- Remain **read-only** — never fix code. Within a single run, QA may retry a
  journey to rule out transient/cold-start flakiness (the skill handles this),
  but does not modify source.

**Template (`qa-engineer.yaml`):** add `app-validation-loop` to the `skills:`
list.

### 6. `agents/pm-orchestrator.md`

- **`resolve_contracts` (Step 2):** when dispatching the QA agent in Phase 4 and
  `user-journeys.yaml` exists, inject its contents **and** the deployed `app_url`
  (read from `.agent-team/status/deploy-engineer.yaml`) into the QA agent's
  prompt context — mirroring the existing `data-profile.yaml` injection pattern.
- **`qa_gate` (Step 7):** a journey `FAIL` is a gate failure. Dispatch an
  **app-developer** fix agent scoped to the specific failing journeys, re-run the
  journey suite, max 3 attempts, then escalate to human. Reuses the existing fix
  loop; no new control structure.
- Document that Phase 4 QA requires a deployed app URL; if none is present (no app
  team), the journey block is skipped.

### 7. `agents/deploy-engineer.md`

Add to the status YAML (`.agent-team/status/deploy-engineer.yaml`):

```yaml
app_url: <deployed Databricks App URL, or null if no app>
app_resource_name: <bundle resource name of the app, or null>
```

This is the source of truth the PM reads to hand the URL to QA.

## End-to-End Flow

```
/create-team  → team-builder writes user-journeys.yaml   (only if app team)
   └─ /add-feature → feature-scoper appends feature-scoped journeys

/start-team   → PM runs Phases 0–3 (contract/code QA unchanged)
   └─ Phase 4:
        deploy-engineer deploys → emits app_url + app_resource_name
        PM injects user-journeys.yaml + app_url into QA dispatch
        QA invokes app-validation-loop → drives journeys → reports verdicts
        PM: any journey FAIL → app-developer fix agent → re-run suite
            (max 3 attempts) → PASS proceeds / 3 fails escalate
```

## Scope Guards (YAGNI)

- No journeys generated or run for pure data/ML teams (no app surface).
- QA never fixes code; all iteration is PM-orchestrated via the existing loop.
- Phases 1–3 QA behavior is unchanged.
- The vendored skill keeps its battle-tested methodology; we add a thin
  structured-journey input path rather than rewriting it.

## Files Touched

| File | Change |
|------|--------|
| `skills/app-validation-loop/**` | **New** — vendored + adapted skill |
| `lib/journey-schema.yaml` | **New** — structured journey contract |
| `skills/team-builder/SKILL.md` | Generate product journeys from PRD (app teams) |
| `skills/feature-scoper/SKILL.md` | Generate feature-scoped journeys |
| `agents/qa-engineer.md` | Phase 4 Journey Validation block |
| `templates/core/qa-engineer.yaml` | Add `app-validation-loop` skill |
| `agents/pm-orchestrator.md` | Inject journeys + app_url; journey FAIL → fix loop |
| `agents/deploy-engineer.md` | Emit `app_url` + `app_resource_name` |

## Out of Scope

- Pre-deploy / local-dev-server browser testing (the skill explicitly defers that
  to the `web-devloop-tester` agent).
- Changing the Phase 1–3 contract/code validation behavior.
- Auto-generating Chrome/CDP setup; the skill documents its own preconditions.
