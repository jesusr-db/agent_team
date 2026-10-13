#!/usr/bin/env python3
"""Generate the agent-team sequence diagrams (diagram-design skill, default skin).

    python3 docs/diagrams/build_sequence_diagrams.py [OUT_DIR]

Writes one self-contained HTML file per diagram. Enforces the skill's sequence budget
(<=5 lifelines, <=12 messages, <=2 single-region loop fragments, labels <=14 chars).
Geometry sits on the 4px grid; arrows are drawn before actor boxes.
"""
import os
import sys
from xml.sax.saxutils import escape

PAPER, INK, MUTED, SOFT = "#f5f5f5", "#2d3142", "#4f5d75", "#5a6580"
ACCENT, LINK = "#bf4520", "#2e5aa8"
SANS, MONO = "'Geist', sans-serif", "'Geist Mono', monospace"
W = 1040
STEP = 36          # vertical distance between messages
MAX_LABEL = 14

# ---------------------------------------------------------------- diagrams
# actor: (name, sublabel, tag, style)   style: focal | backend | input
# item:  ("msg", src, dst, label, kind) kind: call | return | async | headline
#        ("loop", first_lifeline, last_lifeline, guard) ... ("end",)
#        ("band", label)   phase band starting at the next item
ORCH = ("Orchestrator", "main session skill", "ORCH", "focal")
HUMAN = ("You", "approve / comment", "HUMAN", "input")

