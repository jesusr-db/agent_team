# Journey-Driven Validation Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the agent-team plugin a journey-driven validation loop where the QA agent drives the deployed app through PRD-derived user journeys and the PM orchestrates fix iterations.

**Architecture:** Vendor the installed `test-deployed-app` skill into the plugin as `app-validation-loop`. `team-builder` (product) and `feature-scoper` (per-feature) derive structured user journeys from the PRD into `.agent-team/artifacts/user-journeys.yaml`. In Phase 4, the PM injects those journeys plus the deployed app URL into the QA agent, which invokes the vendored skill to drive each journey and reports verdicts; journey failures route through the existing `qa_gate` fix loop.

**Tech Stack:** Claude Code plugin (skills as `SKILL.md`, agents as markdown with YAML frontmatter, contracts/config as YAML). Vendored skill ships a Python Playwright driver. Verification uses `grep`, `python3 -c "import yaml"`, and plugin skill-discovery checks — there is no application test suite in this repo.

**Source of the vendored skill:** `~/.claude/skills/test-deployed-app/` (SKILL.md, references/journey-definition.md, references/findings-template.md, scripts/drive_journeys.py).

**Branch:** `feat/journey-driven-validation-loop` (already created; the spec commit is the first commit on it).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `skills/app-validation-loop/SKILL.md` | **New** — vendored + adapted skill; methodology for driving a deployed app through journeys, with a structured-journey input path |
| `skills/app-validation-loop/references/journey-definition.md` | **New** — vendored journey-quality reference |
| `skills/app-validation-loop/references/findings-template.md` | **New** — vendored findings doc template |
| `skills/app-validation-loop/scripts/drive_journeys.py` | **New** — vendored Playwright/CDP driver |
| `lib/journey-schema.yaml` | **New** — structured journey contract (shape of `user-journeys.yaml`) |
| `skills/team-builder/SKILL.md` | Add a step that derives product journeys from the PRD (app teams only) |
| `skills/feature-scoper/SKILL.md` | Add a step that derives feature-scoped journeys (app-touching features only) |
| `agents/deploy-engineer.md` | Emit `app_url` + `app_resource_name` in status |
| `agents/qa-engineer.md` | Phase 4 Journey Validation block + skill reference |
| `templates/core/qa-engineer.yaml` | Add `app-validation-loop` to `skills:` |
| `agents/pm-orchestrator.md` | Inject journeys + app_url into Phase 4 QA; route journey FAIL through qa_gate fix loop |

No change to `.claude-plugin/plugin.json` — it declares `"skills": "./skills/"`, so the vendored skill is auto-discovered.

---

## Task 1: Vendor the `app-validation-loop` skill

**Files:**
- Create: `skills/app-validation-loop/SKILL.md`
- Create: `skills/app-validation-loop/references/journey-definition.md`
- Create: `skills/app-validation-loop/references/findings-template.md`
- Create: `skills/app-validation-loop/scripts/drive_journeys.py`

- [ ] **Step 1: Copy the skill tree (excluding bytecode cache)**

Run:
```bash
cd /Users/jesus.rodriguez/Documents/ItsAVibe/gitrepos_FY27/agent_team
mkdir -p skills/app-validation-loop/references skills/app-validation-loop/scripts
rsync -a --exclude='__pycache__' ~/.claude/skills/test-deployed-app/ skills/app-validation-loop/
```

- [ ] **Step 2: Verify the files landed and no bytecode came along**

Run:
```bash
find skills/app-validation-loop -type f | sort
```
Expected: exactly these four files, no `__pycache__`:
```
skills/app-validation-loop/SKILL.md
skills/app-validation-loop/references/findings-template.md
skills/app-validation-loop/references/journey-definition.md
skills/app-validation-loop/scripts/drive_journeys.py
```

- [ ] **Step 3: Rename the skill in frontmatter and title**

In `skills/app-validation-loop/SKILL.md`, change the frontmatter `name:` from `test-deployed-app` to `app-validation-loop`, update the `description:` to lead with the agent-team use case, and change the H1 title.

