---
name: app-validation-loop
description: "Drive an already-deployed, OAuth-authenticated web app through user journeys in a real browser, capturing UI + backend-log evidence per journey. Used by the agent-team QA engineer in Phase 4: reads structured journeys from .agent-team/artifacts/user-journeys.yaml when present, otherwise derives them from project notes. Two paths — Playwright + CDP (works in any session) and chrome-devtools MCP (needs restart). Use to validate a deployed build against the PRD's user journeys, smoke-test the UI, or verify a deployed change end-to-end."
---

# App Validation Loop

Drive an already-deployed, OAuth-walled web app from Claude Code. Optimized for Databricks Apps (`*.databricksapps.com`) on this Mac but works for any app whose auth lives in the user's regular Chrome Default profile.

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

## Triggers

Invoke when the user says any of:
- "browser test", "drive the app", "run the user journey", "test the deployed app"
- "click through J1/J2/...", "smoke test the UI"
- "verify the deployed change in a real browser"
- Anything that requires interacting with a live, authenticated UI rather than curling an API

**Don't use for:** local dev servers (use `web-devloop-tester` agent), unauthenticated public pages (`WebFetch` is enough), or API-only verification (use `curl` / SDK).

## Two paths — pick by session state

| Path | Works without Claude restart? | Auth | When to pick |
|---|---|---|---|
| **A. chrome-devtools MCP** | ❌ no — MCP servers only load at session start | Real Chrome Default profile | Cleaner tool calls if you're already in a session that loaded the MCP |
| **B. Playwright + CDP** | ✅ yes | Side debug profile (`~/.chrome-debug-profile`) seeded from Default | Drop-in for any session, including this one |

**Default to Path B.** Path A is described last for completeness.

## Preconditions (Path B)

Verify in this order, fail fast:

```bash
# 1. Debug profile has auth cookies (set up once per Mac, see "First-time setup" below)
ls ~/.chrome-debug-profile/Default/Cookies ~/.chrome-debug-profile/Default/Login\ Data 2>&1

# 2. Chrome with CDP is running on 9222 (port + authenticated tab)
curl -sm 3 http://127.0.0.1:9222/json/version | grep Browser    # expect Chrome/148+
curl -sm 3 http://127.0.0.1:9222/json | python3 -c "import json,sys; [print(p['url']) for p in json.load(sys.stdin) if p.get('type')=='page']"

# 3. Playwright installed (in the user's pyenv intakeApp env, version 1.58+)
python3 -c "from importlib.metadata import version; print(version('playwright'))"
```

If (2) shows no listening port: Chrome isn't running with CDP. Run the launch command in "Launch Chrome with CDP" below.

If (1) shows missing files: do "First-time setup" first.

## First-time setup (per Mac, one-time)

Seed `~/.chrome-debug-profile/` from the user's real Default profile. **Chrome must be fully quit during this step** (file lock).

```bash
pkill -f "Google Chrome.app/Contents/MacOS/Google Chrome"; sleep 2
DEST="$HOME/.chrome-debug-profile"
SRC="$HOME/Library/Application Support/Google/Chrome"
mkdir -p "$DEST/Default"
cp "$SRC/Local State" "$DEST/Local State"
cd "$SRC/Default" && rsync -a \
  "Cookies" "Cookies-journal" "Login Data" "Login Data-journal" \
  "Preferences" "Secure Preferences" "Web Data" "Web Data-journal" \
  "Local Storage/" "Session Storage/" "IndexedDB/" \
  "$DEST/Default/"
```

Why this side profile instead of using the real Default directly: Chrome 136+ silently disables `--remote-debugging-port` if `--user-data-dir` points at the real Default profile (security mitigation). The side profile is a copy that carries auth cookies but isn't locked out.

## Launch Chrome with CDP

```bash
# Quit any Chrome first — the debug profile must not be in use elsewhere
pkill -f "Google Chrome.app/Contents/MacOS/Google Chrome"; sleep 2
open -na "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-debug-profile" \
  --profile-directory=Default \
  --no-first-run --no-default-browser-check \
  "$APP_URL"
sleep 4
curl -sm 3 http://127.0.0.1:9222/json/version    # confirm CDP is up
```

`$APP_URL` is the deployed app URL (e.g. `https://crustopher-ui-7405605519549535.15.azure.databricksapps.com`).

After this, you can issue many drive-the-app scripts against the same Chrome from the same Claude session — Playwright connects each time and disconnects without killing Chrome.

