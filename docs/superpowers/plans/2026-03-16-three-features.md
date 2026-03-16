# Three Features Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add data catalog analysis, incremental feature work, and UI/UX workflow analysis to the agent-team plugin.

**Architecture:** Three independent feature additions to an existing Claude Code plugin. Each feature adds new files (skills, commands, agents, templates) and modifies existing ones. All files are markdown or YAML — this is prompt engineering and configuration, not traditional code.

**Tech Stack:** Claude Code plugin system (markdown commands, skills, agent definitions, YAML templates)

**Spec:** `docs/superpowers/specs/2026-03-16-three-features-design.md`

---

## Chunk 1: Feature 1 — Data Catalog Analyzer

### Task 1: Create `skills/data-analyzer/SKILL.md`

**Files:**
- Create: `skills/data-analyzer/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p skills/data-analyzer
```

- [ ] **Step 2: Write the data-analyzer skill**

Create `skills/data-analyzer/SKILL.md` with:

```markdown
---
name: data-analyzer
description: Profiles existing Unity Catalog tables — schema metadata, column stats, sample rows, and inferred relationships. Invoked by /create-team when --catalog/--schema flags are provided or PRD references existing tables.
---
```

The skill body must include:

1. **Input section** — accepts `catalog`, `schema`, optional `max_tables` (default 50)
2. **Step 1: List tables** — use `mcp__databricks-mcp__execute_sql` with `SHOW TABLES IN {catalog}.{schema}`
3. **Step 2: Profile each table** (up to max_tables):
   - Get table details via `mcp__databricks-mcp__get_table_details`
   - Run profiling SQL per column:
     ```sql
     SELECT
       COUNT(*) as row_count,
       COUNT(DISTINCT {col}) as distinct_count,
       SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) / COUNT(*) as null_rate,
       MIN({col}) as min_val,
       MAX({col}) as max_val
     FROM {catalog}.{schema}.{table}
     ```
   - Cap at 30 seconds per table
   - For tables >1M rows, use `TABLESAMPLE (1000 ROWS)` for sample rows
   - Get 5 sample rows: `SELECT * FROM {table} LIMIT 5`
4. **Step 3: Infer relationships** — scan column names for `_id` suffixes matching other table names, check for common columns across tables
5. **Step 4: Write output** — write `.agent-team/artifacts/data-profile.yaml` following the schema from the spec (include `status` field per table: profiled/partial/error/skipped)
6. **Failure modes section** — MCP unavailable (skip with warning), tables not found (mark error), permission denied (mark error), slow queries (mark partial), too many tables (cap at max_tables with warning)

- [ ] **Step 3: Validate the skill file**

```bash
# Check file exists and has frontmatter
head -5 skills/data-analyzer/SKILL.md
# Check it's referenced correctly in plugin structure
ls skills/data-analyzer/
```

- [ ] **Step 4: Commit**

```bash
git add skills/data-analyzer/SKILL.md
git commit -m "feat(F1): add data-analyzer skill for UC table profiling"
```

---

### Task 2: Modify `commands/create-team.md` to support data analysis

**Files:**
- Modify: `commands/create-team.md`

- [ ] **Step 1: Add flags to the Input section**

After the existing `{{ARGUMENTS}}` line, add parsing for optional flags:
- `--catalog <name>` — Unity Catalog catalog to profile
- `--schema <name>` — UC schema to profile
- `--max-tables N` — max tables to profile (default 50)

- [ ] **Step 2: Add Step 1.5 between "Read the PRD" and "Invoke team-builder"**

Add a new step: **Step 1.5: Analyze existing data (if applicable)**

This step triggers when:
- `--catalog` and `--schema` flags are provided, OR
- PRD text contains patterns like `catalog.schema.table` references

When triggered:
1. Invoke the `data-analyzer` skill with catalog, schema, max_tables
2. The skill writes `.agent-team/artifacts/data-profile.yaml`
3. Pass the data profile path to team-builder in the next step

When NOT triggered, skip silently.

- [ ] **Step 3: Update Step 2 to pass data profile to team-builder**

Add a note that if `data-profile.yaml` was produced, team-builder should incorporate it into agent context and contracts.

- [ ] **Step 4: Validate the command**

```bash
# Check the command file parses correctly
grep -c "data-analyzer" commands/create-team.md
grep -c "catalog" commands/create-team.md
```