Replace the frontmatter block and title. The opening of the file currently is:
```markdown
---
name: test-deployed-app
description: "Drive an already-deployed, OAuth-authenticated web app (Databricks Apps, internal tools, etc.) from Claude Code without a session restart. Two paths — Playwright + CDP (works in any session) and chrome-devtools MCP (cleaner but needs restart). Use when asked to browser-test the app, run a user journey, drive the deployed UI, click through the app, smoke-test the UI, or verify a deployed change end-to-end in a real browser."
---

# Test Deployed App
```
Change it to:
```markdown
---
name: app-validation-loop
description: "Drive an already-deployed, OAuth-authenticated web app through user journeys in a real browser, capturing UI + backend-log evidence per journey. Used by the agent-team QA engineer in Phase 4: reads structured journeys from .agent-team/artifacts/user-journeys.yaml when present, otherwise derives them from project notes. Two paths — Playwright + CDP (works in any session) and chrome-devtools MCP (needs restart). Use to validate a deployed build against the PRD's user journeys, smoke-test the UI, or verify a deployed change end-to-end."
---

# App Validation Loop
```

- [ ] **Step 4: Add the "Consume structured journeys" section**

In `skills/app-validation-loop/SKILL.md`, locate the section that begins with `## Deriving journeys from project notes`. Insert the following new section **immediately before** it:

````markdown
## Consume structured journeys (agent-team integration)

When invoked inside an agent-team run, the journeys have already been derived
from the PRD/feature by `team-builder` / `feature-scoper`. **Do not re-derive
them.** Instead:

1. Read `.agent-team/artifacts/user-journeys.yaml`. Each entry follows
   `lib/journey-schema.yaml` (`id`, `name`, `persona`, `goal`, `preconditions`,
   `steps[].action|prompt|expected`, `success_criteria`, `failure_risk`,
   `maps_to`). Drive each journey in order.
2. Read the deployed app URL from the dispatch context (the PM passes `app_url`
   and `app_resource_name`, sourced from `.agent-team/status/deploy-engineer.yaml`).
   Use `app_url` as `$APP_URL` for the launch + driver steps.
3. For each journey, capture **both** channels (UI screenshot + final text via
   Playwright, and backend evidence via `databricks apps logs <app_resource_name>`)
   exactly as in the dual-channel section below.
4. Write results to `.agent-team/status/journey-test-results-phase-4.md` using the
   findings template, and record a per-journey verdict line
   (`PASS | PARTIAL | FAIL`) with severity (`demo-blocker | intermittent | cosmetic`),
   verbatim prompt/action, reproduction, and the `maps_to` criterion.

**Only fall back to "Deriving journeys from project notes" (below) when
`.agent-team/artifacts/user-journeys.yaml` is absent.**

This skill never edits source code. If journeys fail, report them — the PM
orchestrator dispatches a fix agent and re-runs the suite.
````

- [ ] **Step 5: Lightly genericize the baseline log filter**

In `skills/app-validation-loop/SKILL.md`, the dual-channel section has a baseline
`FILTER_REGEX`. Leave the regex itself intact (it is generic enough), but ensure
the surrounding prose says "for any agent-app, augment with project-specific
patterns surfaced in the app's `CLAUDE.md` or the journey `failure_risk` fields"
rather than implying Crustopher specifics are required. Make this one-line edit to
the sentence introducing project-specific augmentation:

Find:
```
Augment with project-specific patterns surfaced in `CLAUDE.md`. Crustopher's CLAUDE.md lists canonical auth reason codes — add them so denial-path journeys produce captured evidence:
```
Replace with:
```
Augment with project-specific patterns surfaced in the app's `CLAUDE.md` or in the journey `failure_risk` fields (e.g. auth reason codes for denial-path journeys). Example — a project whose CLAUDE.md lists canonical auth reason codes:
```

(The Crustopher worked examples elsewhere stay as labeled illustrations.)

- [ ] **Step 6: Verify the adaptations are present**

Run:
```bash
grep -c "name: app-validation-loop" skills/app-validation-loop/SKILL.md
grep -c "Consume structured journeys" skills/app-validation-loop/SKILL.md
grep -c "user-journeys.yaml" skills/app-validation-loop/SKILL.md
grep -c "journey-test-results-phase-4.md" skills/app-validation-loop/SKILL.md
```
Expected: each prints `1` or higher (no `0`).

- [ ] **Step 7: Verify the driver script copied intact (syntax check)**

Run:
```bash
python3 -m py_compile skills/app-validation-loop/scripts/drive_journeys.py && echo "OK"
```
Expected: `OK` (no syntax errors).

- [ ] **Step 8: Commit**