## Drive via Playwright

**Use `scripts/drive_journeys.py` as the template.** It:
- Connects to the running Chrome via CDP at `127.0.0.1:9222`
- Takes a list of journeys (store, prompt, optional confirm step)
- Streams responses with a settle-based polling pattern
- Captures screenshots, network status, and a final-text excerpt per journey
- Disconnects cleanly without killing Chrome

Minimal inline pattern when you don't want a full script:

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
        ctx = browser.contexts[0]
        page = next((pg for pg in ctx.pages if "yourapp" in pg.url), ctx.pages[0])
        # ... your interactions ...
        await page.screenshot(path="/tmp/state.png")
        await browser.close()   # closes the Playwright connection only, NOT Chrome

asyncio.run(main())
```

Keep the whole journey in ONE `asyncio.run` — Playwright cold start is 3-5s per `python3` invocation, so doing 10 clicks across 10 invocations costs 30-50s of nothing.

## Wait-for-streaming-response pattern

Agent apps stream tokens. Don't `wait_for_selector` on a static "done" element — there usually isn't one. Use settle polling:

```python
prior = await page.evaluate("() => document.body.innerText.length")
last = prior
stable = 0
deadline = time.monotonic() + 60   # max wait
while time.monotonic() < deadline:
    await page.wait_for_timeout(500)
    cur = await page.evaluate("() => document.body.innerText.length")
    if cur > last + 10:
        last = cur; stable = 0
    elif last > prior + 100:
        stable += 1
        if stable >= 6:     # ~3s of no growth after meaningful growth
            break
