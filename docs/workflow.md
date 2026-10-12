# agent-team Workflow

Diagrams render on GitHub (Mermaid). They describe the plugin as it exists on this branch, including the UI/UX loop. Thick arrows (`==>`) mark **iteration loops**; every loop shares the phase's 3-attempt cap, then escalates to a human.

## 1. End-to-end flow

```mermaid
flowchart TD
    PRD(["PRD"]) --> CT["/create-team: team-builder + phase-planner"]
    CT --> CFG[".agent-team/: manifest, agents, contracts, phases, user-journeys"]
    CFG --> ST["/start-team: pm-orchestrator skill runs in the MAIN session"]
    ADD["/add-feature: feature-scoper"] -.-> CFG
    ST --> S1

    subgraph PHASE["Per-phase loop (repeats for each phase)"]
        S1["read_phase_config"] --> S2["resolve_contracts"]
        S2 --> S3["dispatch_agents: worktree-isolated, parallel groups"]
        S3 --> S4["await_agents"]
        S4 --> S5{"agent status?"}
        S5 ==>|"NEEDS_CONTEXT or BLOCKED: re-dispatch"| S3
        S5 -->|"DONE"| S6["merge_worktrees"]
        S6 --> S7{"qa_gate: qa-engineer"}
        S7 ==>|"FAIL: dispatch fix agent, attempt n of 3"| S3
        S7 -->|"PASS"| S74{"ux-critic in gates?"}
        S74 -->|"yes"| UXG["Step 7.4 UX gate (see section 4)"]
        S74 -->|"no"| S75
        UXG ==>|"FAIL: fix and re-QA"| S3
        UXG -->|"PASS"| S75{"adversarial-reviewer in gates?"}
        S75 -->|"yes"| ADV["Step 7.5 adversarial review"]
        S75 -->|"no"| CP
        ADV ==>|"FAIL: fix and re-run QA + review"| S3
        ADV -->|"PASS"| CP["checkpoint + introspection"]
    end

    CP --> HT{"human touchpoint: confirm next phase"}
    HT ==>|"next phase"| S1
    HT -->|"last phase done"| DONE(["All phases complete"])
    S7 -.->|"3 failed attempts"| ESC(["escalate to human"])
```

## 2. Phase structure

```mermaid
flowchart LR
    P0["Phase 0: data-discovery, domain SME"] --> P1["Phase 1: data-engineer, data-scientist, genai-architect, ui-ux-analyst"]
    P1 --> P2["Phase 2: app-developer, consumers of data outputs. Gates: qa-engineer, ux-critic"]
    P2 --> P3["Phase 3: integration"]
    P3 --> P4["Phase 4 (final): deploy-engineer, qa-engineer with journeys. Gate: adversarial-reviewer"]
```

## 3. Orchestration constraint

The harness supports one level of subagent fan-out. The orchestrator therefore runs as a skill in the main session, and workers never spawn workers.

```mermaid
flowchart TD
    MAIN["Main session: pm-orchestrator skill"] --> W1["data-engineer"]
    MAIN --> W2["app-developer"]
    MAIN --> W3["qa-engineer"]
    MAIN --> W4["ux-critic"]
    MAIN --> W5["adversarial-reviewer"]
    W1 -.-|"workers never dispatch other agents"| W2
```

## 4. UI/UX loop

```mermaid
flowchart TD
    SME["Domain SME, Phase 0"] -->|"ux-brief.yaml"| UX["ui-ux-analyst, Phase 1: skill stack databricks-app-design, ui-ux-pro-max, dataviz"]
    UX -->|"ui-design-spec.yaml, wireframes, component contract"| APP["app-developer: records run_command and health_url"]
    APP --> QA["qa_gate"]
    QA --> CR["ux-critic: start app locally, drive each screen, screenshot every viewport (attempt k of 3)"]
    CR --> V{"critic status?"}
    V -->|"BLOCKED: app will not start"| ESC1(["escalate: deploy first or skip gate"])
    V -->|"PASS or FAIL"| HR{"attempt 1 and human review enabled?"}
    HR -->|"yes"| HUM["print app link + ux-feedback.md, wait up to 5 min"]
    HUM -->|"comments saved"| HF["human findings, top priority"]
    HUM -->|"no response"| ROUTE
    HF --> ROUTE
    HR -->|"no"| ROUTE{"open blocker or major findings?"}
    ROUTE -->|"none"| DEP(["design approved: continue to deploy"])
    ROUTE ==>|"spec problem"| UX2["ui-ux-analyst fixes spec"]
    UX2 ==> APP2["app-developer rebuilds affected screens"]
    ROUTE ==>|"code problem"| APP2
    APP2 ==>|"merge, re-run QA, critic attempt k+1"| QA
    ROUTE -.->|"same finding IDs twice, or 3 attempts"| ESC2(["escalate to human"])
```

