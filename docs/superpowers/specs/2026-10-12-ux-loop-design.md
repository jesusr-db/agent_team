# UI/UX Loop — Design

**Date:** 2026-10-12
**Branch:** `feat/ux-loop` (off `fix/orchestrator-root-nesting`)
**Status:** Implemented in plugin v0.3.0 (spec and implementation were approved together in conversation; no separate review stop).

## Goal

Add a design-and-review loop for application UI. SME research drives the UX; installed UI skills shape the design; a critic reviews the **rendered** app before deploy; findings are fixed in a bounded loop; a human can optionally add direction.

## Constraints

- Orchestrator runs in the main session. Every other agent is a one-level subagent dispatched by it. No worker has the `Agent` tool.
- The critic judges rendered output (screenshots of the running app), not only code.
- `brandkit` is out of scope. A brand picker (Domino's, Databricks, Casey's) is roadmap, tracked in the README.

## Components

1. **Domain SME (Phase 0)** also writes `.agent-team/artifacts/ux-brief.yaml`: personas, decisions and cadence, vocabulary, data-density expectations, trust needs.
2. **`ui-ux-analyst` (Phase 1)** reads the brief, resolves a UI skill stack from installed skills, and writes the existing wireframes and component contract plus `ui-design-spec.yaml` (`lib/ui-design-spec-schema.yaml`): tokens, per-screen states, a11y targets, viewports, skill stack used.
3. **`app-developer` (Phase 2)** unchanged except it records `run_command` and `health_url` in its status file.
4. **`ux-critic` (new gate agent)** runs after the build phase's QA gate and before deploy. It starts the app locally, drives each route with Playwright, captures screenshots and console output, and writes `ux-findings-phase-N.yaml` (`lib/ux-findings-schema.yaml`). Read-only on source.
5. **Orchestrator Step 7.4 (`ux_gate`)** triggers when the phase `gates:` list includes `ux-critic`, runs the fix loop, and handles the optional human review.

## Fix loop

Critic FAIL → route findings by `owner` → spec fixes (`ui-ux-analyst`) before rebuilds (`app-developer`) → re-run the critic with previously failing IDs first plus a regression pass. Shares the phase `qa_attempts` counter (cap 3). If two consecutive attempts return the same finding IDs, escalate early. Each attempt is kept as `ux-findings-phase-N-attemptK.yaml`. Blocker and major findings fail the gate; minor findings are logged.

## Human in the loop

`team-manifest.yaml`:

```yaml
ux_review:
  human: async        # off | async | checkpoint
  wait_minutes: 5
```

- `async` (default): after attempt 1 only, print the local app link and `ux-feedback.md` path; poll up to `wait_minutes` for the file to be saved; no response means continue with agent findings.
- `checkpoint`: stop and ask the user before continuing.
- `off`: agent-only.

Human comments become findings with `source: human`, ranked above agent findings. Design-level direction goes to `ui-ux-analyst` first.

## Failure behavior

If the app cannot start locally, the gate reports `BLOCKED` with the reason and the orchestrator asks the user whether to deploy first and critique the deployed app, or skip the gate. It never silently passes.

## Out of scope

Brand picker and `brandkit` (roadmap). Deployed-app critique pass (only offered as the fallback above).