```

**Tune `stable >= 6` upward** if the sidebar refreshes during the chat and the heuristic exits too early — the sidebar updating mid-stream can cause a false-positive "settled" reading. Sign of this: elapsed_s under 5 but the screenshot shows a thinking indicator.

## Six gotchas the documented-by-pain version of this taught us

1. **Don't loop sub-second actions across multiple `python3` invocations.** Each cold start is 3-5s. Put the whole journey in one async script.

2. **Chrome's debug port dies if Chrome quits.** If the human closes the Chrome window between actions, relaunch from "Launch Chrome with CDP."

3. **Don't assume the store/nav picker is a `<select>`.** It might be a hidden `<select>` (older Crustopher UI used this), OR a set of `<div role="button">` cards followed by a "Continue" commit button (current Crustopher UI uses this — landing page only; switching mid-session uses an in-chat dropdown). **Always inspect first** with a quick probe before scripting:
   ```python
   info = await page.evaluate("""
     () => ({
       selects: Array.from(document.querySelectorAll('select')).map(s => ({options: Array.from(s.options).map(o => ({value: o.value, text: o.text.trim()}))})),
       buttons: Array.from(document.querySelectorAll('[role=button]')).slice(0, 10).map(b => b.innerText.trim().slice(0, 80))
     })
   """)
   ```
   The simplest portable fix when the UI has card+Continue landing: reload to landing between journeys and re-pick. Slower (~3-5s extra per journey) but works without writing a separate in-chat-switcher path:
   ```python
   await page.goto(APP_URL, wait_until="networkidle")
   await page.get_by_role("button", name=re.compile(rf"Store #{sid}\b")).first.click()
   await page.get_by_role("button", name=re.compile(rf"Continue as.*#{sid}\b")).first.click()
   ```

4. **The string "I'm having trouble connecting to my AI system right now" is NOT always a cold-start race.** This is the Crustopher agent's generic OpenAI-exception fallback. Real causes include:
   - Cold-start race (warmup) — solved by resending
   - **Upstream `input_guardrail_triggered` 400** (e.g. `violent-crimes: true` false-positive on legitimate prompts like "Run an end-of-day extract for my store.")
   - **Upstream `output_guardrail_triggered` 400** (e.g. `pii_detection: true` matching a synthetic ID against `US_BANK_NUMBER`)
   
   Always check `databricks apps logs <app-name>` for a 400 BAD_REQUEST before retrying. If you see `finishReason: "*_guardrail_triggered"`, no amount of retrying will help — it's a content-classifier false-positive at the upstream FMAPI router.

5. **Right-sidebar widget data ≠ tool-call data.** In agent apps the sidebar Store Health (or similar) widget is computed independently from the same-named tool call, and the numbers can disagree for the same store in the same minute. Don't cross-validate by comparing them.

6. **Auth lives in the Default profile on this Mac, not Profile 1 / Profile 2.** Confirm with `ls "$HOME/Library/Application Support/Google/Chrome/Default/Cookies"`. If you ever re-seed `~/.chrome-debug-profile/`, source from Default, not Profile N.

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
   verbatim prompt/action, reproduction steps (for PARTIAL/FAIL), and the `maps_to` criterion.
   (In agent-team mode this path takes precedence over the `docs/journey-test-results-<YYYY-MM-DD>.md` path mentioned in "Synthesizing findings" below, which is for standalone runs.)

**Only fall back to "Deriving journeys from project notes" (below) when
`.agent-team/artifacts/user-journeys.yaml` is absent.**

This skill never edits source code. If journeys fail, report them — the PM
orchestrator dispatches a fix agent and re-runs the suite.

## Deriving journeys from project notes

Before driving anything, scan the project for an existing test plan. **A bad journey list catches no bugs; a good one catches the next demo failure.** Look for:

| Source | What you're looking for |
|---|---|
| `docs/handoff*.md`, `docs/journey*.md`, `docs/testing*.md` | Explicit user-journey specs (Crustopher had `docs/handoff-user-journey-testing.md` with 4 ready-made J1-J4 definitions) |
| `CLAUDE.md` (project + user-global) | Canonical inputs: store/account IDs, problematic test data, auth boundaries, demo personas |
| App entry points (sidebar / "quick actions" / nav) | Each visible action = a journey candidate |
| Permission/auth-reason enums | Negative-path journeys (forbidden inputs, expired sessions) |
| Tool/skill catalog | Multi-tool reasoning prompts that exercise tool-chaining |
| Known-buggy resources noted in `CLAUDE.md` or memory | High-yield "stress" journeys — Crustopher's store 217 was flagged "problematic" and J4 there surfaced the PII guardrail bug |
| Risk-tiered actions (orange/red) | Confirmation-flow journeys — Crustopher's `run_eod_extract` |

If no explicit plan exists, derive 3-5 journeys covering:

1. **Happy single-action** — simplest path through the most common quick-action
2. **Multi-step / multi-tool** — exercises the agent loop, tool-result message shape
3. **High-risk confirmation flow** — if the app has gated actions
4. **Known-bad input or known-bad data** — fixed bug regression OR a resource flagged as problematic
5. **Negative auth** — input the user isn't authorized for (expect a clean deny, not a 500)

Read `references/journey-definition.md` for a fuller checklist.

## Dual-channel testing: UI + backend logs

A UI-only test catches "did it render?" and misses "did the wrapper return a 400 that the UI masked as a friendly error?" Pair Playwright drive with a **persistent log monitor** so every journey has both UI evidence and server-side proof.

### Step 1 — Arm a filtered log stream

Use the `Monitor` tool (persistent, not bounded), so each interesting log line becomes a notification:

```bash
databricks apps logs <app-name> --tail-lines 0 --follow --profile DEFAULT 2>&1 | \
  grep --line-buffered -E "$FILTER_REGEX"