```bash
git add skills/app-validation-loop
git commit -m "feat: vendor test-deployed-app into plugin as app-validation-loop

Adds a structured-journey input path that reads
.agent-team/artifacts/user-journeys.yaml and writes Phase 4 findings.

Co-authored-by: Isaac"
```

---

## Task 2: Define the structured journey contract

**Files:**
- Create: `lib/journey-schema.yaml`

- [ ] **Step 1: Write the schema file**

Create `lib/journey-schema.yaml` with this exact content:
```yaml
# Structured user-journey contract.
# team-builder and feature-scoper write .agent-team/artifacts/user-journeys.yaml
# in this shape. The app-validation-loop skill (invoked by the QA engineer in
# Phase 4) reads it and drives each journey against the deployed app.
#
# Generated ONLY when the team/feature has a web-app or databricks-app capability.

version: 1

# Top-level key is `journeys`: an ordered list. Drive in listed order.
journeys:
  - id: J1                       # short id, unique per file; used for filenames + log correlation
    name: <human-readable name>
    persona: <who is performing this journey>
    goal: <what the user is trying to accomplish>
    preconditions:              # state/data that must exist before the journey runs
      - <e.g. "demo dataset loaded", "user authorized for store 42">
    steps:                      # ordered UI interactions
      - action: <navigate | click | type | confirm | select | wait>
        prompt: <verbatim text to send, when action is type/chat; omit otherwise>
        expected: <what should happen / which backend tool or path should fire>
    success_criteria: <FALSIFIABLE — a human or grep can check it (e.g. "final message contains a numeric score", "Confirm card appears before tool runs")>
    failure_risk: <what this journey specifically guards against; also seeds the log filter>
    maps_to: <PRD success criterion (team-builder) OR feature_description (feature-scoper)>

# Notes for generators:
# - Prefer 3-5 journeys covering: happy path, multi-step/multi-tool, high-risk
#   confirmation flow (if any), known-bad input/data, and negative-auth (if any).
# - Every journey MUST set `maps_to` so coverage is auditable.
# - feature-scoper APPENDS to an existing file; it must not drop product journeys.
```

- [ ] **Step 2: Verify it is valid YAML**

Run:
```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('lib/journey-schema.yaml')); assert d['version']==1 and isinstance(d['journeys'],list); print('OK')"
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add lib/journey-schema.yaml
git commit -m "feat: add structured user-journey schema contract

Co-authored-by: Isaac"
```

---

## Task 3: team-builder derives product journeys from the PRD

**Files:**
- Modify: `skills/team-builder/SKILL.md` (insert a new step between Step 1 and Step 2; Step 2 currently starts at line 47)

- [ ] **Step 1: Insert the journey-generation step**

In `skills/team-builder/SKILL.md`, immediately **before** the line `## Step 2: Map to Capability Tags`, insert this section:

````markdown
## Step 1.7: Derive User Journeys (app teams only)

If — and only if — the team will include a `web-app` or `databricks-app`
capability (decided in Step 2/Step 3), derive user journeys that exercise the
PRD's goal and write them to `.agent-team/artifacts/user-journeys.yaml`.

(If no app capability is present, skip this step — there is no app to drive.)

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
````

- [ ] **Step 2: Verify the step is present and references the schema + artifact**

Run:
```bash
grep -c "Step 1.7: Derive User Journeys" skills/team-builder/SKILL.md
grep -c "user-journeys.yaml" skills/team-builder/SKILL.md
grep -c "lib/journey-schema.yaml" skills/team-builder/SKILL.md
```
Expected: each ≥ `1`.

- [ ] **Step 3: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat: team-builder derives PRD user journeys for app teams

Co-authored-by: Isaac"
```

---

## Task 4: feature-scoper derives feature-scoped journeys

**Files:**
- Modify: `skills/feature-scoper/SKILL.md` (add a sub-step inside Step 4; Step 4 starts at line 106)

- [ ] **Step 1: Insert the feature-journey sub-step**

In `skills/feature-scoper/SKILL.md`, inside `## Step 4: Generate Scoped .agent-team/ Config`, **after** the `**6. Reset status:**` block and before `## Step 5: Tag and Hand Off`, insert:

````markdown
**7. Generate feature-scoped user journeys (app-touching features only):**

If the feature touches app behavior — any of the capability tags `web-app`,
`frontend`, `databricks-app`, or an `api-backend` change that alters
user-visible behavior — derive journeys for **this feature's** success criteria
and **append** them to `.agent-team/artifacts/user-journeys.yaml`:

