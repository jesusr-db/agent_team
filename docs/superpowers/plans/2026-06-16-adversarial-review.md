# Adversarial Review Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent, context-firewalled `adversarial-reviewer` agent that runs as a second gate after functional QA, produces severity-tiered findings, and routes them into the existing PM fix loop — working for the current Databricks team and designed target-agnostic so the future general team inherits it unchanged.

**Architecture:** This is a Claude Code *plugin* — the substrate is Markdown agent definitions, YAML templates/contracts, SKILL.md files, and slash commands (no application code, no pytest harness). "Tests" here are structural validations (YAML parses, frontmatter is well-formed, wiring strings exist) plus an end-to-end dry-run against the bundled test PRD. The adversarial reviewer is a *new registered agent* that the `team-builder` always adds (like `qa-engineer`/`deploy-engineer`), placed in the final phase. The PM orchestrator dispatches it after the final-phase QA gate passes, handing it a deliberately *firewalled* context (spec + contracts + built artifacts only — never the builders' rationale or QA's pass notes), and treats its high-severity findings exactly like a QA failure (route to owning agent, share the `qa_attempts` counter).

**Tech Stack:** Markdown + YAML, the `Agent` tool (curated dispatch via `subagent_type`), git worktree isolation, `python3 -c "import yaml"` for parse validation, `grep` for wiring assertions.

**Branch:** All work in this plan lands on a branch off `main` named `feat/adversarial-review`, then merges to `main`. After merge, `main` carries the adversarial gate and is the base for both the `databricks-team` and `general-team` branches (see the companion plan `2026-06-16-generalize-agent-team.md`).

**Verification substrate note:** Every "run the test" step uses one of three real checks for this repo:
- **Parse check:** `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" <file>` exits 0 on valid YAML.
- **Wiring check:** `grep -q "<string>" <file>` exits 0 when the wiring is present.
- **Dry-run check:** run `/create-team test/qa-chatbot-prd.md` and inspect the generated `.agent-team/` for expected entries (a human/agent reads the output — there is no automated assert for agent behavior, so the expected observation is stated explicitly).

---

## File Structure

**New files:**
- `agents/adversarial-reviewer.md` — registered agent definition (the falsifier). Read-only/analysis tools only; no write-capable MCP tools.
- `templates/core/adversarial-reviewer.yaml` — curated template so `team-builder` discovers and includes it.
- `lib/adversarial-findings-schema.yaml` — structured findings format (severity tiers + routing hints).

**Modified files:**
- `skills/team-builder/SKILL.md` — always include `adversarial-reviewer`; place it in the final phase as a post-QA gate; note it in the team summary.
- `agents/pm-orchestrator.md` — new Step 7.5 `adversarial_gate`; context-firewall rules; findings routing; shared attempt counter; checkpoint + recovery row.
- `agents/qa-engineer.md` — one clarifying paragraph delimiting QA (happy-path/contract) from adversarial review (falsification) so the two gates don't blur.
- `commands/start-team.md` — add `adversarial_gate` to the `--dry-run` execution-plan illustration.
- `.claude-plugin/plugin.json` — bump version to `0.2.0` (agents are auto-discovered from `./agents/`, no manifest list to edit; version bump signals the new capability).

**Reference (unchanged, read for context):** `lib/contract-schema.yaml`, `lib/journey-schema.yaml`, `test/qa-chatbot-prd.md`.

---

## Task 1: Branch setup

**Files:** none (git only)

- [ ] **Step 1: Ensure clean main and branch**

Run:
```bash
git checkout main && git pull --ff-only && git checkout -b feat/adversarial-review
```
Expected: on branch `feat/adversarial-review`, working tree clean.

---

## Task 2: Define the adversarial findings schema

**Files:**
- Create: `lib/adversarial-findings-schema.yaml`

- [ ] **Step 1: Write the schema file**