DIAGRAMS = [
    dict(
        slug="seq-phases", eyebrow="Sequence · Phase flow",
        title="Phases, agents and gates",
        desc="The orchestrator runs Phase 0 discovery and SME, pauses for human confirmation, loops builders and gates in phases one to three until the gates pass, then deploys and runs final journeys and the red team in phase four.",
        actors=[HUMAN, ORCH,
                ("Discovery + SME", "haiku", "PHASE 0", "backend"),
                ("Builders", "haiku · sonnet · opus", "AGENTS", "backend"),
                ("Gates", "qa · ux-critic · red team", "GATES", "backend")],
        items=[
            ("band", "PHASE 0"),
            ("msg", 1, 2, "DISPATCH", "call"),
            ("msg", 2, 1, "BRIEF + DATA", "return"),
            ("msg", 1, 0, "PHASE DONE", "async"),
            ("msg", 0, 1, "CONFIRM", "return"),
            ("band", "PHASES 1-3"),
            ("loop", 1, 4, "[gate FAIL: fix, attempt n of 3]"),
            ("msg", 1, 3, "DISPATCH", "call"),
            ("msg", 3, 1, "STATUS", "return"),
            ("msg", 1, 4, "QA + UX GATE", "call"),
            ("msg", 4, 1, "FINDINGS", "return"),
            ("end",),
            ("band", "PHASE 4"),
            ("msg", 1, 3, "DEPLOY", "call"),
            ("msg", 3, 1, "APP URL", "return"),
            ("msg", 1, 4, "JOURNEYS+RED", "call"),
            ("msg", 4, 1, "PASS", "headline"),
        ],
        notes=[("BRIEF + DATA", "domain playbook, ux-brief and data profile"),
               ("QA + UX GATE", "qa-engineer, then ux-critic where the team has a UI"),
               ("JOURNEYS+RED", "user journeys on the deployed app, then the adversarial review")],
    ),
    dict(
        slug="seq-qa-loop", eyebrow="Sequence · Iteration",
        title="Phase execution and the QA fix loop",
        desc="The orchestrator dispatches builders, then QA. On a QA failure it loops: dispatch fix agents scoped to the failures and re-run QA, up to three attempts, escalating to the human after the third failure. After QA passes the adversarial reviewer runs.",
        actors=[HUMAN, ORCH,
                ("Builders", "worktree-isolated", "AGENTS", "backend"),
                ("qa-engineer", "sonnet", "GATE", "backend"),
                ("Red team", "opus · read-only", "GATE", "backend")],
        items=[
            ("msg", 1, 2, "DISPATCH", "call"),
            ("msg", 2, 1, "STATUS", "return"),
            ("msg", 1, 3, "QA SCOPE", "call"),
            ("loop", 0, 3, "[QA FAIL: attempt n of 3]"),
            ("msg", 3, 1, "FAIL", "return"),
            ("msg", 1, 2, "FIX IDS", "call"),
            ("msg", 2, 1, "FIXED", "return"),
            ("msg", 1, 3, "RE-RUN QA", "call"),
            ("msg", 1, 0, "3 FAILS", "async"),
            ("end",),
            ("msg", 3, 1, "PASS", "headline"),
            ("msg", 1, 4, "RED TEAM", "call"),
            ("msg", 4, 1, "FINDINGS", "return"),
        ],
        notes=[("FIX IDS", "the owning agent is re-dispatched, scoped to the failing checks only"),
               ("3 FAILS", "after three failed attempts the orchestrator writes escalation.md and asks you"),
               ("RED TEAM", "dispatched only in the final phase, after QA passes")],
    ),
    dict(
        slug="seq-ux-gate", eyebrow="Sequence · Iteration",
        title="UX gate loop with optional human review",
        desc="The UX critic reviews the rendered app. On the first attempt the human can comment for up to five minutes. While blocker or major findings stay open the orchestrator loops: the analyst fixes the spec, the developer rebuilds affected screens, and the critic re-checks, up to three attempts.",
        actors=[HUMAN, ORCH,
                ("ui-ux-analyst", "sonnet", "AGENT", "backend"),
                ("app-developer", "sonnet", "AGENT", "backend"),
                ("ux-critic", "sonnet · rendered app", "GATE", "backend")],
        items=[
            ("msg", 1, 4, "UX GATE", "call"),
            ("msg", 4, 1, "FINDINGS", "return"),
            ("msg", 1, 0, "APP LINK", "async"),
            ("msg", 0, 1, "COMMENTS", "return"),
            ("loop", 1, 4, "[blocker or major open: attempt n of 3]"),
            ("msg", 1, 2, "FIX SPEC", "call"),
            ("msg", 2, 1, "SPEC V2", "return"),
            ("msg", 1, 3, "REBUILD IDS", "call"),
            ("msg", 3, 1, "REBUILT", "return"),
            ("msg", 1, 4, "RE-CHECK", "call"),
            ("end",),
            ("msg", 4, 1, "PASS", "headline"),
        ],
        notes=[("APP LINK", "attempt 1 only: the local app URL and ux-feedback.md; waits up to 5 minutes, then continues without you"),
               ("COMMENTS", "your comments become top-priority findings; no reply means the agent's findings stand"),
               ("FIX SPEC", "only when a finding says the spec itself is wrong; otherwise straight to REBUILD IDS")],
    ),
    dict(
        slug="seq-journey-fix", eyebrow="Sequence · Iteration",
        title="Fix and validate journeys before redeploy",
        desc="When a deployed journey fails, the developer fixes it, then every journey is re-run against the app started locally, plus a UX regression check if the frontend changed. Only when everything passes locally is the app redeployed, followed by one confirming run, with up to three attempts.",
        actors=[ORCH,
                ("app-developer", "sonnet", "AGENT", "backend"),
                ("qa-engineer", "sonnet · journeys", "GATE", "backend"),
                ("ux-critic", "sonnet", "GATE", "backend"),
                ("deploy-engineer", "haiku", "AGENT", "backend")],
        items=[
            ("msg", 2, 0, "JOURNEY FAIL", "return"),
            ("loop", 0, 3, "[any journey FAIL: attempt n of 3]"),
            ("msg", 0, 1, "FIX FAILED", "call"),
            ("msg", 1, 0, "FIXED", "return"),
            ("msg", 0, 2, "ALL LOCAL", "call"),
            ("msg", 2, 0, "RESULTS", "return"),
            ("msg", 0, 3, "UI REGRESSION", "call"),
            ("msg", 3, 0, "VERDICT", "return"),
            ("end",),
            ("msg", 0, 4, "REDEPLOY", "call"),
            ("msg", 4, 0, "APP URL", "return"),
            ("msg", 0, 2, "CONFIRM RUN", "call"),
            ("msg", 2, 0, "ALL PASS", "headline"),
        ],
        notes=[("ALL LOCAL", "the app is started locally and ALL journeys run, not only the failing ones"),
               ("UI REGRESSION", "only if the fix changed frontend files and the team has a ux-critic gate"),
               ("REDEPLOY", "never to find out whether a fix worked; journeys that cannot run locally need your approval first")],
    ),
    dict(
        slug="seq-red-team", eyebrow="Sequence · Iteration",
        title="Adversarial review in rounds of batched probes",
        desc="The reviewer runs up to three rounds of batched probes, each round writing a batch, running it once and reading the results. Findings go to the orchestrator, which loops fixes and QA, then re-reviews by re-running only the probes behind earlier findings plus one regression round.",
        actors=[ORCH,
                ("Red team", "opus · read-only", "GATE", "backend"),
                ("Probe batches", "data · http · static", "BATCH", "backend"),
                ("Owning agent", "builder for the surface", "AGENT", "backend"),
                ("qa-engineer", "sonnet", "GATE", "backend")],
        items=[
            ("msg", 0, 1, "RED TEAM", "call"),
            ("loop", 1, 2, "[round n of 3, stop when no new signal]"),
            ("msg", 1, 2, "RUN BATCH", "call"),
            ("msg", 2, 1, "RESULTS", "return"),
            ("end",),
            ("msg", 1, 0, "FINDINGS", "return"),
            ("loop", 0, 4, "[FAIL: fix, attempt n of 3]"),
            ("msg", 0, 3, "FIX + PROBE", "call"),
            ("msg", 3, 0, "FIXED", "return"),
            ("msg", 0, 4, "RE-RUN QA", "call"),
            ("msg", 4, 0, "QA PASS", "return"),
            ("msg", 0, 1, "RE-REVIEW", "call"),
            ("msg", 1, 2, "RERUN PROBES", "call"),
            ("end",),
            ("msg", 1, 0, "PASS", "headline"),
        ],
        notes=[("RUN BATCH", "data (one-time job, scratch schema), http (local app; GET-only when deployed) and static probes"),
               ("RE-REVIEW", "re-runs only the probes behind prior findings plus one targeted regression round"),
               ("FIX + PROBE", "the fix agent receives the finding and its probe_id as evidence")],
    ),
    dict(
        slug="seq-improve-ux", eyebrow="Sequence · /improve-ux",
        title="/improve-ux on an existing app",
        desc="You give a UX direction. The critic audits the app as it is today, you review the audit, the analyst redesigns the spec, the developer rebuilds the affected pages, and the critic gate loops fixes until it passes. Deploy and journey validation then follow as in the journey diagram.",
        actors=[HUMAN, ORCH,
                ("ux-critic", "sonnet · audit mode", "GATE", "backend"),
                ("ui-ux-analyst", "sonnet", "AGENT", "backend"),
                ("app-developer", "sonnet", "AGENT", "backend")],
        items=[
            ("msg", 0, 1, "DIRECTION", "call"),
            ("msg", 1, 2, "AUDIT", "call"),
            ("msg", 2, 1, "AUDIT FINDS", "return"),
            ("msg", 1, 0, "REVIEW AUDIT", "async"),
            ("msg", 1, 3, "REDESIGN", "call"),
            ("msg", 3, 1, "SPEC V2", "return"),
            ("msg", 1, 4, "REBUILD", "call"),
            ("msg", 4, 1, "BUILT", "return"),
            ("loop", 1, 4, "[gate FAIL: attempt n of 3]"),
            ("msg", 1, 2, "GATE", "call"),
            ("msg", 2, 1, "FINDINGS", "return"),
            ("msg", 1, 4, "FIX IDS", "call"),
            ("end",),
            ("msg", 2, 1, "PASS", "headline"),
        ],
        notes=[("DIRECTION", "free text or a file; an empty direction lets the audit drive the work"),
               ("REVIEW AUDIT", "the phase boundary after the audit: comment in ux-feedback.md, or continue"),
               ("PASS", "design approved: deploy-engineer redeploys, then journeys run (see the journey diagram); --no-deploy stops here")],
    ),
]


