# Deriving Journeys from Project Notes

The quality of a browser-test pass is set by the journey list, not the driver. A good journey is **specific** (exact prompt, exact store/account, expected tools), **falsifiable** (success criteria a human or grep can check), and **high-yield** (it exercises a recently-changed code path or a known-risky resource).

## Checklist — what to look for

### Authoritative test plans
- `docs/handoff*.md` — handoff docs often have a "how to verify" section
- `docs/journey*.md`, `docs/testing*.md`, `docs/e2e*.md` — explicit test specs
- `docs/ROADMAP.md` or `docs/QA.md` — sometimes lists "must-test before ship"
- `tests/e2e/`, `tests/integration/` — even unit tests can suggest journey shapes

### Canonical inputs
- Project `CLAUDE.md` — store IDs, account IDs, demo personas, problematic resources
- User-global `~/.claude/CLAUDE.md` or `MEMORY.md` — cross-project conventions
- `.env.example`, `app.yaml` — env vars indicate what's configurable
- Synthetic-data scripts (`data/init_assets.py` etc.) — what test data exists

### App surface
- Frontend `App.tsx` / `main.py` / router config — list of routes / pages
- Sidebar / nav / quick-action buttons — visible affordances to a real user
- Chat input placeholders — hint at the canonical prompt style

### Risk surface
- Tool/skill catalog — multi-tool prompts that chain calls
- Risk tiers (e.g., orange/red, requires_confirmation: true) — confirmation-flow journeys
- Permission/auth reason codes — negative-path journeys (forbidden inputs)
- Known-buggy fixtures noted in CLAUDE.md or memory — high-yield "stress" journeys
- Recently merged commits — anything new is more likely broken

## A good journey has

- **Name** — short id (`J1`, `J2`, ...) for filenames and log correlation
- **Resource selector** — store, account, dataset etc. that the journey acts on
- **Verbatim prompt** — exact text to send (no paraphrasing — the LLM is sensitive)
- **Expected tool/path** — what backend calls should fire (so absence is a signal)
- **Success criteria** — falsifiable: "final message contains a numeric score", "elapsed ≤15s", "Confirm card appeared before tool ran"
- **Failure-risk note** — what this journey is specifically testing (regression of fix X, sensitive to guardrail Y, slow because of Z)

Example, well-formed:

```
### J3 — Confirmation flow on store 42
- Store: 42
- Prompt: "Run an end-of-day extract for my store."
- Expected agent loop: LLM call 1 → tool_calls: [run_eod_extract] → backend returns risk_tier orange + confirmation payload → UI shows Confirm card → user clicks → POST /api/confirm → tool executes → LLM call 2 → final message
- Success: Confirm card appears BEFORE tool runs; after click, log shows auth.decision path=/api/confirm decision=allow
- Failure risk: confirmation gate regression — if the tool runs without a card, governance is broken
```

Example, badly-formed:

```
### Test confirmation
- Send something that needs confirmation
- It should work
```

The bad version isn't falsifiable. You can't tell from logs or UI whether it passed.

## Coverage — 3 to 5 journeys is the sweet spot

| Journey type | Why include |
|---|---|
| **Happy single-action** | Smoke test for the most-demoed path |
| **Multi-step / multi-tool** | Tests agent-loop message shape, tool-result handling |
| **High-risk confirmation flow** | Governance regression detector |
| **Known-bad data or fixed-bug regression** | High signal-to-noise for catching regressions |
| **Negative auth / forbidden input** | Tests that denials are clean (no 500s) |

Beyond 5, you're paying setup tax without adding signal. Better to run 4 journeys deeply (capture network, screenshots, error bodies) than 15 shallowly.

## Don't journey-test these

- Things a backend integration test already covers cheaply (`pytest` is faster)
- Static content / docs pages (no behavior to exercise)
- Things the human-facing UI doesn't surface (use API or unit tests)
- "Does the app load?" — that's a `curl /healthz`, not a journey