- Follow `lib/journey-schema.yaml` exactly.
- Set `maps_to: "<feature_description>"` on every journey so feature journeys are
  attributable and product-level journeys remain intact.
- If `user-journeys.yaml` already exists (from `team-builder` or a prior feature),
  **read it first and append** — never overwrite existing journeys. Give new
  journeys ids that do not collide (e.g. continue the `J<n>` numbering).
- Generate 1–3 journeys focused narrowly on the new/changed behavior, including a
  negative path if the feature adds a gate or validation.

If the feature touches no app behavior, skip this sub-step.
````

- [ ] **Step 2: Verify**

Run:
```bash
grep -c "feature-scoped user journeys" skills/feature-scoper/SKILL.md
grep -c "maps_to" skills/feature-scoper/SKILL.md
grep -c "never overwrite existing journeys" skills/feature-scoper/SKILL.md
```
Expected: each ≥ `1`.

- [ ] **Step 3: Commit**

```bash
git add skills/feature-scoper/SKILL.md
git commit -m "feat: feature-scoper appends feature-scoped user journeys

Co-authored-by: Isaac"
```

---

## Task 5: deploy-engineer emits the app URL

**Files:**
- Modify: `agents/deploy-engineer.md` (Output Requirements ~line 185; Status Protocol ~line 204)

- [ ] **Step 1: Add app_url/app_resource_name to the status YAML**

In `agents/deploy-engineer.md`, in the Status Protocol code block, add two fields.
Find:
```yaml
deploy_target: dev
concerns: []
blockers: []
setup_job_tasks: [list of task_keys generated]
```
Replace with:
```yaml
deploy_target: dev
app_url: <deployed Databricks App URL, or null if the team has no app>
app_resource_name: <bundle resource name of the app, or null>
concerns: []
blockers: []
setup_job_tasks: [list of task_keys generated]
```

- [ ] **Step 2: Add an instruction to capture the URL after deploy**

In `agents/deploy-engineer.md`, in the `## Step 4: Validate and Deploy` section,
after the `databricks bundle deploy --target dev` line/block, add:

````markdown
After a successful deploy, if the bundle includes an app resource, capture its URL
so downstream journey validation can drive it:
```bash
# Resolve the deployed app URL (app_resource_name is the resource key in resources/apps*.yml)
databricks bundle summary --target dev -o json | \
  python3 -c "import json,sys; d=json.load(sys.stdin); apps=d.get('resources',{}).get('apps',{}); [print(k, (v.get('url') or '')) for k,v in apps.items()]"
```
Record the resulting URL as `app_url` and the resource key as `app_resource_name`
in your status file. If there is no app resource, set both to `null`.
````

- [ ] **Step 3: Verify**

Run:
```bash
grep -c "app_url" agents/deploy-engineer.md
grep -c "app_resource_name" agents/deploy-engineer.md
```
Expected: each ≥ `2` (status block + Step 4 instruction).

- [ ] **Step 4: Commit**

```bash
git add agents/deploy-engineer.md
git commit -m "feat: deploy-engineer emits app_url for journey validation

Co-authored-by: Isaac"
```

---

## Task 6: QA agent runs the Phase 4 journey loop

**Files:**
- Modify: `agents/qa-engineer.md` (Phase 4 block ~lines 38-41; Skills to Use ~lines 43-45)
- Modify: `templates/core/qa-engineer.yaml` (skills list ~lines 14-16)

- [ ] **Step 1: Expand the Phase 4 checklist with a Journey Validation block**