# ---------------------------------------------------------------- geometry
def lifeline_xs(n):
    x0, x1 = 136, 904
    return [round(x0 + i * (x1 - x0) / (n - 1)) for i in range(n)]


def layout(d):
    xs = lifeline_xs(len(d["actors"]))
    c, last_y, stack = 176, None, None
    msgs, frames, bands = [], [], []
    for it in d["items"]:
        k = it[0]
        if k == "band":
            bands.append({"label": it[1], "start": None})
        elif k == "loop":
            assert stack is None, "no nested fragments"
            top = (last_y + 24) if last_y else 144
            stack = {"i": it[1], "j": it[2], "guard": it[3], "top": top}
            c = top + 68
            if bands and bands[-1]["start"] is None:
                bands[-1]["start"] = top - 4
        elif k == "end":
            bottom = last_y + 24
            frames.append({**stack, "bottom": bottom})
            stack, c = None, bottom + 36
        else:
            _, s, t, label, kind = it
            assert len(label) <= MAX_LABEL, f"label too long: {label}"
            msgs.append({"y": c, "s": s, "t": t, "label": label, "kind": kind})
            if bands and bands[-1]["start"] is None:
                bands[-1]["start"] = c - 28
            last_y, c = c, c + STEP
    assert stack is None, "unclosed loop"
    assert len(d["actors"]) <= 5, "max 5 lifelines"
    assert len(msgs) <= 12, f"{d['slug']}: {len(msgs)} messages (max 12)"
    assert len(frames) <= 2, "max 2 fragments"
    assert sum(1 for m in msgs if m["kind"] == "headline") <= 1, "one headline message"
    line_end = last_y + 48
    for i, b in enumerate(bands):
        b["end"] = bands[i + 1]["start"] if i + 1 < len(bands) else last_y + 28
    return xs, msgs, frames, bands, line_end


