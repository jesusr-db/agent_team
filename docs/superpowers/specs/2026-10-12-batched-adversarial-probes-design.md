# Batched Adversarial Probes — Design

**Date:** 2026-10-12
**Branch:** `feat/batched-adversarial-probes` (off `databricks-team`)
**Status:** Implemented in plugin v0.3.1.

## Goal

Replace the adversarial reviewer's one-call-at-a-time probing with rounds of batched probes: write a batch, run it once, analyze the structured results, and use them to write a more targeted next batch.

## Decisions

- **Rounds, not one big batch.** Adversarial work is adaptive; round 1 is broad, rounds 2-3 target what round 1 found. Cap 3 rounds, stop early when a round yields no new FALSIFIED/ERROR probe.
- **Three batch kinds** (`lib/adversarial-probe-schema.yaml`): data (one-time notebook/SQL run), http (`lib/run_http_probes.py`), static (grep/AST script).
- **Data batches are never persistent bundle resources.** Run as a one-time job (`databricks jobs submit` or a throwaway bundle target); write probes only to a scratch schema, dropped at the end.
- **HTTP safety.** Mutating probes only against the locally started app; deployed app is GET-only (the runner SKIPs the rest).
- **ERROR is never a pass.** Transport/SQL errors are recorded as ERROR and surfaced in coverage.
- **Evidence is reproducible.** Probes live in `.agent-team/review/round-K/` with stable ids; findings carry `probe_id`; after a fix the reviewer re-runs only the probes behind prior findings plus one regression round (re-review mode).
- **Independence preserved.** The reviewer writes probes from the spec and contracts only. Its tools gain `Write`, limited to `.agent-team/status/` and `.agent-team/review/`.
- The 3-attempt cap is unchanged: rounds happen inside one reviewer dispatch.

## Files

New: `lib/adversarial-probe-schema.yaml`, `lib/run_http_probes.py`. Changed: `agents/adversarial-reviewer.md`, `lib/adversarial-findings-schema.yaml` (`probe_id`, `rounds`), `templates/core/adversarial-reviewer.yaml`, `skills/pm-orchestrator/SKILL.md` (Step 7.5 inputs, re-review mode, recovery), README, workflow.

## Open items

HTTP probes against the deployed app are GET-only by default; widen only on explicit user approval.
