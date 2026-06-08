# Journey Test Results — Template

File at: `docs/journey-test-results-<YYYY-MM-DD>.md` (or `docs/qa/<YYYY-MM-DD>-<branch>.md`)

```markdown
# Journey Test Results — <YYYY-MM-DD>

> **Branch:** `<branch-name>`
> **App URL:** <url>
> **Tester:** <human or "Playwright-driven via test-deployed-app skill">
> **Path:** A (chrome-devtools MCP) | B (Playwright + CDP)
> **Chrome:** <version from /json/version>

## Setup

- Preconditions verified: ✓ debug profile, ✓ CDP port 9222, ✓ Playwright 1.58+
- Backend log monitor armed with filter: `<the grep regex used>`
- App health pre-check: <`databricks apps get`, endpoint status, etc.>

## Per-journey results

### J1 — <one-line description>

**Store / resource:** <id>
**Prompt:** `<verbatim>`
**Send timestamp:** `<unix_ts (UTC HH:MM:SS)>`

**Network transcript:**
| Time (UTC) | Δ | Event | Status |
|---|---|---|---|
| HH:MM:SS.sss | — | `/api/chat` received | — |
| HH:MM:SS.sss | +N.Ns | LLM call 1 (`POST /serving-endpoints/chat/completions`) | 200 |
| HH:MM:SS.sss | +N.Ns | Tool `<name>` (`POST /api/tool/<name>`) | 200 |
| HH:MM:SS.sss | +N.Ns | LLM call 2 | 200 |
| HH:MM:SS.sss | +N.Ns | `/api/chat` closed | 200 |

**Final assistant text:**
> <paste verbatim — the LLM's words matter>

**Wallclock latency:** N.Ns

**Screenshot:** `/tmp/j1_final.png`

**Verdict:** ✅ PASS / 🟡 PARTIAL / 🔴 FAIL

**Observations:**
- <anything that made you pause — UI glitch, slow load, surprising wording>

### J2 — ... (repeat per journey)

## Roll-up

| Journey | Verdict | Latency | Notes |
|---|---|---|---|
| J1 | ✅ PASS | N.Ns | <one line> |
| J2 | ✅ PASS | N.Ns | <one line> |
| J3 | 🔴 FAIL | N.Ns | <one line> |
| J4 | ✅ PASS | N.Ns | <one line> |

**Total:** X PASS, Y PARTIAL, Z FAIL.

## New findings

### 🔴 Finding 1 — <short title>

**Severity:** demo-blocker | intermittent | cosmetic

**Failure mode:** <what happens>

**Reproduction:**
1. <step>
2. <step>

**Backend evidence:**
```
<actual log line excerpt>
```

**Recommended fix paths:**
1. <option 1>
2. <option 2>

**Memory observation:** `<observation_id>` saved as `<memory_file>.md`

### 🟡 Finding 2 — ... (repeat per new finding)

## Recommendations

- [ ] <actionable item>
- [ ] <actionable item>

## What was NOT tested

- <journey or path you skipped, and why>
```

## How to fill it in

- **Verbatim** matters: paste the assistant's final text, paste log lines as-is. Paraphrasing loses signal.
- **Tie UI to logs**: every UI-level verdict should have a matching network row. A PASS where you can't find the LLM calls in logs is a setup problem.
- **Findings ≠ failures**: a passing journey can still surface findings ("J2 passed but tool ordering was unexpected — 3 calls in parallel instead of sequential per spec").
- **Memory observations** are the durable artifact. The results doc is for the PR/handoff; the memory entries are what the next session reads.