# ---------------------------------------------------------------- rendering
def label_w(label):
    return len(label) * 5.6 + 12


def svg_actor(cx, a, slug):
    name, sub, tag, style = a
    x, y, w, h = cx - 72, 72, 144, 56
    if style == "focal":
        fill, stroke, tagc = "rgba(191,69,32,0.08)", ACCENT, ACCENT
        tagstroke = "rgba(191,69,32,0.50)"
    elif style == "input":
        fill, stroke, tagc = "rgba(79,93,117,0.10)", SOFT, SOFT
        tagstroke = "rgba(90,101,128,0.40)"
    else:
        fill, stroke, tagc = "#ffffff", INK, MUTED
        tagstroke = "rgba(45,49,66,0.30)"
    tw = max(32, len(tag) * 6 + 14)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        f'<rect x="{x + 8}" y="{y + 8}" width="{tw}" height="12" rx="2" fill="transparent" stroke="{tagstroke}" stroke-width="0.8"/>'
        f'<text x="{x + 8 + tw / 2}" y="{y + 17}" fill="{tagc}" font-size="7" font-family="{MONO}" text-anchor="middle" letter-spacing="0.08em">{escape(tag)}</text>'
        f'<text x="{cx}" y="{y + 32}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{escape(name)}</text>'
        f'<text x="{cx}" y="{y + 47}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{escape(sub)}</text>'
    )


def svg_message(m, xs, slug):
    sx, tx = xs[m["s"]], xs[m["t"]]
    d = 1 if tx > sx else -1
    x1, x2, y = sx + 2 * d, tx - 2 * d, m["y"]
    kind = m["kind"]
    if kind == "headline":
        stroke, width, dash, marker = ACCENT, 1.4, "", f"{slug}-arrow-accent"
    elif kind == "return":
        stroke, width, dash, marker = MUTED, 1.2, ' stroke-dasharray="5,4"', f"{slug}-arrow"
    elif kind == "async":
        stroke, width, dash, marker = MUTED, 1.2, ' stroke-dasharray="5,4"', f"{slug}-arrow-open"
    else:
        stroke, width, dash, marker = MUTED, 1.2, "", f"{slug}-arrow"
    # label sits above the stroke, in the gap next to the source lifeline
    nxt = xs[m["s"] + d]
    cx = (sx + nxt) / 2
    lw = label_w(m["label"])
    out = f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{stroke}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>'
    out += f'<rect x="{cx - lw / 2:.0f}" y="{y - 22}" width="{lw:.0f}" height="13" rx="2" fill="{PAPER}"/>'
    col = ACCENT if kind == "headline" else MUTED
    out += (f'<text x="{cx:.0f}" y="{y - 12}" fill="{col}" font-size="8" font-family="{MONO}" '
            f'text-anchor="middle" letter-spacing="0.08em">{escape(m["label"])}</text>')
    return out


def svg_frame(f, xs):
    x = xs[f["i"]] - 28
    w = xs[f["j"]] + 28 - x
    y, h = f["top"], f["bottom"] - f["top"]
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.22)" stroke-width="1"/>'
        f'<rect x="{x}" y="{y}" width="40" height="16" rx="2" fill="{PAPER}" stroke="rgba(45,49,66,0.22)" stroke-width="1"/>'
        f'<text x="{x + 20}" y="{y + 12}" fill="{MUTED}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.12em">LOOP</text>'
        f'<rect x="{x + 8}" y="{y + 20}" width="{len(f["guard"]) * 5.0 + 10:.0f}" height="16" fill="#f1f1f1"/>'
        f'<text x="{x + 12}" y="{y + 32}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.04em">{escape(f["guard"])}</text>'
    )


def svg_band(b, idx):
    y, h = b["start"], b["end"] - b["start"]
    out = f'<line x1="8" y1="{y}" x2="{W - 8}" y2="{y}" stroke="rgba(45,49,66,0.14)" stroke-width="0.8" stroke-dasharray="4,3"/>'
    out += (f'<text x="16" y="{y + 16}" fill="{SOFT}" font-size="8" font-family="{MONO}" letter-spacing="0.14em">{escape(b["label"])}</text>')
    return out


