# Generalize the Agent Team Beyond Databricks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Databricks-only harness into a single harness with pluggable **target profiles**, so `/create-team` + `/start-team` can build GenAI/ML-fine-tuning, Docker, and full-stack-web projects (plus a generic fallback) — while the Databricks profile reproduces today's strong team exactly, and the adversarial gate (from `2026-06-16-adversarial-review.md`) is inherited and made target-aware.

**Architecture:** Extract the one real coupling point — the Databricks-specific capability vocabulary, agent selection, scaffold/deploy verbs, and QA assertions — out of prose and into declarative `targets/<name>.yaml` profiles read by a new `lib/target-schema.yaml`. The platform-neutral *spine* (contracts, phases, worktree dispatch, checkpoint/recovery, journey schema, introspection) is untouched. To de-risk the hardest constraint (registered Claude Code agents have **static** tool grants in frontmatter), we use a **hybrid dispatch model**: the Databricks profile keeps the existing curated registered agents *exactly as-is* (`subagent_type` dispatch, static Databricks-MCP tools — zero regression); non-Databricks profiles assemble their teams from **dynamically generated specialists** (written to `.agent-team/agents/*.md`, dispatched via the PM's *already-existing* dynamic-agent path with generic tools). Per-target specificity is recovered by **technical SMEs** (a new meta-template) that write a `tech-playbook.md` in Phase 0.

**Tech Stack:** Markdown + YAML, the `Agent` tool (curated `subagent_type` *and* dynamic `model`+prompt dispatch — both already implemented in `agents/pm-orchestrator.md` Step 3), git worktree isolation, `python3 -c "import yaml"` parse validation, `grep` wiring assertions, `/create-team … --dry-run`-style dry-run inspection.

**Branch:** Branches off `main` **after** `2026-06-16-adversarial-review.md` has merged (so the adversarial gate is inherited). Branch name: `general-team`. This is the experimental branch — it is NOT merged to `main` until validated. The companion stable branch `databricks-team` is created from the same post-adversarial `main` and left untouched by this plan.

**Prerequisite:** `main` contains the adversarial gate (Plan 1 merged). Confirm with:
`grep -q "adversarial_gate" agents/pm-orchestrator.md` → exit 0 before starting.

**Verification substrate:** identical to Plan 1 — parse checks (`python3 -c "import yaml"`), wiring checks (`grep -q`), and explicit-observation dry-runs (`/create-team` then inspect `.agent-team/`). There is no automated assert for agent *behavior*; behavioral steps state the expected observation for a human/agent to confirm.

---

## File Structure

**New files:**
- `lib/target-schema.yaml` — the profile schema (documents every key a `targets/*.yaml` may set).
- `targets/databricks.yaml` — reproduces today's team exactly (default profile).
- `targets/web-fullstack.yaml` — full-stack web (React/Vite + FastAPI/Node) — the fully-worked non-DB example.
- `targets/docker.yaml` — containerized backend service.
- `targets/genai-finetuning.yaml` — LLM/ML fine-tuning + eval.
- `targets/generic.yaml` — minimal fallback for unrecognized stacks.
- `templates/meta/tech-sme-generator.yaml` — generates a *technical*-domain SME (mirrors `domain-sme-generator.yaml`, which stays for *industry* SMEs).

**Modified files:**
- `commands/create-team.md` — `--target <name>` flag, auto-detect from PRD, load active profile, Databricks-only steps gated behind the databricks target.
- `skills/team-builder/SKILL.md` — load the active profile; capability vocabulary, curated-agent set, generated-specialist set, scaffold/deploy/validation/QA all sourced from the profile; spin up technical SMEs in Phase 0; target-neutral framing.
- `commands/start-team.md` — profile-driven scaffold (Step 3) instead of hardwired DAB.
- `skills/app-validation-loop/SKILL.md` — select the journey driver from `profile.validation_driver` (browser / http / cli / eval).
- `agents/adversarial-reviewer.md` — consume `profile.security_focus` for target-specific attack surfaces.
- `templates/core/qa-engineer.yaml` *(new file — currently the QA agent has no core template entry beyond the registered agent; if absent, create it)* — QA assertions sourced from profile; **plus** edit `agents/qa-engineer.md` to make the E2E/deploy checklist profile-driven.
- `.claude-plugin/plugin.json` — bump to `0.3.0`.

**Reference (unchanged spine — do NOT modify):** `lib/contract-schema.yaml`, `lib/journey-schema.yaml`, the contracts/phases/checkpoint logic in `agents/pm-orchestrator.md` (except the small target-passthrough edit in Task 8).

---

## Task 1: Branch setup and prerequisite check

**Files:** none (git only)

- [ ] **Step 1: Confirm adversarial gate is on main**

Run: `git checkout main && grep -q "adversarial_gate" agents/pm-orchestrator.md && echo "prereq ok"`
Expected: `prereq ok`. If not, stop — execute `2026-06-16-adversarial-review.md` first.

- [ ] **Step 2: Create the stable Databricks bookmark and the experimental branch**

```bash
git branch databricks-team        # stable, primary workflow — left untouched
git checkout -b general-team       # experimental generalization branch
git branch --show-current
```
Expected: on `general-team`; `databricks-team` exists as a bookmark of current `main`.

---

## Task 2: Tool-binding de-risk spike (DECISION GATE — do this before the rest)

**Files:** none (validation only) — this is the highest risk in the brainstorm; validate the hybrid model works before building profiles on top of it.

The premise: non-Databricks teams are assembled from **dynamically generated** specialists, dispatched via the PM's existing dynamic path (`agents/pm-orchestrator.md` lines ~141–153), which uses `model`+full-prompt and `general-purpose` (tools = `*`, so generic `Bash`/`Read`/`Write` are always present and no Databricks-MCP grant is needed). Confirm this path is real and adequate before depending on it.

- [ ] **Step 1: Confirm the dynamic-dispatch path exists and needs no MCP grant**

Run:
```bash
grep -q "For \*\*dynamic agents\*\*" agents/pm-orchestrator.md && \
grep -q "general-purpose" agents/pm-orchestrator.md && echo "dynamic path present"
```
Expected: `dynamic path present`. (This path already dispatches runtime-generated agents from `.agent-team/agents/*.md` — generalization reuses it rather than inventing a new mechanism.)

- [ ] **Step 2: Confirm the specialist generator can emit a non-DB agent with generic tools**

Read `templates/meta/specialist-generator.yaml`. Confirm its `mcp_tools` default is `[]` and the generated frontmatter does not force any Databricks tool. Expected observation: a generated specialist defaults to generic tools only.

- [ ] **Step 3: DECISION GATE (record outcome inline in this plan, then proceed)**

The architecture this plan builds on:
- **Databricks target → curated registered agents, unchanged** (`subagent_type` dispatch, static Databricks-MCP tools). No regression risk.
- **All other targets → generated specialists + tech SMEs**, dispatched dynamically with generic tools.

If Steps 1–2 both pass, this hybrid is sound — proceed to Task 3. If the dynamic path were missing or forced Databricks tools (it is not, per current `pm-orchestrator.md`), the fallback would be per-profile registered-agent variants; that fallback is NOT needed and is out of scope.

- [ ] **Step 4: No commit** (validation only).

---

## Task 3: Define the target-profile schema

**Files:**
- Create: `lib/target-schema.yaml`

- [ ] **Step 1: Write the schema**

```yaml
# Target Profile Schema
# A target profile (targets/<name>.yaml) declares everything stack-specific that
# the harness needs, so the team-builder / start-team / deploy / validation logic
# stays target-neutral and reads choices from here.
#
# The Databricks profile (targets/databricks.yaml) reproduces today's behavior
# exactly; it is the default when no --target is given and the PRD does not clearly
# indicate another stack.

schema_version: 1

# --- identity ---
name: string                 # profile slug, must equal the filename stem
display_name: string         # human label, e.g. "Full-Stack Web"
description: string          # one line

# Keywords used to AUTO-DETECT this target from PRD text when --target is omitted.
# The create-team auto-detector scores each profile by keyword hits; highest wins,
# ties and zero-hits fall back to `generic`. Databricks always wins on databricks hits.
detect_keywords: [string]    # e.g. ["react", "frontend", "rest api", "fastapi"]

# --- team composition ---
# Curated registered agents to use AS-IS via subagent_type dispatch. Only the
# databricks profile populates this (its 8 agents). Other profiles leave it empty
# and rely on generated specialists.
curated_agents: [string]     # e.g. ["data-engineer","app-developer",...] or []

# Capability tags valid for THIS target (replaces the hardwired table in team-builder).
# Each maps to how the team-builder satisfies it.
capabilities:
  - tag: string              # e.g. "api-backend"
    triggered_by: string     # PRD phrasing that implies this capability
    # How to satisfy it:
    #   curated:<agent>   → use a curated agent (databricks only)
    #   generate:<role>   → generate a specialist via specialist-generator
    satisfy: string

# Technical-domain SMEs to spin up in Phase 0 (recovers per-stack specificity).
# Each becomes a generated agent from templates/meta/tech-sme-generator.yaml.
tech_smes: [string]          # e.g. ["docker","fastapi"] ; [] for databricks (it has curated depth)

# --- project skeleton ---
# Files/dirs to scaffold in start-team Step 3 (replaces the hardwired DAB scaffold).
scaffold:
  marker_file: string        # if this file exists, skip scaffolding (e.g. "databricks.yml")
  create_dirs: [string]      # e.g. ["frontend/src","backend/app","tests"]
  create_files:              # path → short description of starter content
    - path: string
      purpose: string

# --- deploy ---
deploy:
  # curated:<agent> (databricks → deploy-engineer) or generate:<role>
  satisfy: string
  verb: string               # the deploy command, e.g. "databricks bundle deploy" | "docker compose up -d" | "vercel deploy --prod"

# --- validation (app-validation-loop driver selection) ---
validation:
  driver: browser | http | cli | eval   # how journeys are driven
  # how to fetch backend evidence for the dual-channel capture
  log_command: string        # e.g. "databricks apps logs <app>" | "docker compose logs --tail=200" | "tail -n 200 server.log"

# --- QA assertions (replaces hardwired E2E checks in qa-engineer) ---
qa_assertions:
  e2e: [string]              # phase 3+ checks, e.g. ["docker build succeeds","compose config valid"]
  deployed: [string]         # phase 4 checks, e.g. ["container healthy on :8080","/health returns 200"]

# --- adversarial reviewer focus ---
# Extra attack surfaces the adversarial-reviewer should prioritize for this stack.
security_focus: [string]     # e.g. ["secrets in frontend bundle","CORS misconfig","exposed ports"]
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" lib/target-schema.yaml`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add lib/target-schema.yaml
git commit -m "feat: add target-profile schema"
```

---

## Task 4: Write the Databricks profile (reproduces today exactly)

**Files:**
- Create: `targets/databricks.yaml`

This is the regression anchor: it must encode exactly what the harness does today.
Curated agents = the current 8; deploy = `databricks bundle deploy`; validation =
browser via `databricks apps logs`; QA = the current E2E/deployed assertions from
`agents/qa-engineer.md`.

- [ ] **Step 1: Write the profile**

```yaml
schema_version: 1
name: databricks
display_name: Databricks
description: Databricks application — UC, DABs, Spark, Model Serving, Apps (default profile)

detect_keywords: [databricks, unity catalog, delta, spark, dab, "asset bundle", "model serving", "vector search", genie, lakebase, "databricks app"]

# Use the existing curated registered agents AS-IS — zero behavior change.
curated_agents:
  - data-discovery
  - data-engineer
  - data-scientist
  - genai-architect
  - ui-ux-analyst
  - app-developer
  - deploy-engineer
  - qa-engineer

capabilities:
  - {tag: data-profiling, triggered_by: existing tables/schemas or --catalog/--schema, satisfy: "curated:data-discovery"}
  - {tag: catalog-exploration, triggered_by: references existing catalog/schema, satisfy: "curated:data-discovery"}
  - {tag: data-ingestion, triggered_by: data loading/ETL/file processing, satisfy: "curated:data-engineer"}
  - {tag: data-transformation, triggered_by: cleaning/feature-eng/aggregation, satisfy: "curated:data-engineer"}
  - {tag: etl, triggered_by: batch/streaming pipelines, satisfy: "curated:data-engineer"}
  - {tag: streaming, triggered_by: real-time processing, satisfy: "curated:data-engineer"}
  - {tag: ml-training, triggered_by: model training/experiment tracking, satisfy: "curated:data-scientist"}
  - {tag: ml-serving, triggered_by: model deployment/inference, satisfy: "curated:data-scientist"}
  - {tag: feature-engineering, triggered_by: feature store/tables, satisfy: "curated:data-scientist"}
  - {tag: genai-rag, triggered_by: RAG/doc Q&A/retrieval, satisfy: "curated:genai-architect"}
  - {tag: genai-prompt-engineering, triggered_by: prompt design/few-shot, satisfy: "curated:genai-architect"}
  - {tag: vector-search, triggered_by: embedding storage/similarity, satisfy: "curated:genai-architect"}
  - {tag: embeddings, triggered_by: embedding generation, satisfy: "curated:genai-architect"}
  - {tag: llm-integration, triggered_by: LLM API calls, satisfy: "curated:genai-architect"}
  - {tag: web-app, triggered_by: web UI/dashboard, satisfy: "curated:app-developer"}
  - {tag: api-backend, triggered_by: REST/backend services, satisfy: "curated:app-developer"}
  - {tag: frontend, triggered_by: React/UI components, satisfy: "curated:app-developer"}
  - {tag: ui-design, triggered_by: mockups/wireframes, satisfy: "curated:ui-ux-analyst"}
  - {tag: ux-workflow, triggered_by: journeys/personas, satisfy: "curated:ui-ux-analyst"}
  - {tag: wireframing, triggered_by: screen layouts, satisfy: "curated:ui-ux-analyst"}
  - {tag: frontend-planning, triggered_by: component architecture, satisfy: "curated:ui-ux-analyst"}
  - {tag: databricks-app, triggered_by: Databricks Apps deployment, satisfy: "curated:app-developer"}
  - {tag: deployment, triggered_by: DAB config/CI-CD, satisfy: "curated:deploy-engineer"}

# Databricks curated agents already carry deep stack knowledge — no tech SMEs needed.
tech_smes: []

scaffold:
  marker_file: databricks.yml
  create_dirs: [src, resources, tests]
  create_files:
    - {path: databricks.yml, purpose: "base DAB bundle config"}

deploy:
  satisfy: "curated:deploy-engineer"
  verb: "databricks bundle deploy"

validation:
  driver: browser
  log_command: "databricks apps logs <app_resource_name>"

qa_assertions:
  e2e:
    - "databricks bundle validate passes"
    - "E2E test scenarios cover PRD success criteria"
    - "Security review: no secrets, proper auth patterns"
  deployed:
    - "Pipeline executes successfully"
    - "Serving endpoints respond correctly"
    - "App loads and basic smoke test passes"

security_focus:
  - "UC permission grants too broad"
  - "secrets hardcoded instead of dbutils.secrets / app resources"
  - "serving endpoint unauthenticated"
```

- [ ] **Step 2: Verify it parses and curated_agents matches the real registered set**

Run:
```bash
python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" targets/databricks.yaml
python3 -c "
import yaml,glob,os
prof=yaml.safe_load(open('targets/databricks.yaml'))
registered={os.path.basename(p)[:-3] for p in glob.glob('agents/*.md')}
missing=[a for a in prof['curated_agents'] if a not in registered and a!='qa-engineer' or (a=='qa-engineer' and 'qa-engineer' not in registered)]
missing=[a for a in prof['curated_agents'] if a not in registered]
assert not missing, f'profile names agents that are not registered: {missing}'
print('curated_agents all registered')
"
```
Expected: `curated_agents all registered`.

- [ ] **Step 3: Commit**

```bash
git add targets/databricks.yaml
git commit -m "feat: add databricks target profile (reproduces current team)"
```

---

## Task 5: Write the web-fullstack profile (worked non-DB example)

**Files:**
- Create: `targets/web-fullstack.yaml`

- [ ] **Step 1: Write the profile**

```yaml
schema_version: 1
name: web-fullstack
display_name: Full-Stack Web
description: React/Vite frontend + FastAPI or Node backend, deployed as a containerized or hosted web app

detect_keywords: [react, vue, svelte, frontend, "rest api", fastapi, express, node, "full stack", website, "web app", typescript, tailwind, vite]

# No curated registered agents — assembled from generated specialists + tech SMEs.
curated_agents: []

capabilities:
  - {tag: frontend, triggered_by: React/Vue/UI components, satisfy: "generate:frontend-engineer"}
  - {tag: api-backend, triggered_by: REST/GraphQL backend, satisfy: "generate:backend-engineer"}
  - {tag: ui-design, triggered_by: mockups/wireframes, satisfy: "generate:ui-ux-designer"}
  - {tag: ux-workflow, triggered_by: user journeys/personas, satisfy: "generate:ui-ux-designer"}
  - {tag: integration, triggered_by: frontend↔backend wiring, satisfy: "generate:integration-engineer"}
  - {tag: deployment, triggered_by: hosting/CI-CD, satisfy: "generate:deploy-specialist"}

# Technical SMEs run in Phase 0 and write tech-playbook.md to recover specificity.
tech_smes: [react, fastapi, web-security]

scaffold:
  marker_file: package.json
  create_dirs: [frontend/src, backend/app, tests]
  create_files:
    - {path: package.json, purpose: "root workspace manifest / scripts"}
    - {path: backend/requirements.txt, purpose: "python backend deps (fastapi, uvicorn)"}
    - {path: docker-compose.yml, purpose: "frontend + backend services for local + deploy"}

deploy:
  satisfy: "generate:deploy-specialist"
  verb: "docker compose up -d --build"

validation:
  driver: browser
  log_command: "docker compose logs --tail=200 backend"

qa_assertions:
  e2e:
    - "frontend builds (npm run build) with no errors"
    - "backend imports and starts without exceptions"
    - "no secrets committed; .env is gitignored"
    - "E2E scenarios cover PRD success criteria"
  deployed:
    - "compose stack is healthy (docker compose ps all 'running')"
    - "backend /health returns 200"
    - "frontend served and renders root route"

security_focus:
  - "secrets or API keys bundled into the frontend build"
  - "CORS misconfigured (wildcard with credentials)"
  - "unauthenticated mutating endpoints"
  - "SQL/NoSQL/prompt injection on user input"
  - "exposed ports beyond what the app needs"
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" targets/web-fullstack.yaml`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add targets/web-fullstack.yaml
git commit -m "feat: add web-fullstack target profile"
```

---

## Task 6: Write the docker, genai-finetuning, and generic profiles

**Files:**
- Create: `targets/docker.yaml`
- Create: `targets/genai-finetuning.yaml`
- Create: `targets/generic.yaml`

- [ ] **Step 1: Write `targets/docker.yaml`**

```yaml
schema_version: 1
name: docker
display_name: Docker Service
description: Containerized backend service (single or multi-container) built and run via Docker/Compose

detect_keywords: [docker, dockerfile, container, "docker compose", microservice, kubernetes, k8s, image, "containerized"]

curated_agents: []

capabilities:
  - {tag: api-backend, triggered_by: service/API logic, satisfy: "generate:backend-engineer"}
  - {tag: containerization, triggered_by: Dockerfile/compose/image build, satisfy: "generate:container-engineer"}
  - {tag: data-store, triggered_by: db/cache/queue dependency, satisfy: "generate:backend-engineer"}
  - {tag: deployment, triggered_by: registry push/orchestration, satisfy: "generate:deploy-specialist"}

tech_smes: [docker, web-security]

scaffold:
  marker_file: Dockerfile
  create_dirs: [app, tests]
  create_files:
    - {path: Dockerfile, purpose: "service image build"}
    - {path: docker-compose.yml, purpose: "service + dependencies"}
    - {path: requirements.txt, purpose: "or package.json — runtime deps"}

deploy:
  satisfy: "generate:deploy-specialist"
  verb: "docker compose up -d --build"

validation:
  driver: http
  log_command: "docker compose logs --tail=200"

qa_assertions:
  e2e:
    - "docker build succeeds"
    - "docker compose config is valid"
    - "no secrets baked into image layers"
    - "image runs as non-root where feasible"
  deployed:
    - "container reports healthy"
    - "primary endpoint returns expected status"

security_focus:
  - "secrets in image layers or ENV defaults"
  - "running as root unnecessarily"
  - "exposed ports beyond service need"
  - "base image with known CVEs / :latest pin"
```

- [ ] **Step 2: Write `targets/genai-finetuning.yaml`**

```yaml
schema_version: 1
name: genai-finetuning
display_name: GenAI / ML Fine-Tuning
description: Fine-tune or adapt an LLM/ML model with a reproducible training + evaluation harness

detect_keywords: [finetune, "fine-tune", "fine tuning", lora, qlora, sft, rlhf, dpo, "training run", "eval harness", peft, "hugging face", transformers, checkpoint, dataset, "model adaptation"]

curated_agents: []

capabilities:
  - {tag: data-prep, triggered_by: dataset curation/formatting, satisfy: "generate:data-prep-engineer"}
  - {tag: training, triggered_by: fine-tuning/training loop, satisfy: "generate:training-engineer"}
  - {tag: evaluation, triggered_by: eval/benchmark/metrics, satisfy: "generate:eval-engineer"}
  - {tag: model-serving, triggered_by: serve/inference the tuned model, satisfy: "generate:serving-engineer"}
  - {tag: deployment, triggered_by: package/ship the artifact, satisfy: "generate:deploy-specialist"}

tech_smes: [finetuning, ml-evaluation]

scaffold:
  marker_file: pyproject.toml
  create_dirs: [data, train, eval, configs, tests]
  create_files:
    - {path: pyproject.toml, purpose: "deps (transformers, peft, datasets, etc.)"}
    - {path: configs/train.yaml, purpose: "training hyperparameters"}
    - {path: eval/run_eval.py, purpose: "evaluation harness entrypoint"}

deploy:
  satisfy: "generate:serving-engineer"
  verb: "python -m serve  # or container/endpoint per PRD"

# Fine-tuning has no UI to drive — journeys become an eval harness run.
validation:
  driver: eval
  log_command: "tail -n 200 eval/eval.log"

qa_assertions:
  e2e:
    - "training config loads and a 1-step smoke train runs"
    - "dataset schema matches the training contract"
    - "no secrets / no raw API keys in configs"
  deployed:
    - "eval harness runs and writes metrics"
    - "tuned model beats the baseline on the PRD's target metric (or regression is reported)"

security_focus:
  - "training data PII/licensing leakage"
  - "eval set contamination / train-test leakage"
  - "model card / metric claims unsupported by the eval output"
  - "secrets in config or checkpoint metadata"
```

- [ ] **Step 3: Write `targets/generic.yaml`**

```yaml
schema_version: 1
name: generic
display_name: Generic
description: Fallback profile for stacks that do not match a specialized target — leans entirely on tech SMEs + generated specialists

detect_keywords: []          # never auto-detected; only the explicit fallback

curated_agents: []

capabilities:
  - {tag: implementation, triggered_by: any build requirement, satisfy: "generate:implementation-engineer"}
  - {tag: deployment, triggered_by: any ship/run requirement, satisfy: "generate:deploy-specialist"}

# The PRD's primary technologies become tech-SME domains at assembly time
# (team-builder fills this from PRD analysis when the profile leaves it open).
tech_smes: []

scaffold:
  marker_file: README.md
  create_dirs: [src, tests]
  create_files:
    - {path: README.md, purpose: "project overview"}

deploy:
  satisfy: "generate:deploy-specialist"
  verb: "echo 'define deploy in PRD'  # generic: deploy specialist derives from PRD"

validation:
  driver: cli
  log_command: "tail -n 200 run.log"

qa_assertions:
  e2e:
    - "project builds / imports without error"
    - "tests present and passing for new code"
    - "no secrets committed"
  deployed:
    - "primary entrypoint runs and produces expected output"

security_focus:
  - "hardcoded secrets"
  - "unvalidated external input"
```

- [ ] **Step 4: Verify all three parse**

Run:
```bash
for f in targets/docker.yaml targets/genai-finetuning.yaml targets/generic.yaml; do
  python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$f" || echo "FAIL: $f"
done; echo "parsed"
```
Expected: `parsed` with no `FAIL:` lines.

- [ ] **Step 5: Commit**

```bash
git add targets/docker.yaml targets/genai-finetuning.yaml targets/generic.yaml
git commit -m "feat: add docker, genai-finetuning, generic target profiles"
```

---

## Task 7: Add the technical-SME generator meta-template

**Files:**
- Create: `templates/meta/tech-sme-generator.yaml`

Mirrors `templates/meta/domain-sme-generator.yaml` (which stays, for *industry* SMEs).
This one produces a *technical*-domain SME (e.g. "Docker SME", "Fine-Tuning SME")
that writes a `tech-playbook.md` broadcast to all builders in Phase 0 — the
mechanism that recovers per-stack specificity.

- [ ] **Step 1: Write the meta-template**

```yaml
type: generator
output_format: agent-definition-md
description: >
  Generates a Technical Subject Matter Expert agent definition. The tech SME
  researches a specific technology/stack (e.g. Docker, FastAPI, LoRA fine-tuning)
  and writes a tech-playbook.md that all downstream builder agents reference.
  Industry/domain SMEs are generated by domain-sme-generator.yaml instead.

generator_prompt: |
  Given the technology "{{tech_domain}}" and project "{{project_description}}",
  generate a Technical Subject Matter Expert agent definition as a Markdown file
  with YAML frontmatter.

  The agent definition MUST follow this exact format:

  ---
  name: {{tech_slug}}-tech-sme
  display_name: {{tech_display}} Tech SME
  model: haiku
  phase: [0]
  parallel_group: planning
  skills: [{{relevant_skills_if_any}}]
  mcp_tools: []
  inputs: []
  outputs:
    - contract: tech-playbook
      consumer: broadcast
      artifacts:
        - .agent-team/artifacts/tech-playbook-{{tech_slug}}.md
  constraints:
    - Write only to .agent-team/artifacts/
    - Do not write any application code
    - Focus on research and concrete, actionable guidance
  ---

  The prompt body MUST instruct the tech SME to:
  1. Research {{tech_domain}} best practices using WebSearch/WebFetch and any
     relevant skills available in the environment.
  2. Document the canonical project layout, key commands, and version pins.
  3. List the top failure modes for {{tech_domain}} and how to avoid them
     (this is the highest-value section — be specific and concrete).
  4. Specify security/quality must-dos for {{tech_domain}}.
  5. Give 3–5 copy-pasteable reference snippets (config, Dockerfile, training
     config, etc.) that builders can adapt.
  6. Write all findings to .agent-team/artifacts/tech-playbook-{{tech_slug}}.md.

  Make the SME's prompt specific to {{tech_domain}}. Prefer concrete, current
  guidance over generic advice. The playbook is consumed by builder agents in
  later phases, so write it for an engineer who knows software but not this stack.

defaults:
  model: haiku
  phase: [0]
  skills: []
  mcp_tools: []
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" templates/meta/tech-sme-generator.yaml`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add templates/meta/tech-sme-generator.yaml
git commit -m "feat: add technical-SME generator meta-template"
```

---

## Task 8: Add the --target flag and profile loading to /create-team

**Files:**
- Modify: `commands/create-team.md`

- [ ] **Step 1: Add `--target` to the flags list**

Find:
```markdown
- `--catalog <name>` — Unity Catalog catalog to profile
- `--schema <name>` — Unity Catalog schema/database to profile
- `--max-tables N` — maximum tables to profile (default: 50; passed through to data-analyzer)
```
Replace with:
```markdown
- `--target <name>` — target profile to build for: `databricks` (default), `web-fullstack`,
  `docker`, `genai-finetuning`, or `generic`. Profiles live in `targets/<name>.yaml`.
  If omitted, auto-detect from the PRD (Step 1.4).
- `--catalog <name>` — Unity Catalog catalog to profile (databricks target only)
- `--schema <name>` — Unity Catalog schema/database to profile (databricks target only)
- `--max-tables N` — maximum tables to profile (default: 50; passed through to data-analyzer)
```

- [ ] **Step 2: Update the command's headline so it is target-neutral**

Find:
```markdown
# /create-team

You are creating a dynamic agent team to build a Databricks application.
```
Replace with:
```markdown
# /create-team

You are creating a dynamic agent team to build a software project. The **target
profile** (`targets/<name>.yaml`) selects the technology stack; `databricks` is the
default and reproduces the original Databricks-only behavior.
```

- [ ] **Step 3: Insert the target-resolution step (new Step 1.4, after Step 1 Read the PRD)**

Find the start of Step 1.5:
```markdown
### Step 1.5: Analyze existing data
```
Insert immediately BEFORE it:
```markdown
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
```

- [ ] **Step 4: Gate the Databricks-only data step behind the databricks target**

Find:
```markdown
### Step 1.5: Analyze existing data

**Trigger:** Run this step when either condition is true:
```
Replace with:
```markdown
### Step 1.5: Analyze existing data (databricks target only)

**Applies only when `active_profile.name == "databricks"`.** For all other targets,
skip this step entirely (there is no Unity Catalog to profile).

**Trigger:** Run this step when either condition is true:
```

- [ ] **Step 5: Pass the profile to team-builder (Step 2)**

Find:
```markdown
### Step 2: Invoke team-builder skill

Use the team-builder skill to:
```
Replace with:
```markdown
### Step 2: Invoke team-builder skill

Pass `active_profile` (from Step 1.4) to the team-builder skill — it is the
authoritative source for capability vocabulary, curated vs. generated agents,
tech SMEs, scaffold, deploy, validation, and QA assertions.

Use the team-builder skill to:
```

- [ ] **Step 6: Verify wiring**

Run:
```bash
grep -q "### Step 1.4: Resolve the target profile" commands/create-team.md && \
grep -q "active_profile" commands/create-team.md && \
grep -q "databricks target only" commands/create-team.md && echo ok
```
Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add commands/create-team.md
git commit -m "feat: /create-team resolves a target profile (flag + auto-detect)"
```

---

## Task 9: Make team-builder profile-driven

**Files:**
- Modify: `skills/team-builder/SKILL.md`

The most significant edit. The capability table, curated-agent selection, specialist
generation, and tech-SME spin-up all source from `active_profile`. Keep the Databricks
behavior identical when `active_profile.name == "databricks"`.

- [ ] **Step 1: Make the opening target-neutral and declare the profile input**

Find:
```markdown
# Team Builder

You are assembling a team of AI agents to build a Databricks application.
Given a PRD document, you will analyze it and produce a complete team configuration.
```
Replace with:
```markdown
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
```

- [ ] **Step 2: Replace the hardwired capability table with a profile reference (Step 2)**

Find the entire Step 2 block, from:
```markdown
## Step 2: Map to Capability Tags

Map each PRD requirement to one or more capability tags:

| Capability Tag | Triggered By |
```
…through the end of that table (the last row `| domain:* | Industry-specific expertise (e.g., domain:retail, domain:healthcare) |`).
Replace the whole block with:
```markdown
## Step 2: Map to Capability Tags

Map each PRD requirement to one or more capability tags **from
`active_profile.capabilities`**. Each profile entry has `tag`, `triggered_by`
(the PRD phrasing that implies it), and `satisfy` (`curated:<agent>` or
`generate:<role>`). Match PRD requirements against `triggered_by` to select tags.

`domain:*` tags (industry expertise, e.g. `domain:retail`) are always available
regardless of profile and are satisfied by an industry SME (Step 4).

> The capability vocabulary is no longer hardwired here — it lives in the target
> profile so new stacks are added by authoring a profile, not editing this skill.
> For the canonical Databricks vocabulary, see `targets/databricks.yaml`.
```

- [ ] **Step 3: Make curated-agent selection profile-driven (Step 3)**

Find:
```markdown
## Step 3: Select Curated Agents

For each capability tag, check if a curated template in `templates/core/` covers it.
Read each template's `capabilities` field to match.
```
Replace with:
```markdown
## Step 3: Select Curated Agents

For each matched capability whose `satisfy` is `curated:<agent>`, select that curated
registered agent (its template is in `templates/core/`). Only the `databricks` profile
uses curated agents; other profiles leave `curated_agents` empty and satisfy every
capability via `generate:<role>` (Step 4).
```

- [ ] **Step 4: Make the always-include set profile-aware**

Find (note: this block was edited by the adversarial-review plan; match the
post-adversarial text):
```markdown
Always include these agents regardless of capabilities:
- **qa-engineer** (always needed for validation)
- **deploy-engineer** (always needed for deployment)
- **adversarial-reviewer** (always needed; independent red-team gate that runs
  in the final phase AFTER the qa-engineer gate passes — see Step 5)
```
Replace with:
```markdown
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
```

- [ ] **Step 5: Add tech-SME generation and make Step 4 profile-driven**

Find:
```markdown
## Step 4: Generate Dynamic Specialists

For capability tags not covered by any curated template:
1. Read the appropriate meta-template from `templates/meta/`
   - `domain:*` tags → use `domain-sme-generator.yaml`
   - All other uncovered tags → use `specialist-generator.yaml`
2. Fill in the meta-template variables with PRD context
3. Generate the full agent definition
4. Write to `.agent-team/agents/<name>.md`
```
Replace with:
```markdown
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
```

- [ ] **Step 6: Make the scaffold/deploy notes reference the profile (Step 7 area)**

Find in Step 7:
```markdown
Write all files:
- `.agent-team/team-manifest.yaml` — team roster, phases, model tiers
```
Replace with:
```markdown
Write all files:
- `.agent-team/team-manifest.yaml` — team roster, phases, model tiers. **Also record
  `target: <active_profile.name>` and embed the resolved `scaffold`, `deploy`,
  `validation`, and `qa_assertions` blocks from the profile so `/start-team`, the
  deploy agent, the QA agent, and the validation loop read them without re-loading
  the profile file.**
```

- [ ] **Step 7: Verify wiring**

Run:
```bash
grep -q "active_profile.* is authoritative" skills/team-builder/SKILL.md && \
grep -q "from \*\*\`active_profile.capabilities\`\*\*" skills/team-builder/SKILL.md && \
grep -q "4a. Technical SMEs" skills/team-builder/SKILL.md && \
grep -q "tech-sme-generator.yaml" skills/team-builder/SKILL.md && \
grep -q "target: <active_profile.name>" skills/team-builder/SKILL.md && echo ok
```
Expected: `ok`.

- [ ] **Step 8: Commit**

```bash
git add skills/team-builder/SKILL.md
git commit -m "feat: team-builder sources team composition from the target profile"
```

---

## Task 10: Make /start-team scaffold profile-driven

**Files:**
- Modify: `commands/start-team.md`

- [ ] **Step 1: Replace the hardwired DAB scaffold (Step 3)**

Find:
```markdown
### 3. Scaffold DAB Project

If `databricks.yml` doesn't exist, create the base DAB structure:
```
```
databricks.yml
src/
resources/
tests/
```
```
Replace with:
```markdown
### 3. Scaffold Project (profile-driven)

Read the `scaffold` block from `.agent-team/team-manifest.yaml` (embedded by
team-builder from the target profile). If `scaffold.marker_file` already exists,
skip scaffolding. Otherwise create `scaffold.create_dirs` and each
`scaffold.create_files` entry with minimal starter content matching its `purpose`.

For the `databricks` target this is exactly the original DAB scaffold
(`databricks.yml`, `src/`, `resources/`, `tests/`). For other targets it is the
profile's skeleton (e.g. `package.json` + `frontend/` + `backend/` for web-fullstack).
```

- [ ] **Step 2: Make the headline target-neutral**

Find:
```markdown
# /start-team

You are launching the agent team to build the Databricks application.
```
Replace with:
```markdown
# /start-team

You are launching the agent team to build the project for its configured target
(read `target:` from `.agent-team/team-manifest.yaml`).
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -q "### 3. Scaffold Project (profile-driven)" commands/start-team.md && \
grep -q "scaffold.marker_file" commands/start-team.md && echo ok
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add commands/start-team.md
git commit -m "feat: /start-team scaffolds from the target profile"
```

---

## Task 11: Make the QA agent's E2E/deploy checks profile-driven

**Files:**
- Modify: `agents/qa-engineer.md`

The Phase 3/4 checklist currently hardwires `databricks bundle validate`, serving
endpoints, etc. Make those read from the manifest's `qa_assertions`.

- [ ] **Step 1: Replace the hardwired E2E and Deployed sections**

Find:
```markdown
### E2E Validation (Phase 3+)
- [ ] `databricks bundle validate` passes
- [ ] E2E test scenarios cover PRD success criteria
- [ ] Security review: no secrets, proper auth patterns

### Deployed Validation (Phase 4)
- [ ] Pipeline executes successfully
- [ ] Serving endpoints respond correctly
- [ ] App loads and basic smoke test passes
```
Replace with:
```markdown
### E2E Validation (Phase 3+) — profile-driven
Read `qa_assertions.e2e` from `.agent-team/team-manifest.yaml` and verify EACH
listed assertion. For the `databricks` target these are `databricks bundle validate`,
E2E scenarios cover PRD criteria, and the secrets/auth security review. For other
targets they are the profile's checks (e.g. `npm run build` succeeds, backend starts).

### Deployed Validation (Phase 4) — profile-driven
Read `qa_assertions.deployed` from the manifest and verify EACH listed assertion.
For `databricks`: pipeline executes, serving endpoints respond, app smoke test.
For other targets: the profile's checks (e.g. container healthy, `/health` 200).
```

- [ ] **Step 2: Make the "Skills to Use" note target-aware**

Find:
```markdown
## Skills to Use
- Invoke the `databricks-query` skill to validate SQL and table schemas
- Invoke the `asset-bundles` skill to validate DAB configuration
- Invoke the `app-validation-loop` skill in Phase 4 to drive the deployed app
  through the PRD user journeys (only when an `app_url` is provided)
```
Replace with:
```markdown
## Skills to Use
- For the `databricks` target: invoke `databricks-query` to validate SQL/schemas and
  `asset-bundles` to validate DAB config.
- For non-Databricks targets: use `Bash` to run the profile's `qa_assertions`
  (build/test/health commands) — do not invoke Databricks skills.
- All targets: invoke the `app-validation-loop` skill in Phase 4 to drive the
  deployed artifact through the PRD user journeys, when journeys + an entrypoint
  (`app_url` for UI targets, or the profile's validation driver) are provided.
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -q "E2E Validation (Phase 3+) — profile-driven" agents/qa-engineer.md && \
grep -q "qa_assertions.deployed" agents/qa-engineer.md && echo ok
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add agents/qa-engineer.md
git commit -m "feat: qa-engineer reads E2E/deployed assertions from the target profile"
```

---

## Task 12: Make app-validation-loop driver target-aware

**Files:**
- Modify: `skills/app-validation-loop/SKILL.md`

The dual-channel principle (drive + capture logs) stays; the *driver* is chosen from
the profile. Read the current SKILL.md opening before editing to place this naturally.

- [ ] **Step 1: Read the current skill head**

Run: `sed -n '1,40p' skills/app-validation-loop/SKILL.md` (read only — to find the insertion point after the frontmatter and intro).

- [ ] **Step 2: Insert a driver-selection section right after the skill's intro**

After the skill's first `##` section heading (before the existing Playwright/CDP path
instructions), insert:
```markdown
## Driver selection (target-aware)

Read `validation.driver` and `validation.log_command` from
`.agent-team/team-manifest.yaml` (embedded from the target profile). Select the
driver; the dual-channel evidence rule (action + backend log capture) is the same
for all:

- **browser** — drive the UI with the Playwright + CDP path below (web-fullstack,
  databricks-app). Capture: screenshot + final text, and backend logs via
  `validation.log_command`.
- **http** — drive the service with HTTP requests (curl/httpx) against each journey's
  endpoint. Capture: response status/body, and container logs via `log_command`.
- **cli** — drive the artifact via its CLI entrypoint with the journey's input on
  stdin/args. Capture: stdout/stderr, and `log_command` output.
- **eval** — there is no interactive surface; run the project's eval harness and
  treat each journey's `success_criteria` as a metric threshold. Capture: the
  metrics output and `log_command`.

When `validation.driver == browser`, follow the Playwright + CDP / chrome-devtools
paths exactly as documented below. For `http`/`cli`/`eval`, the journey schema and
the PASS/PARTIAL/FAIL verdict + severity model are unchanged — only the drive and
capture mechanism differs.
```

- [ ] **Step 3: Verify**

Run: `grep -q "## Driver selection (target-aware)" skills/app-validation-loop/SKILL.md && echo ok`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add skills/app-validation-loop/SKILL.md
git commit -m "feat: app-validation-loop selects driver from the target profile"
```

---

## Task 13: Make the adversarial reviewer target-aware

**Files:**
- Modify: `agents/adversarial-reviewer.md`

Inherited from Plan 1; now feed it the profile's `security_focus`.

- [ ] **Step 1: Add a profile-focus instruction**

Find:
```markdown
## Attack surfaces to probe

Work through these deliberately; for each, try to construct a falsifying case:
```
Replace with:
```markdown
## Attack surfaces to probe

If your dispatch prompt includes a `security_focus` list (from the target profile),
treat those as **priority** attack surfaces for this stack — probe them first, in
addition to the general surfaces below.

Work through these deliberately; for each, try to construct a falsifying case:
```

- [ ] **Step 2: Update the PM dispatch to pass security_focus**

In `agents/pm-orchestrator.md`, find the Step 7.5 dispatch prompt (added by Plan 1):
```
  prompt: "<PRD spec text> + <list of .agent-team/contracts/*.yaml paths> +
           'The built artifacts are the current repo state. Try to falsify the
            build per your definition. Write findings to
            .agent-team/status/adversarial-findings-phase-N.yaml.'"
```
Replace with:
```
  prompt: "<PRD spec text> + <list of .agent-team/contracts/*.yaml paths> +
           <security_focus list from team-manifest.yaml, if present> +
           'The built artifacts are the current repo state. Try to falsify the
            build per your definition. Prioritize the security_focus surfaces for
            this target. Write findings to
            .agent-team/status/adversarial-findings-phase-N.yaml.'"
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -q "security_focus" agents/adversarial-reviewer.md && \
grep -q "security_focus list from team-manifest" agents/pm-orchestrator.md && echo ok
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add agents/adversarial-reviewer.md agents/pm-orchestrator.md
git commit -m "feat: adversarial reviewer prioritizes target profile security_focus"
```

---

## Task 14: Version bump

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version and broaden the description**

Find:
```json
  "description": "Dynamically assemble and orchestrate AI agent teams to build Databricks applications end-to-end. Use /create-team to analyze a PRD and assemble a team, then /start-team to execute.",
  "version": "0.2.0",
```
Replace with:
```json
  "description": "Dynamically assemble and orchestrate AI agent teams to build software projects end-to-end across target profiles (Databricks, full-stack web, Docker, GenAI fine-tuning, generic). Use /create-team to analyze a PRD and assemble a team, then /start-team to execute.",
  "version": "0.3.0",
```

- [ ] **Step 2: Verify JSON**

Run: `python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" && echo ok`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "chore: bump plugin to 0.3.0 (target profiles)"
```

---

## Task 15: Regression dry-run — Databricks target unchanged

**Files:** none (validation only). Critical: prove the Databricks team did not regress.

- [ ] **Step 1: Assemble with the default (databricks) target**

If `.agent-team/` exists, move it aside: `mv .agent-team .agent-team.bak 2>/dev/null || true`.
Run: `/create-team test/qa-chatbot-prd.md`
Expected observation: auto-detect resolves `databricks` (the test PRD is a Databricks
chatbot), and the team is assembled from the curated agents.

- [ ] **Step 2: Confirm curated agents and DB scaffold/QA are used**

Run:
```bash
grep -q "target: databricks" .agent-team/team-manifest.yaml && \
grep -q "databricks bundle" .agent-team/team-manifest.yaml && \
grep -rq "data-engineer\|app-developer\|qa-engineer" .agent-team/team-manifest.yaml && \
grep -q "adversarial" .agent-team/team-manifest.yaml && echo "databricks unchanged + adversarial present"
```
Expected: `databricks unchanged + adversarial present` — curated roster intact, DB
deploy verb embedded, adversarial gate inherited.

- [ ] **Step 3: Clean up**

Run: `rm -rf .agent-team && mv .agent-team.bak .agent-team 2>/dev/null || true`

---

## Task 16: New-target dry-run — web-fullstack assembles cleanly

**Files:**
- Create (temporary, do NOT commit): `test/web-todo-prd.md` — a tiny web PRD to exercise a non-DB target.

- [ ] **Step 1: Write a minimal web PRD fixture**

```markdown
# PRD: Team To-Do Web App

Build a full-stack web app: a React frontend and a FastAPI backend with a REST API.
Users can create, list, complete, and delete to-do items. Persist items in a local
SQLite database. Deploy the frontend and backend with Docker Compose.

## User interactions
- Add a to-do from an input box.
- See the list update live.
- Mark a to-do complete; delete a to-do (with a confirm).

## Success criteria
- Adding a to-do shows it in the list without a page reload.
- A completed to-do is visually distinct.
- Deleting a to-do removes it from the list and the database.
```

- [ ] **Step 2: Assemble with the web-fullstack target**

If `.agent-team/` exists: `mv .agent-team .agent-team.bak 2>/dev/null || true`.
Run: `/create-team test/web-todo-prd.md --target web-fullstack`

- [ ] **Step 3: Confirm a sensible non-DB team was assembled**

Run:
```bash
grep -q "target: web-fullstack" .agent-team/team-manifest.yaml && \
grep -q "docker compose up" .agent-team/team-manifest.yaml && \
ls .agent-team/agents/ | grep -qi "frontend\|backend" && \
ls .agent-team/agents/ | grep -qi "tech-sme" && \
grep -q "adversarial" .agent-team/team-manifest.yaml && \
! grep -q "databricks bundle" .agent-team/team-manifest.yaml && \
echo "web-fullstack assembled: generated specialists + tech SMEs + adversarial, no databricks"
```
Expected: `web-fullstack assembled: generated specialists + tech SMEs + adversarial, no databricks`
— i.e. generated frontend/backend specialists exist, tech SMEs were generated, the
adversarial gate is present, the deploy verb is `docker compose`, and no Databricks
artifacts leaked in.

- [ ] **Step 4: Confirm journeys use the right driver**

Run: `grep -q "driver: browser" .agent-team/team-manifest.yaml && echo "driver ok"`
Expected: `driver ok` (web-fullstack uses the browser driver).

- [ ] **Step 5: Clean up**

Run: `rm -rf .agent-team test/web-todo-prd.md && mv .agent-team.bak .agent-team 2>/dev/null || true`
(Do not commit the fixture or generated `.agent-team/`.)

---

## Task 17: Do NOT merge — hand back to user

**Files:** none.

- [ ] **Step 1: Final parse sweep**

Run:
```bash
for f in lib/target-schema.yaml targets/*.yaml templates/meta/tech-sme-generator.yaml; do
  python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$f" || echo "FAIL: $f"
done
python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" || echo "FAIL: plugin.json"
echo "sweep done"
```
Expected: `sweep done`, no `FAIL:`.

- [ ] **Step 2: Summarize and stop**

This branch (`general-team`) stays unmerged. Report to the user the dry-run results
from Tasks 15–16. The user decides whether to keep iterating on `general-team`, run a
real end-to-end build on a non-DB PRD, or merge to `main`. `databricks-team` and
`main` remain the stable Databricks workflow with the adversarial gate.

---

## Self-Review (completed by plan author)

**Spec coverage** (against the brainstorm Recommendation, Option A + A1):
1. Extract `targets/` profile layer → Tasks 3–6 (schema + 5 profiles). ✓
2. Re-shape agents to be profile-parameterized, decouple tool binding → Task 2 (de-risk spike: hybrid model — DB curated unchanged, others generated via the existing dynamic path) + Task 9. ✓
3. Generalize SMEs to technical domains → Task 7 (`tech-sme-generator.yaml`) + Task 9 Step 5 (4a). ✓
4. Strengthen/target-aware test-iteration loop → Task 11 (profile QA) + Task 12 (driver selection). ✓
5. Adversarial reviewer in the general team, target-aware → Task 13 (inherited from Plan 1, fed `security_focus`). ✓
- Databricks reproduced exactly + branch isolation (`databricks-team` stable, `general-team` experimental, not merged) → Task 1, Task 4, Task 15, Task 17. ✓
- Top risk #1 (tool-binding) addressed first as a decision gate → Task 2. ✓
- Top risk #2 (specificity regression) mitigated by tech SMEs and validated against the known-good Databricks baseline → Task 7, Task 15. ✓

**Placeholder scan:** No TBD/TODO. New files have full content; edits are find+replace with literal text; each verification has an exact command + expected output. The one created fixture (Task 16) has full content and is explicitly not committed. ✓

**Type/name consistency:** `active_profile` (passed create-team→team-builder), profile keys `capabilities/curated_agents/tech_smes/scaffold/deploy/validation/qa_assertions/security_focus/detect_keywords` used identically across the schema (Task 3), every profile (Tasks 4–6), and every consumer (Tasks 8–13); `target:` manifest key (Task 9 Step 6) read by start-team (Task 10), qa-engineer (Task 11), app-validation-loop (Task 12); `tech-sme-generator.yaml` name consistent (Tasks 7, 9). ✓

**Cross-plan consistency:** Task 9 Step 4 edits the exact post-adversarial text that `2026-06-16-adversarial-review.md` Task 5 Step 1 produces; Task 13 edits the exact Step 7.5 dispatch block that adversarial Task 6 Step 1 produces. Run the adversarial plan first. ✓