```

**Baseline FILTER_REGEX for any agent-app**:
```
/api/chat|serving-endpoints/chat/completions|/api/tool/|/api/confirm|auth\.decision|BAD_REQUEST|guardrail|tool_use ids| 4[0-9]{2} | 5[0-9]{2} |ERROR|Traceback
```

Augment with project-specific patterns surfaced in the app's `CLAUDE.md` or in the journey `failure_risk` fields (e.g. auth reason codes for denial-path journeys). Example — a project whose CLAUDE.md lists canonical auth reason codes:
```
|reason=(authorized|token-absent|user-unresolvable|store-not-authorized|local-dev-bypass)
```

### Step 2 — Capture send timestamps from Playwright

The driver template records `send_unix_ts` per journey. Use it to find the matching server-side window:

```python
t_send = time.time()
await send_prompt(page, journey["prompt"])
# t_send is your anchor for log correlation
```

### Step 3 — Correlate after each journey

The log monitor's events stream into the conversation as they arrive. After each journey:

1. Find the auth.decision line at or after `send_unix_ts` for that store
2. Walk forward: LLM call 1 status → tool call(s) status → LLM call 2 status → `/api/chat` close
3. If any 4xx/5xx, pull the full body with: `databricks apps logs <app> --tail-lines 500 | grep -B1 -A30 "<HH:MM:SS>"`
4. **A "successful" 200 on `/api/chat` does NOT mean success.** The Crustopher pattern catches OpenAI exceptions and returns 200 with an in-message error string. Always cross-reference: if logs show `BAD_REQUEST` or `guardrail_triggered` at the same second, the UI's 200 is masking a backend failure.

### Step 4 — What to capture per journey

| Field | Source |
|---|---|
| User prompt (verbatim) | journey spec |
| Send timestamp (unix) | Playwright driver |
| HTTP transcript (LLM/tool/confirm + status + timing) | log monitor stream |
| Final assistant text | Playwright `capture_assistant_text` + screenshot |
| Wallclock latency | Playwright driver `elapsed_s` |
| Screenshot | Playwright `page.screenshot()` |
| Verdict | PASS / PARTIAL / FAIL with one-line reason |
| Backend error body (if any) | `databricks apps logs --tail-lines 500 | grep -B1 -A30 "HH:MM:SS"` |
| Surprises | anything that made you pause — friendly errors masking 4xx, unexpected tool ordering, slow paths |

## Cross-correlating UI failures with backend errors

The single most useful pattern from real-world testing: **the UI's friendly "trouble connecting" message is almost always hiding a specific backend 400.** Always pull the backend body before retrying.

Worked example from a real session:

| Observation | UI evidence | Backend evidence | What it actually was |
|---|---|---|---|
| Chat fails on store 42 with EOD-extract prompt | "I'm having trouble connecting to my AI system right now" | `httpx POST .../serving-endpoints/chat/completions "HTTP/1.1 400 Bad Request"` + `input_guardrail: [{flagged: true, categories: {violent-crimes: true}}]` + `finishReason: "input_guardrail_triggered"` | Upstream FMAPI input safety guardrail false-positive on "Run an end-of-day extract for my store" — NOT a connection issue at all |
| Chat fails on store 217 with drivers prompt | Same "trouble connecting" message | Same `400 Bad Request` but with `output_guardrail`, `pii_detection: true`, `anonymized_input: [...Order <US_BANK_NUMBER>...]`, `finishReason: "output_guardrail_triggered"` | Output PII detector matched a synthetic order ID against the US_BANK_NUMBER regex |

Two distinct failure modes, identical UI surface. UI testing alone would have called both "cold-start race, retry." The backend logs revealed they're product-shipping bugs.

## Synthesizing findings

After driving all journeys, write a results doc at `docs/journey-test-results-<YYYY-MM-DD>.md`. See `references/findings-template.md` for the structure. Required sections:

1. **Setup** — what branch, what path (A or B), Chrome version, when
2. **Per-journey results** — prompt, transcript, final text, latency, verdict, observations
3. **Roll-up** — PASS/PARTIAL/FAIL counts, total elapsed
4. **New findings** — bugs surfaced that aren't in the existing tech-debt list. For each: failure mode, reproduction conditions, severity (demo-blocker / intermittent / cosmetic), recommended fix paths
5. **Memory observations** — for each new finding, save a project memory entry so future sessions don't rediscover it

If a journey fails, also add the failure to the project's `gotchas.md` (or equivalent) so the next person doesn't trip on it cold.

## Path A — chrome-devtools MCP (alternative, requires restart)

User-scope config in `~/.claude.json`:

```json
"chrome-devtools": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "chrome-devtools-mcp@latest",
    "--userDataDir=/Users/jesus.rodriguez/Library/Application Support/Google/Chrome",
    "--isolated=false",
    "--chromeArg=--profile-directory=Default"
  ],
  "env": { "I_DANGEROUSLY_OPT_IN_TO_UNSUPPORTED_ALPHA_TOOLS": "true" }
}
```

Two non-obvious bits:
- `--isolated=false` — use the real profile, not a temp dir
- `--chromeArg=--profile-directory=Default` — the MCP has no native flag for this, must pass through

The MCP also accepts `--browserUrl http://127.0.0.1:9222` to attach to an *already running* Chrome — useful for sharing with Path B sessions.

Once loaded, use `mcp__chrome-devtools__navigate_page`, `_click`, `_fill`, `_take_screenshot`, `_list_console_messages`, `_list_network_requests`, etc. **Restart Claude Code after editing `~/.claude.json`** — MCP servers only load at session start.

## When the skill itself isn't enough

If you keep landing on a login page even after seeding the debug profile, the SSO session in the Default profile expired. Have the user open regular Chrome with the Default profile, visit the app, complete SSO, then re-seed `~/.chrome-debug-profile/` (steps in "First-time setup").