- [ ] **Step 5: Commit**

```bash
git add commands/create-team.md
git commit -m "feat(F1): add --catalog/--schema flags to /create-team"
```

---

### Task 3: Modify `skills/team-builder/SKILL.md` to consume data profiles

**Files:**
- Modify: `skills/team-builder/SKILL.md`

- [ ] **Step 1: Add data profile awareness to Step 1 (Parse the PRD)**

After the existing extraction list, add:
- If `.agent-team/artifacts/data-profile.yaml` exists, read it and extract: table names, column schemas, relationships, sample data

- [ ] **Step 2: Update Step 6 (Define Contracts) to use real schemas**

Add instruction: when data-profile.yaml is available, use actual column names, types, and relationships from the profile instead of inferring from PRD text. Mark all profiled columns as `required: true` since they're confirmed to exist.

- [ ] **Step 3: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat(F1): team-builder consumes data-profile.yaml for real schemas"
```

---

### Task 4: Modify `agents/pm-orchestrator.md` to pass data profile context

**Files:**
- Modify: `agents/pm-orchestrator.md`

- [ ] **Step 1: Update Step 2 (resolve_contracts) context list**

Add to the dynamic context list:
- **Data profile** — contents of `.agent-team/artifacts/data-profile.yaml` (if exists). Provides real table schemas, column stats, sample rows, and relationships for the target catalog/schema.

- [ ] **Step 2: Commit**

```bash
git add agents/pm-orchestrator.md
git commit -m "feat(F1): PM passes data profile context to agents"
```

---

## Chunk 2: Feature 2 — Incremental Feature Work

### Task 5: Create `skills/feature-scoper/SKILL.md`

**Files:**
- Create: `skills/feature-scoper/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p skills/feature-scoper
```

- [ ] **Step 2: Write the feature-scoper skill**

Create `skills/feature-scoper/SKILL.md` with frontmatter:

```markdown
---
name: feature-scoper
description: Analyzes an existing project and scopes incremental feature work. Discovers current codebase state, maps feature to capability tags, selects minimum agents, and generates a scoped .agent-team/ config. Invoked by /add-feature.
---
```

The skill body must include 5 steps matching the spec:

**Step 1: Discover Current State**
- Scan `src/`, `resources/`, `tests/`, `databricks.yml` using Glob and Read tools
- Read `.agent-team/team-manifest.yaml` if it exists (copy to `.agent-team/team-manifest.previous.yaml`)
- Read `CLAUDE.md` introspection section if it exists
- Read `.agent-team/contracts/*.yaml` if they exist
- If no `.agent-team/` exists, set `history: null` and build snapshot from code only
- Produce `project_snapshot` YAML structure (spec lines 121-139)

**Step 2: Analyze Feature Request**
- Parse the feature description (received as input)
- Map to capability tags (reference the same tag table from team-builder)
- Diff: which capabilities are new vs extensions of existing code

**Step 3: Smart Agent Scoping**
- Include the agent scoping table from spec (lines 152-160)
- Always include qa-engineer
- No domain SME (domain established)
- Include deploy-engineer only if resource/DAB changes expected

**Step 4: Generate Scoped .agent-team/ Config**
- Write `team-manifest.yaml` with `mode: incremental`, `feature_description`, `previous_manifest`
- Write only needed agent definitions
- Write collapsed phases (skip unused phases)
- Write contracts that reference existing artifacts as read-only inputs
- Reset `status/progress.yaml` for new phases
- Embed `project_snapshot` in manifest

**Step 5: Tag and hand off**
- Tag current commit: `git tag feature-start/<slug>`
- Output message: "Scoped team written to .agent-team/. Invoking /start-team..."

- [ ] **Step 3: Validate**

```bash
head -5 skills/feature-scoper/SKILL.md
grep -c "incremental" skills/feature-scoper/SKILL.md
```

- [ ] **Step 4: Commit**

```bash
git add skills/feature-scoper/SKILL.md
git commit -m "feat(F2): add feature-scoper skill for incremental work analysis"
```

---

### Task 6: Create `commands/add-feature.md`

**Files:**
- Create: `commands/add-feature.md`

- [ ] **Step 1: Write the command**

Create `commands/add-feature.md` with frontmatter:

```markdown
---
description: "Add a feature or improvement to an existing project — scopes work to only the agents needed"
---
```

The command body must include:

**Input section:**
- `{{ARGUMENTS}}` — either a file path or inline text
- Detection logic: check if argument resolves to an existing file. If yes, read it. If no, treat as inline text.

**Execution:**
1. Validate project exists (at minimum: `src/` or `databricks.yml` must exist)
2. Invoke `feature-scoper` skill with the feature description
3. Feature-scoper writes scoped `.agent-team/` config
4. Invoke `/start-team` to execute (which detects `mode: incremental`)

**Rollback section:**
Document the git-based rollback:
```
git log --oneline | grep "feature-start/"
git revert --no-commit <first>..HEAD
git commit -m "rollback: revert feature"
```

- [ ] **Step 2: Validate**

```bash
head -5 commands/add-feature.md
grep -c "feature-scoper" commands/add-feature.md
```

- [ ] **Step 3: Commit**

```bash
git add commands/add-feature.md
git commit -m "feat(F2): add /add-feature command for incremental work"
```

---

### Task 7: Modify `commands/start-team.md` for incremental mode

**Files:**
- Modify: `commands/start-team.md`

- [ ] **Step 1: Add incremental mode handling**

After the "Initialize or Read Progress" section (Step 4), add:

**Step 4.5: Detect incremental mode**

Read `.agent-team/team-manifest.yaml`. If `mode: incremental`:
- Skip Step 2 (Initialize Git) — project already has a repo
- Skip Step 3 (Scaffold DAB Project) — project already has structure
- Display: "Incremental mode: adding feature '<feature_description>'"
- Proceed directly to PM orchestrator dispatch

- [ ] **Step 2: Commit**

```bash
git add commands/start-team.md
git commit -m "feat(F2): start-team handles mode: incremental from /add-feature"
```

---

### Task 8: Modify `agents/pm-orchestrator.md` for incremental mode

**Files:**
- Modify: `agents/pm-orchestrator.md`

- [ ] **Step 1: Add incremental mode section**

After the "Inputs" section, add:

**Incremental Mode**

When `team-manifest.yaml` has `mode: incremental`:
- Read `project_snapshot` from the manifest
- Pass it as context to ALL agents alongside their normal contract context
- Frame agent prompts with: "You are modifying an existing project. Here is the current state: [snapshot]. Your task is to add: [feature_description]"
- Introspection captures feature-specific learnings (tag with feature name)

- [ ] **Step 2: Commit**

```bash
git add agents/pm-orchestrator.md
git commit -m "feat(F2): PM orchestrator handles incremental mode with project snapshot"
```

---

### Task 9: Update `skills/team-builder/SKILL.md` for project snapshot input

**Files:**
- Modify: `skills/team-builder/SKILL.md`

- [ ] **Step 1: Add optional project_snapshot input**

At the top of the skill, after the frontmatter, add:

**Optional Inputs:**
- `project_snapshot` — when provided (by feature-scoper), use it to:
  - Inform contract definitions with real table/endpoint names from existing code
  - Skip capability tags that are already fully implemented
  - Reference existing artifacts as read-only contract inputs

- [ ] **Step 2: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat(F2): team-builder accepts project_snapshot for incremental contracts"
```

---

## Chunk 3: Feature 3 — UI/UX Workflow Analyst

### Task 10: Create `templates/core/ui-ux-analyst.yaml`

**Files:**
- Create: `templates/core/ui-ux-analyst.yaml`

- [ ] **Step 1: Write the template**

Create `templates/core/ui-ux-analyst.yaml` with the exact content from the spec:

```yaml
name: ui-ux-analyst
display_name: UI/UX Analyst
description: Designs app UX workflows, wireframes, and component specs
model: sonnet
registered_agent: agents/ui-ux-analyst.md
typical_phases: [1]

capabilities:
  - ui-design
  - ux-workflow
  - wireframing
  - frontend-planning

skills:
  - ui-ux-pro-max

mcp_tools: []

output_paths:
  - .agent-team/artifacts/ui-workflow.md
  - .agent-team/artifacts/ui-wireframes/
  - .agent-team/artifacts/ui-component-contract.yaml
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/ui-ux-analyst.yaml
git commit -m "feat(F3): add ui-ux-analyst template with capability tags"
```

---

### Task 11: Create `agents/ui-ux-analyst.md`

**Files:**
- Create: `agents/ui-ux-analyst.md`

- [ ] **Step 1: Write the agent definition**

Create `agents/ui-ux-analyst.md` with YAML frontmatter:

```yaml
---
name: ui-ux-analyst
description: >
  Designs application user experience — workflows, wireframes, and component
  specifications — informed by domain research. Produces HTML mockups and
  structured component contracts for the app-developer. Dispatched by PM orchestrator.
model: sonnet
tools: Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, WebSearch, WebFetch
---
```

The agent body must include:

**Role section** — Senior UX Designer on the agent team

**Skills to Use** — Invoke `ui-ux-pro-max` skill for:
- Style selection (50 styles catalog)
- Color palette (21 palettes)
- Typography (50 font pairings)
- Wireframe/mockup generation

**Inputs section:**
- Domain playbook (required, from Phase 0 SME)
- PRD features (passed via PM context)
- Data profile (optional, from data-analyzer)
- Existing wireframes (optional, for incremental mode)

**Process:**
1. Read domain playbook for user-facing workflows
2. Define user personas and journeys
3. Create screen inventory
4. Design navigation flow
5. Invoke ui-ux-pro-max for visual design decisions and HTML wireframes
6. Produce structured component contract

**Output Requirements** — exact paths:
- `.agent-team/artifacts/ui-workflow.md` — user journeys, screen inventory, navigation, visual decisions
- `.agent-team/artifacts/ui-wireframes/` — HTML files per screen
- `.agent-team/artifacts/ui-component-contract.yaml` — pages, components, API endpoints, data shapes

**Incremental Mode Behavior:**
When existing wireframes are provided as input:
- Read existing artifacts as context
- Produce additive outputs (new wireframes added, existing untouched)
- Add `status: new | modified | unchanged` to each page in component contract

**Constraints:**
- Write only to `.agent-team/artifacts/ui-*`
- Do not write application code
- Focus on design and specification

**Status Protocol** — same as other agents:
```yaml
status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
artifacts: [list]
concerns: [if any]
blockers: [if any]
```

- [ ] **Step 2: Validate**

```bash
head -10 agents/ui-ux-analyst.md
grep -c "ui-ux-pro-max" agents/ui-ux-analyst.md
```

- [ ] **Step 3: Commit**

```bash
git add agents/ui-ux-analyst.md
git commit -m "feat(F3): add ui-ux-analyst agent definition"
```

---

### Task 12: Update `skills/team-builder/SKILL.md` with UI capability tags

**Files:**
- Modify: `skills/team-builder/SKILL.md`

- [ ] **Step 1: Add 4 new capability tags to the table in Step 2**

Add these rows to the capability tag table:

| ui-design | UI mockups, wireframes, visual design |
| ux-workflow | User journeys, personas, interaction patterns |
| wireframing | Screen layouts, component placement |
| frontend-planning | Component architecture, page structure |

- [ ] **Step 2: Update Step 3 (Select Curated Agents)**

Add logic: when `ui-design`, `ux-workflow`, `wireframing`, or `frontend-planning` tags are matched, select the `ui-ux-analyst` template. Only select when a domain SME is also present (UI design needs domain context).

- [ ] **Step 3: Update Step 6 (Define Contracts)**

Add the `ui-to-app` contract definition pattern: when ui-ux-analyst and app-developer are both selected, generate a contract with:
- Producer: ui-ux-analyst
- Consumer: app-developer
- Artifacts: ui-workflow.md, ui-wireframes/, ui-component-contract.yaml
- Optional inputs: data-profile.yaml

- [ ] **Step 4: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat(F3): team-builder selects ui-ux-analyst and wires ui-to-app contract"
```

---

### Task 13: Update `agents/app-developer.md` with UI artifact inputs

**Files:**
- Modify: `agents/app-developer.md`

- [ ] **Step 1: Add optional UI inputs section**

After the "Skills to Use" section, add:

**Optional UI/UX Inputs (when ui-ux-analyst is on the team):**
- `.agent-team/artifacts/ui-workflow.md` — user journeys, screen inventory, navigation flow
- `.agent-team/artifacts/ui-wireframes/` — HTML mockup files (open in browser for reference)
- `.agent-team/artifacts/ui-component-contract.yaml` — structured page/component/API spec

When these are present:
- Code against the component contract for page structure and API shapes
- Reference wireframes for visual layout and styling
- Follow the navigation flow for routing
- In incremental mode, only implement pages with `status: new` or `status: modified`

- [ ] **Step 2: Commit**

```bash
git add agents/app-developer.md
git commit -m "feat(F3): app-developer consumes UI/UX wireframes and component contract"
```

---

## Chunk 4: Integration Validation

### Task 14: Update test PRD and validate end-to-end

**Files:**
- Modify: `test/qa-chatbot-prd.md` (optional — add a note about UI expectations)
- Create: `test/add-feature-test.md` (test scenario for Feature 2)

- [ ] **Step 1: Create a test feature description for Feature 2**

Write `test/add-feature-test.md`:

```markdown
# Add Feedback Feature

Add a thumbs up/down feedback button to each assistant response in the chat UI.
Store feedback in a Delta table with columns: feedback_id, message_id, rating (up/down), timestamp.
Display aggregate feedback stats on a simple admin page.
```

- [ ] **Step 2: Validate all new files exist**

```bash
echo "=== New Files ==="
ls skills/data-analyzer/SKILL.md
ls skills/feature-scoper/SKILL.md
ls commands/add-feature.md
ls agents/ui-ux-analyst.md
ls templates/core/ui-ux-analyst.yaml

echo "=== Modified Files ==="
grep "data-analyzer\|catalog\|schema" commands/create-team.md | head -3
grep "data-profile\|project_snapshot" skills/team-builder/SKILL.md | head -3
grep "incremental\|data.profile" agents/pm-orchestrator.md | head -3
grep "ui-workflow\|wireframe\|component-contract" agents/app-developer.md | head -3
grep "incremental" commands/start-team.md | head -3
```

Expected: all files exist, all grep patterns match.

- [ ] **Step 3: Commit test files**

```bash
git add test/add-feature-test.md
git commit -m "test: add test scenarios for new features"
```

- [ ] **Step 4: Final commit — update handoff.md**

Update `handoff.md` to reference the 3 new features, new commands, and test scenarios. Commit.

```bash
git add handoff.md
git commit -m "docs: update handoff with three new features"
```

---

## Implementation Notes

### Sequential file modifications

Three files are modified across multiple chunks:
- `skills/team-builder/SKILL.md` — modified in Tasks 3, 9, and 12 (F1, F2, F3)
- `agents/pm-orchestrator.md` — modified in Tasks 4 and 8 (F1, F2)

These MUST be done sequentially. Do not parallelize tasks that touch the same file.

### Prerequisite: `ui-ux-pro-max` skill

Feature 3's `ui-ux-analyst` agent invokes the `ui-ux-pro-max` skill, which is an external skill from the superpowers plugin marketplace. Verify it is available before implementing Task 11. If not installed, the agent will fail at runtime. This is NOT built as part of this plan.

### Phase-planner validation

The spec states phase-planner needs no changes because the dependency graph handles ui-ux-analyst placement automatically. After Task 12 (adding UI capability tags to team-builder), read `skills/phase-planner/SKILL.md` and verify its algorithm will correctly:
- Place ui-ux-analyst (depends on domain-playbook, no data dependencies) in the same phase as data-engineer
- NOT place it in Phase 0 (it's not a domain SME)
If the phase-planner's logic doesn't handle this, add a note to its algorithm about agents that consume only Phase 0 outputs.

### Artifact path isolation

When implementing Task 11 (ui-ux-analyst agent), the constraints section MUST restrict writes to `.agent-team/artifacts/ui-*` only. This prevents merge conflicts with data-engineer which writes to `src/` and `resources/`. The PM orchestrator should validate non-overlapping paths before merge — add this check when modifying pm-orchestrator.md in Task 8.

### Contract phase affinity

When implementing Task 12 Step 3 (ui-to-app contract wiring in team-builder), include a `consumed_in_phase` field or a note that this contract is resolved in Phase 2 (app-developer's first invocation), NOT Phase 3 (integration). This ensures the PM orchestrator passes wireframes to the app-developer when it first builds the UI shell.

### Rollback consistency

Task 6 (add-feature command) documents rollback via `feature-start/<slug>` git tags. The feature-scoper (Task 5, Step 5) creates these tags. Both must use the same convention. The PM orchestrator's checkpoint commits (`checkpoint: phase N completed`) are a secondary rollback mechanism for mid-feature recovery.