```yaml
# Adversarial Findings Schema
# Written by the adversarial-reviewer agent to:
#   .agent-team/status/adversarial-findings-phase-<N>.yaml
# Read by the PM orchestrator (Step 7.5) to decide the adversarial gate.
#
# The reviewer's job is to FALSIFY the build, not bless it. Every finding is a
# concrete, reproducible way the build fails to meet the spec/contract or is
# unsafe — never a style nitpick.

schema_version: 1

# Top-level status the PM reads first.
# FAIL  → at least one demo-blocker or high finding exists; PM routes fixes.
# PASS  → no demo-blocker/high findings (medium/low may still be listed as notes).
status: PASS | FAIL

# Ordered list of findings, most severe first.
findings:
  - id: string                      # stable slug, e.g. "auth-bypass-on-delete"
    title: string                   # one line
    severity: demo-blocker | high | medium | low
    category: correctness | contract-violation | security | spec-drift | hallucinated-api | data-integrity
    # Which built surface owns the fix. Maps to an agent the PM can re-dispatch.
    owner_surface: data | pipeline | model | serving-endpoint | app-frontend | app-backend | deployment | contract
    # The spec/PRD line or contract field this falsifies. REQUIRED — a finding
    # with no spec/contract anchor is an opinion, not a finding; drop it.
    falsifies: string
    evidence: string                # file:line, command output, or contract path proving it
    reproduction: string            # exact steps/command to observe the failure
    suggested_fix: string           # optional; what would resolve it (advisory only)

# Free-text reviewer notes: attack surfaces probed, what was NOT checked, and why.
# Lets the PM and humans judge coverage.
coverage_notes: string
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" lib/adversarial-findings-schema.yaml`
Expected: exit 0, no output.

- [ ] **Step 3: Commit**

```bash
git add lib/adversarial-findings-schema.yaml
git commit -m "feat: add adversarial findings schema"
```

---

## Task 3: Create the adversarial-reviewer agent definition

**Files:**
- Create: `agents/adversarial-reviewer.md`

