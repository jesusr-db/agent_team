---
description: "UX/UI-focused improvement pass on an existing app — audits the rendered UI, redesigns, rebuilds, and gates on the ux-critic"
---

# /improve-ux

You are running a UX/UI-focused improvement loop on an existing Databricks application.

## Input

`{{ARGUMENTS}}` — the UX direction, plus optional flags:
- `--human off|async|checkpoint` — human review mode at the critic gate (default `async`, 5 minutes)
- `--no-deploy` — stop after the design is approved; skip deploy and journey validation (default: deploy, then validate)

**Auto-detect input type:**
- If the argument (minus flags) is a path to an existing file, use Read to load it as the direction.
- Otherwise treat it as inline text. An empty direction is allowed: the audit alone drives the work.

## Validation

Verify the project exists: `src/` must exist, OR `databricks.yml` must exist. Otherwise tell the user:
```
No existing project found. Use /create-team to start a new project instead.
```
Also verify the app has a UI (a frontend under `src/`). If not, say so and stop.

## Execution

### 1. Invoke ux-scoper Skill

Invoke the `ux-scoper` skill with the direction and flags. It will:
- Snapshot the current app (pages, routes, run command, existing design artifacts)
- Derive a lightweight `ux-brief.yaml` if none exists
- Write a scoped `.agent-team/` config with `mode: incremental` and `focus: ux`
- Create a `ux-focus/<slug>` git tag on the current commit (rollback point)

### 2. Confirm Scoped Configuration

Display:
```
UX direction: <direction or "audit-driven">

Phase 0: ux-critic (audit of the app as it is today)
Phase 1: ui-ux-analyst (redesign from audit + direction)
Phase 2: app-developer (rebuild affected pages), qa-engineer, gate: ux-critic
         (design approved here: by you, or by the critic if you don't respond)
Phase 3: deploy-engineer (redeploys the approved UI)
Phase 4: qa-engineer (user journeys against the deployed app)
[Phases 3-4 omitted with --no-deploy]

Human review: <off|async 5 min|checkpoint>
Git tag created: ux-focus/<slug>  (rollback point)
```
Ask: "Proceed with /start-team? (yes / review .agent-team/ first / cancel)"

### 3. Invoke /start-team

If confirmed, invoke `/start-team`. It detects `mode: incremental` and `focus: ux`, and the
pm-orchestrator skill runs its UX-focus mode: audit first, then a pause at the Phase 0
boundary where the user can review findings and add comments to `.agent-team/status/ux-feedback.md`.

## Rollback

```bash
git show ux-focus/<slug>                    # the pre-change state
git reset --hard ux-focus/<slug>            # discard all UX changes
git checkout -b rollback/<slug> ux-focus/<slug>   # or compare on a branch
```