In `agents/qa-engineer.md`, find the Deployed Validation block:
```markdown
### Deployed Validation (Phase 4)
- [ ] Pipeline executes successfully
- [ ] Serving endpoints respond correctly
- [ ] App loads and basic smoke test passes
```
Replace it with:
```markdown
### Deployed Validation (Phase 4)
- [ ] Pipeline executes successfully
- [ ] Serving endpoints respond correctly
- [ ] App loads and basic smoke test passes

### Journey Validation (Phase 4 — app teams only)
Run only when the PM provides an `app_url` (i.e. the team deployed an app) and
`.agent-team/artifacts/user-journeys.yaml` exists.

- [ ] Invoke the `app-validation-loop` skill
- [ ] Read `.agent-team/artifacts/user-journeys.yaml` (per `lib/journey-schema.yaml`)
      and the `app_url` / `app_resource_name` from the dispatch context
- [ ] Drive each journey in order, capturing dual-channel evidence (UI screenshot
      + final text, and backend `databricks apps logs <app_resource_name>`)
- [ ] For each journey, assign a verdict: PASS | PARTIAL | FAIL, with severity
      (demo-blocker | intermittent | cosmetic), verbatim prompt/action,
      reproduction, evidence, and the `maps_to` criterion it validates
- [ ] Write the per-journey results to
      `.agent-team/status/journey-test-results-phase-4.md`
- [ ] Surface any FAIL/PARTIAL into the QA status `checks` so the PM can act

Do NOT modify source code to fix a failing journey — report it. The PM
orchestrator dispatches the appropriate fix agent and re-runs the suite. You may
re-run a journey within this pass to rule out transient/cold-start flakiness.
```

- [ ] **Step 2: Add the skill to "Skills to Use"**

In `agents/qa-engineer.md`, find:
```markdown
## Skills to Use
- Invoke the `databricks-query` skill to validate SQL and table schemas
- Invoke the `asset-bundles` skill to validate DAB configuration
```
Replace with:
```markdown
## Skills to Use
- Invoke the `databricks-query` skill to validate SQL and table schemas
- Invoke the `asset-bundles` skill to validate DAB configuration
- Invoke the `app-validation-loop` skill in Phase 4 to drive the deployed app
  through the PRD user journeys (only when an `app_url` is provided)
```

- [ ] **Step 3: Allow QA to write the journey results file**

In `agents/qa-engineer.md`, find the Constraints block:
```markdown
## Constraints
- Do not modify source code — only read and validate
- Write test files to `tests/` only
- Write status to `.agent-team/status/` only
```
Replace with:
```markdown
## Constraints
- Do not modify source code — only read and validate
- Write test files to `tests/` only
- Write status and journey results to `.agent-team/status/` only
  (including `journey-test-results-phase-4.md`)
```

- [ ] **Step 4: Add the skill to the QA template**

In `templates/core/qa-engineer.yaml`, find:
```yaml
skills:
  - databricks-query
  - asset-bundles
```
Replace with:
```yaml
skills:
  - databricks-query
  - asset-bundles
  - app-validation-loop
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -c "Journey Validation (Phase 4" agents/qa-engineer.md
grep -c "app-validation-loop" agents/qa-engineer.md
grep -c "journey-test-results-phase-4.md" agents/qa-engineer.md
grep -c "app-validation-loop" templates/core/qa-engineer.yaml
python3 -c "import yaml; print('OK' if 'app-validation-loop' in yaml.safe_load(open('templates/core/qa-engineer.yaml'))['skills'] else 'MISSING')"
```
Expected: the greps each ≥ `1`; the python prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add agents/qa-engineer.md templates/core/qa-engineer.yaml
git commit -m "feat: QA engineer drives Phase 4 user-journey validation loop

Co-authored-by: Isaac"
```

---

## Task 7: PM orchestrator wires journeys into the Phase 4 QA gate

**Files:**
- Modify: `agents/pm-orchestrator.md` (`resolve_contracts` Step 2 ~lines 99-116; `qa_gate` Step 7 ~lines 181-190)

- [ ] **Step 1: Inject journeys + app_url into the Phase 4 QA dispatch**

In `agents/pm-orchestrator.md`, in `### Step 2: resolve_contracts`, find the
bullet:
```markdown
  - **QA scope** — for QA agent only, the progressive QA checklist for this phase
```
Replace with:
```markdown
  - **QA scope** — for QA agent only, the progressive QA checklist for this phase
  - **User journeys (Phase 4 QA only)** — if `.agent-team/artifacts/user-journeys.yaml`
    exists, include its full contents in the QA agent's prompt, plus the deployed
    `app_url` and `app_resource_name` read from `.agent-team/status/deploy-engineer.yaml`.
    This mirrors the data-profile injection pattern. If `app_url` is null/absent,
    tell the QA agent to skip Journey Validation (no app to drive).
```

- [ ] **Step 2: Route journey failures through the qa_gate fix loop**

