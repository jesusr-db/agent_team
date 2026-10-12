# agent-team Workflow

Diagrams render on GitHub (Mermaid). They describe the plugin as it exists on this branch, including the UI/UX loop (section 4).

## 1. End-to-end flow

```mermaid
flowchart TD
    PRD([PRD]) --> CT["/create-team<br/>team-builder + phase-planner"]
    CT --> CFG[".agent-team/<br/>team-manifest, agents, contracts, phases,<br/>user-journeys.yaml"]
    CFG --> ST["/start-team<br/>loads pm-orchestrator skill<br/>in the MAIN session"]
    ST --> LOOP

    subgraph LOOP["Per-phase loop (orchestrator at tree root)"]
        direction TB
        S1[read_phase_config] --> S2[resolve_contracts]
        S2 --> S3["dispatch_agents<br/>worktree-isolated, parallel groups"]
        S3 --> S4[await_agents]
        S4 --> S5{status?}
        S5 -- "NEEDS_CONTEXT / BLOCKED" --> S3
        S5 -- "DONE" --> S6[merge_worktrees]
        S6 --> S7["qa_gate<br/>qa-engineer"]
        S7 -- "fail (max 3)" --> S3
        S7 -- pass --> G{"gates: includes<br/>adversarial-reviewer?"}
        G -- yes --> S75["Step 7.5<br/>adversarial-reviewer"]
        S75 -- "findings (shared attempt cap)" --> S3
        S75 -- pass --> CP
        G -- no --> CP[checkpoint + introspection]
    end

    CP --> HT{{"Human touchpoint<br/>confirm next phase"}}
    HT --> LOOP
    HT --> DONE([All phases complete])

    ADD["/add-feature<br/>feature-scoper"] -.-> CFG
```

## 2. Phase structure

```mermaid
flowchart LR
    P0["Phase 0<br/>data-discovery<br/>domain SME"] --> P1["Phase 1<br/>data-engineer<br/>data-scientist<br/>genai-architect<br/>ui-ux-analyst"]
    P1 --> P2["Phase 2<br/>app-developer<br/>consumers of data outputs"]
    P2 --> P3[Phase 3<br/>integration]
    P3 --> P4["Phase 4 (final)<br/>deploy-engineer<br/>qa-engineer + journeys<br/>gate: adversarial-reviewer"]
```

## 3. Orchestration constraint

The harness supports one level of subagent fan-out. The orchestrator therefore runs as a skill in the main session, and workers never spawn workers.

```mermaid
flowchart TD
    MAIN["Main session<br/>pm-orchestrator (skill)"] --> W1[data-engineer]
    MAIN --> W2[app-developer]
    MAIN --> W3[qa-engineer]
    MAIN --> W4[adversarial-reviewer]
    W1 -. "no further dispatch" .-x X[ ]
    style X fill:none,stroke:none
```

## 4. UI/UX loop

```mermaid
flowchart TD
    SME["Domain SME (Phase 0)"] -->|ux-brief.yaml| UX["ui-ux-analyst (Phase 1)<br/>skill stack: databricks-app-design,<br/>ui-ux-pro-max, dataviz"]
    UX -->|"ui-design-spec.yaml<br/>wireframes, component contract"| APP["app-developer<br/>records run_command + health_url"]
    APP --> QA[qa_gate]
    QA --> CR["ux-critic<br/>start app locally, drive each screen,<br/>screenshot every viewport"]
    CR --> V{status}
    V -- BLOCKED --> ESC1["escalate: deploy first<br/>or skip gate"]
    V -- "PASS or FAIL" --> HR{"attempt 1 and<br/>ux_review.human != off?"}
    HR -- "yes" --> HUM["print app link + ux-feedback.md<br/>wait up to 5 min (async)"]
    HUM -- "comments saved" --> HF["human findings<br/>(top priority)"]
    HUM -- "no response" --> ROUTE
    HF --> ROUTE
    HR -- no --> ROUTE{"open blocker/major findings?"}
    ROUTE -- none --> DEP[deploy]
    ROUTE -- "owner: ui-ux-analyst" --> UX2["ui-ux-analyst fixes spec"] --> APP2
    ROUTE -- "owner: app-developer" --> APP2["app-developer fixes<br/>scoped finding IDs"]
    APP2 --> QA
    ROUTE -. "same IDs twice or 3 attempts" .-> ESC2["escalate to human"]
```

Every box is a one-level subagent dispatched by the orchestrator in the main session; the loop is orchestrator-driven, not nested.

## 5. `/improve-ux` (existing app)

```mermaid
flowchart TD
    DIR(["direction text or file"]) --> SC["ux-scoper<br/>snapshot app, derive ux-brief if missing,<br/>tag ux-focus/slug, write scoped .agent-team/"]
    SC --> ST["/start-team (mode: incremental, focus: ux)"]
    ST --> P0["Phase 0: ux-critic in audit mode<br/>on the app as it is today"]
    P0 --> HT{{"phase boundary:<br/>you review findings,<br/>add comments to ux-feedback.md"}}
    HT --> P1["Phase 1: ui-ux-analyst<br/>updates design spec from audit + direction"]
    P1 --> P2["Phase 2: app-developer<br/>rebuilds affected pages only"]
    P2 --> QA[qa-engineer]
    QA --> GATE["ux-critic gate + fix loop<br/>(section 4)<br/>design approved by you or the critic"]
    GATE --> DEP{"--no-deploy?"}
    DEP -- no --> D["Phase 3: deploy-engineer"]
    D --> V["Phase 4: qa-engineer<br/>journeys on deployed app"]
    V --> END([done])
    DEP -- yes --> END2([done: local build, rollback tag available])
```
