#!/usr/bin/env python3
"""Run a batch of HTTP probes and write structured results.

Used by the adversarial-reviewer (lib/adversarial-probe-schema.yaml). Stdlib only.

    run_http_probes.py PROBES.json RESULTS.json [--allow-mutating]

PROBES.json:
  {"base_url": "http://localhost:8000",
   "probes": [{"id": "P-http-001", "claim": "...", "method": "GET", "path": "/api/x",
               "headers": {}, "body": null, "mutating": false,
               "expect": {"status_in": [401, 403], "body_not_contains": ["traceback"],
                          "body_contains": [], "header_absent": ["x-powered-by"]}}]}

A probe HOLDS when every expectation is met (the app defended itself) and is FALSIFIED
when any expectation fails. A transport error is recorded as ERROR, never as HOLDS.
Mutating probes (POST/PUT/PATCH/DELETE, or "mutating": true) are refused unless the
base_url host is localhost/127.0.0.1 or --allow-mutating is given.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_mutating(probe):
    return bool(probe.get("mutating")) or probe.get("method", "GET").upper() in MUTATING_METHODS


def run_probe(base_url, probe):
    method = probe.get("method", "GET").upper()
    url = base_url.rstrip("/") + probe["path"]
    body = probe.get("body")
    data = None
    headers = dict(probe.get("headers") or {})
    if body is not None:
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=probe.get("timeout_s", 15)) as resp:
            status, text, resp_headers = resp.status, resp.read().decode("utf-8", "replace"), resp.headers
    except urllib.error.HTTPError as e:
        status, text, resp_headers = e.code, e.read().decode("utf-8", "replace"), e.headers
    elapsed_ms = int((time.monotonic() - start) * 1000)

    expect = probe.get("expect") or {}
    failures = []
    if "status_in" in expect and status not in expect["status_in"]:
        failures.append(f"status {status} not in {expect['status_in']}")
    lowered = text.lower()
    for s in expect.get("body_not_contains", []):
        if s.lower() in lowered:
            failures.append(f"body contains forbidden {s!r}")
    for s in expect.get("body_contains", []):
        if s.lower() not in lowered:
            failures.append(f"body missing required {s!r}")
    for h in expect.get("header_absent", []):
        if resp_headers.get(h) is not None:
            failures.append(f"header {h!r} present")
    return {
        "id": probe["id"], "claim": probe.get("claim", ""), "request": f"{method} {probe['path']}",
        "status": status, "elapsed_ms": elapsed_ms,
        "verdict": "FALSIFIED" if failures else "HOLDS",
        "failures": failures, "body_excerpt": text[:500],
    }


def main(argv):
    allow = "--allow-mutating" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    spec = json.load(open(args[0]))
    base_url = spec["base_url"]
    local = urllib.parse.urlparse(base_url).hostname in LOCAL_HOSTS
    results = []
    for probe in spec["probes"]:
        if is_mutating(probe) and not (local or allow):
            results.append({"id": probe["id"], "claim": probe.get("claim", ""), "verdict": "SKIPPED",
                            "failures": ["mutating probe refused against non-local base_url"]})
            continue
        try:
            results.append(run_probe(base_url, probe))
        except Exception as e:  # transport errors must not read as a pass
            results.append({"id": probe["id"], "claim": probe.get("claim", ""), "verdict": "ERROR",
                            "failures": [f"{type(e).__name__}: {e}"]})
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    json.dump({"base_url": base_url, "counts": counts, "results": results}, open(args[1], "w"), indent=2)
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