def svg_legend(d, msgs, frames, y0, slug):
    kinds = [k for k in ("call", "return", "async", "headline") if any(m["kind"] == k for m in msgs)]
    items = []
    names = {"call": "Dispatch / call", "return": "Return / report", "async": "Async prompt", "headline": "Headline result"}
    out = f'<line x1="56" y1="{y0}" x2="{W - 56}" y2="{y0}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>'
    out += f'<text x="56" y="{y0 + 16}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">LEGEND</text>'
    x, y = 56, y0 + 36
    for k in kinds:
        stroke = ACCENT if k == "headline" else MUTED
        dash = ' stroke-dasharray="5,4"' if k in ("return", "async") else ""
        marker = {"call": "arrow", "return": "arrow", "async": "arrow-open", "headline": "arrow-accent"}[k]
        wd = 1.4 if k == "headline" else 1.2
        out += f'<line x1="{x}" y1="{y}" x2="{x + 28}" y2="{y}" stroke="{stroke}" stroke-width="{wd}"{dash} marker-end="url(#{slug}-{marker})"/>'
        out += f'<text x="{x + 36}" y="{y + 4}" fill="{MUTED}" font-size="8.5" font-family="{SANS}">{names[k]}</text>'
        x += 200
    if frames:
        out += f'<rect x="{x}" y="{y - 8}" width="28" height="18" rx="2" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.22)" stroke-width="1"/>'
        out += f'<text x="{x + 5}" y="{y + 4}" fill="{MUTED}" font-size="7" font-family="{MONO}">LOOP</text>'
        out += f'<text x="{x + 36}" y="{y + 4}" fill="{MUTED}" font-size="8.5" font-family="{SANS}">Iteration (shared 3-attempt cap)</text>'
    return out


def render(d):
    slug = d["slug"]
    xs, msgs, frames, bands, line_end = layout(d)
    legend_y = line_end + 28
    H = legend_y + 64
    parts = [
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">',
        f'<title id="{slug}-title">{escape(d["title"])}</title>',
        f'<desc id="{slug}-desc">{escape(d["desc"])}</desc>',
        "<defs>",
        f'<marker id="{slug}-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{MUTED}"/></marker>',
        f'<marker id="{slug}-arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{ACCENT}"/></marker>',
        f'<marker id="{slug}-arrow-open" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polyline points="0 0, 8 3, 0 6" fill="none" stroke="{MUTED}" stroke-width="1.2"/></marker>',
        "</defs>",
        f'<rect width="100%" height="100%" fill="{PAPER}"/>',
    ]
    parts += [svg_band(b, i) for i, b in enumerate(bands)]
    parts += [f'<line x1="{x}" y1="128" x2="{x}" y2="{line_end}" stroke="rgba(45,49,66,0.22)" stroke-width="1" stroke-dasharray="3,3"/>' for x in xs]
    parts += [svg_frame(f, xs) for f in frames]
    parts += [svg_message(m, xs, slug) for m in msgs]              # arrows before boxes
    parts += [svg_actor(xs[i], a, slug) for i, a in enumerate(d["actors"])]
    parts.append(svg_legend(d, msgs, frames, legend_y, slug))
    parts.append("</svg>")
    return "\n".join(parts), W


def page(d):
    svg, w = render(d)
    notes = "".join(f"<li><b>{escape(k)}</b> {escape(v)}</li>" for k, v in d.get("notes", []))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(d["title"])} · Sequence</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --paper:{PAPER}; --ink:{INK}; --muted:{MUTED}; --accent:{ACCENT}; }}
    body {{ font-family: 'Geist', system-ui, sans-serif; background: var(--paper); color: var(--ink);
           min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1100px; width: 100%; }}
    .eyebrow {{ font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; font-weight: 500;
               letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem; }}
    h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem); font-weight: 400;
         letter-spacing: -0.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
    .scroll {{ overflow-x: auto; }}
    svg {{ width: 100%; min-width: {w}px; display: block; }}
    .notes {{ list-style: none; margin-top: 1.25rem; font-size: 0.78rem; color: var(--muted); line-height: 1.6; }}
    .notes b {{ font-family: 'Geist Mono', ui-monospace, monospace; font-weight: 500; font-size: 0.7rem;
               letter-spacing: 0.08em; color: var(--ink); margin-right: 0.5rem; }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{escape(d["eyebrow"])}</p>
    <h1>{escape(d["title"])}</h1>
    <div class="scroll">
{svg}
    </div>
    <ul class="notes">{notes}</ul>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out, exist_ok=True)
    for d in DIAGRAMS:
        path = os.path.join(out, d["slug"] + ".html")
        open(path, "w").write(page(d))
        print("wrote", path)