Design constraints (why each choice):
- **Model `opus`** — falsification is hard reasoning; cheaper models rubber-stamp.
- **No write-capable MCP tools.** The reviewer must not be able to mutate the workspace. Read-only DB introspection (`execute_sql`, `get_table_details`) is allowed so it can verify data claims, but no `manage_*`/`create_or_update_*`. This also keeps the agent target-agnostic — the only Databricks tools present are read-only and harmless when absent.
- **Independence/firewall** is enforced by the PM (what it's handed), but the prompt also instructs the agent to ignore any builder rationale if present and reason only from spec + contracts + artifacts.

- [ ] **Step 1: Write the agent definition**

````markdown
---
name: adversarial-reviewer
description: >
  Independent red-team reviewer. Given only the spec/PRD, the contracts, and the
  built artifacts, it actively tries to FALSIFY the build — find correctness bugs,
  contract violations, security holes, spec drift, hallucinated APIs, and data-
  integrity gaps that happy-path QA misses. Read-only: never modifies source.
  Dispatched by the PM orchestrator as a second gate after functional QA.
model: opus
tools: Skill, Read, Glob, Grep, Bash, mcp__databricks-mcp__execute_sql, mcp__databricks-mcp__get_table_details
---

# Adversarial Reviewer

You are an independent adversarial reviewer — a red team of one. Your sole job is
to **falsify** the build: prove, with concrete reproducible evidence, the specific
ways it fails to meet its spec or contracts, or is unsafe. You do not bless work.
You do not award points for effort. A clean report is only credible if you genuinely
tried to break the build and could not.

## Independence (critical)

You reason ONLY from three inputs, provided in your dispatch prompt:
1. The **spec / PRD** — what the build is supposed to do.
2. The **contracts** — `.agent-team/contracts/*.yaml` (producer→consumer obligations).
3. The **built artifacts** — the actual merged code/config in the repo.

If your prompt also contains builder rationale, QA pass notes, or "what went well"
summaries, **ignore them**. They are how the team convinced *itself* the build is
correct; trusting them makes you an echo, not a reviewer. Form your own model of
the spec and attack the artifacts directly.

## Attack surfaces to probe

Work through these deliberately; for each, try to construct a falsifying case:

- **Correctness:** Does the code actually implement the spec's behavior, or only
  the happy path? Off-by-one, wrong aggregation, missing branch, wrong default.
- **Contract violations:** For each contract, does the producer's code actually
  emit every `required: true` column/artifact with the right type? Does the
  consumer reference what the contract promises? Read the code, don't assume.
- **Security:** Hardcoded secrets, missing authz checks on destructive actions,
  injection (SQL/prompt), secrets leaked into frontend bundles or logs, overly
  broad permissions, unauthenticated endpoints.
- **Spec drift:** Features the PRD requires that are silently absent or stubbed;
  features present that the PRD never asked for (scope creep that can hide bugs).
- **Hallucinated APIs:** Calls to functions, SDK methods, table names, or
  endpoints that do not exist. Verify they resolve (grep the repo; for tables,
  use `get_table_details` / `execute_sql` read-only).
- **Data integrity:** Joins that fan out, silent type coercions, null handling
  that drops rows, non-idempotent writes.

## Method

1. Read the spec/PRD and build your own list of falsifiable claims it makes.
2. Read every contract in `.agent-team/contracts/`.
3. For each claim and each contract obligation, locate the implementing artifact
   and try to break it. Prefer evidence you can produce with a command or a
   `file:line` citation over assertion.
4. Tier every confirmed finding by severity:
   - **demo-blocker** — the core PRD flow is wrong/broken or a live security hole.
   - **high** — a contract is violated or a required feature is missing/incorrect.
   - **medium** — a real defect off the critical path.
   - **low** — minor robustness/hardening gap.
5. Drop anything you cannot anchor to a spec line or contract field. If it's an
   opinion, it's not a finding.

## Output Requirements

Write findings to `.agent-team/status/adversarial-findings-phase-{{phase}}.yaml`,
following `lib/adversarial-findings-schema.yaml` exactly. Set top-level
`status: FAIL` if any `demo-blocker` or `high` finding exists, else `status: PASS`.
Always fill `coverage_notes` with what you probed and what you did NOT get to.

## Constraints

- **Read-only.** Never modify source, config, or data. You diagnose; the PM
  dispatches a fix agent. Writing is limited to your one findings file under
  `.agent-team/status/`.
- Every finding MUST set `falsifies` (the spec line or contract field) and
  `evidence`. No anchor → not a finding.
- Do not re-run the happy-path QA suite; assume it passed. Your value is the
  cases it did not cover.

## Status Protocol

When finished, write your status to `.agent-team/status/adversarial-reviewer.yaml`:
```yaml
status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
artifacts: [.agent-team/status/adversarial-findings-phase-{{phase}}.yaml]
finding_counts: {demo_blocker: N, high: N, medium: N, low: N}
gate: PASS | FAIL   # mirrors the findings file top-level status
```
````

- [ ] **Step 2: Verify frontmatter is well-formed**

Run:
```bash
python3 -c "
import sys
t=open('agents/adversarial-reviewer.md').read()
assert t.startswith('---'), 'no frontmatter'
fm=t.split('---',2)[1]
import yaml; d=yaml.safe_load(fm)
assert d['name']=='adversarial-reviewer', d.get('name')
assert d['model']=='opus', d.get('model')
assert 'manage' not in d['tools'] and 'create_or_update' not in d['tools'], 'reviewer must not have write MCP tools'
print('ok')
"
```
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add agents/adversarial-reviewer.md
git commit -m "feat: add adversarial-reviewer agent (read-only falsifier)"
```

---

## Task 4: Create the curated template so team-builder includes it

**Files:**
- Create: `templates/core/adversarial-reviewer.yaml`

This mirrors the shape of `templates/core/qa-engineer.yaml` (read it first if unsure)
so `team-builder` Step 3 can match it. The `capabilities` entry `adversarial-review`
is a sentinel the team-builder always activates (Task 5), not a PRD-triggered tag.

- [ ] **Step 1: Write the template**

```yaml
name: adversarial-reviewer
display_name: Adversarial Reviewer
description: Independent red-team gate that tries to falsify the build after functional QA
model: opus
registered_agent: agents/adversarial-reviewer.md
typical_phases: [final]      # runs in the last phase, after the QA gate

capabilities:
  - adversarial-review       # sentinel: always included, like qa/deploy

skills: []

# Read-only introspection only. Present for the Databricks target; harmless/absent
# for other targets. The reviewer never gets write-capable tools.
mcp_tools:
  - databricks-mcp:execute_sql
  - databricks-mcp:get_table_details

output_paths:
  - .agent-team/status/adversarial-findings-phase-*.yaml
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" templates/core/adversarial-reviewer.yaml`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add templates/core/adversarial-reviewer.yaml
git commit -m "feat: add adversarial-reviewer curated template"
```

---

## Task 5: Wire team-builder to always include the adversarial reviewer

**Files:**
- Modify: `skills/team-builder/SKILL.md`

Three edits: (a) declare the always-include rule next to qa/deploy; (b) add a capability-table row documenting the sentinel; (c) place it in the final phase after QA in the phase algorithm; (d) surface it in the team summary.

- [ ] **Step 1: Add the always-include rule (Step 3 of the skill)**

Find this block:
```markdown
Always include these agents regardless of capabilities:
- **qa-engineer** (always needed for validation)
- **deploy-engineer** (always needed for deployment)
```
Replace with:
```markdown
Always include these agents regardless of capabilities:
- **qa-engineer** (always needed for validation)
- **deploy-engineer** (always needed for deployment)
- **adversarial-reviewer** (always needed; independent red-team gate that runs
  in the final phase AFTER the qa-engineer gate passes — see Step 5)
```

- [ ] **Step 2: Add a capability-table row**

Find this row in the Step 2 capability table:
```markdown
| deployment | DAB configuration, CI/CD |
```
Add immediately below it:
```markdown
| adversarial-review | Always present (sentinel) — independent falsification gate after QA |
```

- [ ] **Step 3: Place it in the phase algorithm (Step 5)**

Find this block:
```markdown
5. Deploy → Phase 4 (always last)
```
Replace with:
```markdown
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
```

- [ ] **Step 4: Surface it in the team summary (Step 8)**

Find this line in Step 8:
```markdown
1. Team roster table: agent name, model tier, phase, parallel group
```
Replace with:
```markdown
1. Team roster table: agent name, model tier, phase, parallel group
   (list `adversarial-reviewer` in the final phase with role "gate: falsification")
```

- [ ] **Step 5: Verify the wiring strings exist**

Run:
```bash
grep -q "adversarial-reviewer (always needed" skills/team-builder/SKILL.md && \
grep -q "| adversarial-review |" skills/team-builder/SKILL.md && \
grep -q "gates:" skills/team-builder/SKILL.md && echo ok
```
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat: team-builder always includes adversarial-reviewer as a final-phase gate"
```

---

## Task 6: Add the adversarial gate to the PM orchestrator

**Files:**
- Modify: `agents/pm-orchestrator.md`

This is the behavioral core. Four edits: (a) new Step 7.5 `adversarial_gate`; (b) recovery-table row; (c) the progress.yaml `steps` list must include the new step; (d) a Rules entry.

- [ ] **Step 1: Insert Step 7.5 after the qa_gate step (Step 7)**

Find the end of the Step 7 block — the line:
```markdown
- **Checkpoint:** Write QA attempt count and result
- Track in `qa_attempts` field
```
Insert immediately after it (before `### Step 8: update_progress`):
```markdown

### Step 7.5: adversarial_gate (final phase only)

Run this gate ONLY in the final phase, and ONLY after Step 7 (qa_gate) returns
PASS. It is a second, independent gate — the red team.

**Context firewall (critical):** Dispatch `adversarial-reviewer` with a prompt
containing ONLY:
- the project description / PRD spec (from the team manifest),
- the list of contract files in `.agent-team/contracts/` (paths — the agent reads them),
- the built artifacts (the merged repo state — the agent reads files directly).

Do NOT include: builder agents' status rationale, QA `checks`/pass notes,
introspection text, or "what went well" summaries. Handing those over turns the
reviewer into an echo. Dispatch in a fresh worktree like any other agent.

```
Agent(
  description: "adversarial-reviewer - Phase N falsification gate"
  subagent_type: "adversarial-reviewer"
  prompt: "<PRD spec text> + <list of .agent-team/contracts/*.yaml paths> +
           'The built artifacts are the current repo state. Try to falsify the
            build per your definition. Write findings to
            .agent-team/status/adversarial-findings-phase-N.yaml.'"
  isolation: "worktree"
)
```

After it returns, read `.agent-team/status/adversarial-findings-phase-N.yaml`:
- **status: PASS** → gate passes. Note any medium/low findings in the phase report
  (informational), then proceed to Step 8.
- **status: FAIL** → treat exactly like a QA failure. For each `demo-blocker`/`high`
  finding, route the fix to the agent that owns `owner_surface`:
  - `app-frontend` / `app-backend` → `app-developer`
  - `serving-endpoint` / `model` → `data-scientist` or `genai-architect`
  - `data` / `pipeline` → `data-engineer`
  - `deployment` → `deploy-engineer`
  - `contract` → the producer agent named in the violated contract
  Dispatch the owning agent scoped to the specific finding(s), passing the
  `evidence` and `reproduction` from the findings file. Then re-run Step 7 (qa_gate)
  AND re-run this Step 7.5 to confirm the fix and that it introduced no regression.

**Shared attempt counter:** adversarial fix cycles share the phase's `qa_attempts`
counter (the same 3-attempt cap that covers QA failures). After 3 combined failed
attempts across qa_gate + adversarial_gate, escalate to human via
`.agent-team/status/escalation.md`.

- **Checkpoint:** Write `phases[N].steps.adversarial_gate` status and the gate
  result; commit progress.yaml.
```

- [ ] **Step 2: Add the recovery-table row**

Find this row in the Auto-Recovery Logic table:
```markdown
| qa_gate | Re-run QA from scratch (stateless) |
```
Add immediately below it:
```markdown
| adversarial_gate | Re-run adversarial review from scratch (stateless); re-read findings file |
```

- [ ] **Step 3: Update the required progress.yaml steps list**

This list is authored by team-builder but the PM documents the contract. Find this
block (Step 7 of team-builder is the writer, but the PM's Startup section relies on
it). In `agents/pm-orchestrator.md`, find the Rules section:
```markdown
## Rules

- NEVER skip QA gates
```
Replace with:
```markdown
## Rules

- NEVER skip QA gates
- NEVER skip the adversarial gate in the final phase
```

- [ ] **Step 4: Note the new step in the final-phase steps requirement**

Also update `skills/team-builder/SKILL.md` Step 7 so the generated progress.yaml
includes the new step for the final phase. Find:
```markdown
  - Each phase's `steps` must include: read_phase_config, resolve_contracts,
    dispatch_agents, await_agents, merge_worktrees, qa_gate, update_progress,
    introspection — all set to `pending`
```
Replace with:
```markdown
  - Each phase's `steps` must include: read_phase_config, resolve_contracts,
    dispatch_agents, await_agents, merge_worktrees, qa_gate, update_progress,
    introspection — all set to `pending`
  - The FINAL phase's `steps` must ALSO include `adversarial_gate: pending`
    (between `qa_gate` and `update_progress`)
```

- [ ] **Step 5: Verify wiring strings exist**

Run:
```bash
grep -q "### Step 7.5: adversarial_gate" agents/pm-orchestrator.md && \
grep -q "Context firewall (critical)" agents/pm-orchestrator.md && \
grep -q "| adversarial_gate |" agents/pm-orchestrator.md && \
grep -q "NEVER skip the adversarial gate" agents/pm-orchestrator.md && \
grep -q "adversarial_gate: pending" skills/team-builder/SKILL.md && echo ok
```
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add agents/pm-orchestrator.md skills/team-builder/SKILL.md
git commit -m "feat: PM orchestrator runs firewalled adversarial gate after final QA"
```

---

## Task 7: Delimit QA vs adversarial review in the QA agent

**Files:**
- Modify: `agents/qa-engineer.md`

Prevents the two gates from blurring — QA owns happy-path + contract conformance;
the adversarial reviewer owns falsification. Without this, both agents may try to
do the same job (or neither does the adversarial one well).

- [ ] **Step 1: Add the delimiter paragraph**

Find the opening:
```markdown
# QA Engineer

You are a Senior QA Engineer on a cross-functional agent team.
```
Replace with:
```markdown
# QA Engineer

You are a Senior QA Engineer on a cross-functional agent team.

**Your scope vs. the adversarial reviewer:** You validate that the build does what
it should on the intended paths — syntax, contract conformance, integration shapes,
and the PRD's happy-path journeys. A separate `adversarial-reviewer` agent runs
after you in the final phase and owns *falsification* (trying to break the build,
security holes, spec drift, hallucinated APIs). Do not attempt adversarial red-teaming
yourself — report what you verify, pass cleanly when the intended behavior holds,
and let the independent gate probe for what you did not cover.
```

- [ ] **Step 2: Verify**

Run: `grep -q "Your scope vs. the adversarial reviewer" agents/qa-engineer.md && echo ok`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add agents/qa-engineer.md
git commit -m "docs: delimit qa-engineer scope from adversarial-reviewer"
```

---

## Task 8: Reflect the gate in the start-team dry-run illustration

**Files:**
- Modify: `commands/start-team.md`

- [ ] **Step 1: Update the --dry-run example**

Find:
```markdown
  Phase 4 (Deploy): deploy-engineer (sonnet) → qa-engineer (sonnet)
```
Replace with:
```markdown
  Phase 4 (Deploy): deploy-engineer (sonnet) → qa-engineer (sonnet) → adversarial-reviewer (opus, gate)
```

- [ ] **Step 2: Verify**

Run: `grep -q "adversarial-reviewer (opus, gate)" commands/start-team.md && echo ok`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add commands/start-team.md
git commit -m "docs: show adversarial gate in start-team dry-run plan"
```

---

## Task 9: Version bump

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version**

Find: `"version": "0.1.0",`
Replace with: `"version": "0.2.0",`

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" && echo ok`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "chore: bump plugin to 0.2.0 (adversarial gate)"
```

---

## Task 10: End-to-end dry-run validation against the test PRD

**Files:** none (validation only)

This is the integration test. There is no automated assert for agent behavior, so
the expected observation is stated explicitly; an engineer (or a dispatched agent)
runs it and confirms.

- [ ] **Step 1: Assemble a team from the bundled test PRD**

Run: `/create-team test/qa-chatbot-prd.md`
(If `.agent-team/` already exists from a prior run, move it aside first:
`mv .agent-team .agent-team.bak` — restore or delete after.)

- [ ] **Step 2: Confirm the adversarial reviewer was included**

Run:
```bash
grep -rq "adversarial-reviewer" .agent-team/team-manifest.yaml && \
grep -rq "gates:" .agent-team/phases/*.yaml && \
grep -rq "adversarial_gate" .agent-team/status/progress.yaml && echo ok
```
Expected: `ok` — the reviewer is on the roster, the final phase lists it under
`gates:`, and the final phase's progress steps include `adversarial_gate: pending`.

- [ ] **Step 3: Confirm the final-phase config places it as a gate, not a build agent**

Read the final phase YAML (`.agent-team/phases/phase-*-*.yaml`, highest N). Confirm
`adversarial-reviewer` appears under `gates:` and NOT under any `parallel_group`.
Expected observation: it is a gate entry.

- [ ] **Step 4: Clean up**

Run: `rm -rf .agent-team && [ -d .agent-team.bak ] && mv .agent-team.bak .agent-team || true`
(Do not commit the test-generated `.agent-team/`.)

- [ ] **Step 5: Commit nothing / note result**

No commit. If any check failed, return to the relevant task before merging.

---

## Task 11: Merge to main

**Files:** none (git only)

- [ ] **Step 1: Final parse sweep**

Run:
```bash
for f in lib/adversarial-findings-schema.yaml templates/core/adversarial-reviewer.yaml; do
  python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$f" || echo "FAIL: $f"
done
python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" || echo "FAIL: plugin.json"
echo "sweep done"
```
Expected: `sweep done` with no `FAIL:` lines.

- [ ] **Step 2: Merge**

```bash
git checkout main
git merge --no-ff feat/adversarial-review -m "feat: adversarial review gate"
```
Expected: clean merge.

- [ ] **Step 3: (Optional) push**

Only if the user confirms pushing. `git push origin main`.

---

## Self-Review (completed by plan author)

**Spec coverage** (against the brainstorm's adversarial-review recommendation, sub-option A1):
- Independent agent, runs after functional QA in the final phase → Task 3, Task 6 (Step 7.5). ✓
- Context firewalled (spec + contracts + artifacts only, not builder rationale/QA notes) → Task 6 Step 1 firewall block + Task 3 "Independence" section. ✓
- Severity-tiered findings → Task 2 schema (`demo-blocker|high|medium|low`). ✓
- Findings feed the same fix loop, routed by owner, shared attempt counter → Task 6 Step 1. ✓
- Target-agnostic so the general team inherits it → Task 3 (read-only tools, no Databricks-specific reasoning) + Task 4 (read-only MCP only). ✓
- Lands on main as shared foundation → Task 1, Task 11. ✓

**Placeholder scan:** No TBD/TODO; every new file has complete content; every edit shows find+replace text; every verification has an exact command and expected output. ✓

**Type/name consistency:** `adversarial-reviewer` (agent name), `adversarial_gate` (PM step + progress key), `adversarial-findings-phase-<N>.yaml` (findings file), `gates:` (phase key), `status: PASS|FAIL` (findings top-level), `qa_attempts` (shared counter) — used identically across Tasks 2–10. ✓

**Known gap (intentional):** This plan does not make the adversarial reviewer *target-aware* (e.g., target-specific security checklists). That is deferred to the generalization plan, where targets exist. The reviewer here is target-*agnostic*, which is correct for landing on main today.