In `agents/pm-orchestrator.md`, in `### Step 7: qa_gate`, find:
```markdown
- If **FAIL:**
  - Dispatch a fix agent for the specific issues (use the original agent's model)
  - Re-run QA
  - After 3 failed attempts: escalate to human
```
Replace with:
```markdown
- If **FAIL:**
  - Dispatch a fix agent for the specific issues (use the original agent's model)
  - Re-run QA
  - After 3 failed attempts: escalate to human
- **Journey failures (Phase 4):** treat any `FAIL`/`PARTIAL` journey in
  `.agent-team/status/journey-test-results-phase-4.md` as a gate failure. Route
  the fix to the agent that owns the failing surface:
  - UI / frontend / app behavior → `app-developer`
  - serving-endpoint / model output → `data-scientist` or `genai-architect`
  - data/pipeline-sourced wrong values → `data-engineer`
  Dispatch the owning agent scoped to the specific failing journeys (include the
  reproduction and backend evidence from the results file), then re-run the
  **journey suite only**. Same 3-attempt cap, then escalate.
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -c "User journeys (Phase 4 QA only)" agents/pm-orchestrator.md
grep -c "journey-test-results-phase-4.md" agents/pm-orchestrator.md
grep -c "agent that owns the failing surface" agents/pm-orchestrator.md
```
Expected: each ≥ `1`.

- [ ] **Step 4: Commit**

```bash
git add agents/pm-orchestrator.md
git commit -m "feat: PM injects user journeys and routes journey FAILs to fix loop

Co-authored-by: Isaac"
```

---

## Task 8: Integration verification

**Files:** none (read-only checks across the changes)

- [ ] **Step 1: Confirm the vendored skill is discoverable as a plugin skill**

Run:
```bash
# plugin.json points skills at ./skills/, so the new dir is auto-discovered
python3 -c "import yaml; d=yaml.safe_load(open('skills/app-validation-loop/SKILL.md').read().split('---')[1]); print(d['name'])"
test -f .claude-plugin/plugin.json && grep -q '"skills": "./skills/"' .claude-plugin/plugin.json && echo "auto-discovery OK"
```
Expected: prints `app-validation-loop` then `auto-discovery OK`.

- [ ] **Step 2: End-to-end grep sweep — the chain references line up**

Run:
```bash
echo "producers write the artifact:"; grep -l "user-journeys.yaml" skills/team-builder/SKILL.md skills/feature-scoper/SKILL.md
echo "consumer reads it:"; grep -l "user-journeys.yaml" agents/qa-engineer.md skills/app-validation-loop/SKILL.md
echo "PM wires it:"; grep -l "user-journeys.yaml" agents/pm-orchestrator.md
echo "deploy emits url:"; grep -l "app_url" agents/deploy-engineer.md agents/pm-orchestrator.md agents/qa-engineer.md
```
Expected: every `grep -l` lists all the files named on its line (no missing file).

- [ ] **Step 3: Confirm all YAML edited/created in this plan still parses**

Run:
```bash
for f in lib/journey-schema.yaml templates/core/qa-engineer.yaml; do
  python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f OK')"
done
```
Expected: both print `OK`.

- [ ] **Step 4: Final review commit (only if Steps 1-3 surfaced fixes)**

If any verification surfaced a gap and you corrected it, commit the fix:
```bash
git add -A && git commit -m "fix: address journey-loop integration verification gaps

Co-authored-by: Isaac"
```
If nothing needed fixing, skip this step.

---

## Self-Review (completed by plan author)

**Spec coverage:** All 7 spec touch points map to tasks — vendored skill (T1),
journey-schema (T2), team-builder (T3), feature-scoper (T4), deploy-engineer
app_url (T5), QA agent + template (T6), PM orchestrator (T7), plus integration
verification (T8). The spec's "fix-agent routing generalization" note is
implemented in T7 Step 2 (owning-surface routing). No manifest change is needed
(plugin.json auto-discovers skills — confirmed in T8 Step 1).

**Placeholder scan:** Angle-bracket tokens in `lib/journey-schema.yaml` and the
deploy status YAML are intentional schema placeholders that ship in the artifact,
not plan placeholders — every edit step shows the literal text to write.

**Type/name consistency:** Names are consistent across tasks — skill
`app-validation-loop`; artifact `.agent-team/artifacts/user-journeys.yaml`;
results file `.agent-team/status/journey-test-results-phase-4.md`; status fields
`app_url` / `app_resource_name`; schema fields `maps_to`, `success_criteria`,
`failure_risk`.