## 5. `/improve-ux` (existing app)

```mermaid
flowchart TD
    DIR(["direction text or file"]) --> SC["ux-scoper: snapshot app, derive ux-brief if missing, tag ux-focus/slug, write scoped config"]
    SC --> ST["/start-team (incremental, focus: ux)"]
    ST --> P0["Phase 0: ux-critic in audit mode on the app as it is today"]
    P0 --> HT{"phase boundary: you review findings and add comments to ux-feedback.md"}
    HT --> P1["Phase 1: ui-ux-analyst updates design spec from audit + direction"]
    P1 --> P2["Phase 2: app-developer rebuilds affected pages, then qa-engineer"]
    P2 --> GATE["ux-critic gate + fix loop (section 4)"]
    GATE ==>|"FAIL: fix and re-check, up to 3 attempts"| P2
    GATE -->|"PASS: design approved"| DEP{"no-deploy flag?"}
    DEP -->|"no"| D["Phase 3: deploy-engineer"]
    D --> V["Phase 4: qa-engineer runs journeys on deployed app (section 6 on failure)"]
    V --> END1(["done"])
    DEP -->|"yes"| END2(["done: local build, rollback tag available"])
```

## 6. Journey failure handling (fix and validate before redeploy)

```mermaid
flowchart TD
    F["Deployed-app journey FAIL or PARTIAL"] --> FIX["owning agent fixes, scoped to failing journeys"]
    FIX --> M["merge worktrees"]
    M --> L["start app locally; qa-engineer runs ALL journeys (mode: local)"]
    L --> NV{"any NOT_LOCALLY_VERIFIABLE?"}
    NV -->|"yes"| ASK["escalate: user approves resource-only or full redeploy"]
    NV -->|"no"| LP{"all journeys PASS locally?"}
    LP ==>|"no: iterate"| FIX
    LP -->|"yes"| FE{"frontend changed and UX gate present?"}
    FE -->|"yes"| CR["ux-critic regression attempt"]
    CR ==>|"FAIL: iterate"| FIX
    CR -->|"PASS"| RD["deploy-engineer redeploys"]
    FE -->|"no"| RD
    ASK --> RD
    RD --> CONF["one deployed-app journey pass, all journeys"]
    CONF ==>|"FAIL: iterate"| FIX
    CONF -->|"PASS"| DONE(["Phase 4 passes"])
```

## 7. Agents and models

| Agent | Model | Phase | Description |
|---|---|---|---|
| `pm-orchestrator` (skill) | main session (Opus recommended) | all | Runs in the main session. Dispatches workers, merges worktrees, runs the QA, UX and adversarial gates, checkpoints progress, escalates blockers. |
| Domain SME (generated) | haiku | 0 | Researches the domain; writes `domain-playbook.md`, `data-requirements.yaml`, `success-criteria.yaml`, and `ux-brief.yaml` for app teams. |
| `data-discovery` | haiku | 0 | Profiles source data: schemas, samples, distributions, quality flags (`data-profile.yaml`, data dictionary). |
| `data-engineer` | haiku | 1 | Builds ingestion and transformation pipelines (Spark Declarative Pipelines, Unity Catalog, Auto Loader). |
| `data-scientist` | haiku | 1-2 | Trains, registers and serves ML models with MLflow and Model Serving. |
| `genai-architect` | opus | 1-2 | Designs RAG, Vector Search, embedding, prompt and model-selection architecture. |
| `ui-ux-analyst` | sonnet | 1 | Designs workflows, wireframes, the component contract and the design spec, using the installed UI skills. |
| `app-developer` | sonnet | 2-3 | Builds the FastAPI backend and React/TypeScript frontend for Databricks Apps. |
| `qa-engineer` | sonnet | every phase | Progressive QA checks; in the final phase drives user journeys against the app. |
| `ux-critic` | sonnet | build phase (gate) | Starts the app locally, drives each screen, and judges the rendered UI against the brief and design spec; also audits existing apps for `/improve-ux`. |
| `deploy-engineer` | haiku | final | Finalizes the Databricks Asset Bundle config and deploys. |
| `adversarial-reviewer` | opus | final (gate) | Independent, read-only red team that tries to falsify the build from the spec, contracts and artifacts. |

Model values are the `model:` line in each agent's definition (`agents/*.md`, mirrored in `templates/core/*.yaml`). Change a line there to re-tier an agent.
