"""
Drive a list of user journeys against an already-running, authenticated app via
Playwright + Chrome DevTools Protocol. Connects to Chrome on 127.0.0.1:9222.

Usage:
    Edit the JOURNEYS list (or import this module and call run(journeys=...)).
    python3 drive_journeys.py

Each journey:
    {
      "name":         "J1",                               # short id for filenames + logs
      "store":        "36",                               # value passed to select_option on the first <select>
      "prompt":       "What's the status of my store?",   # verbatim text to type into the chat input
      "confirm":      False,                              # set True if the journey produces a Confirm button to click
      "max_wait_s":   45,                                 # cap on settle-polling
    }

Outputs:
    /tmp/<name>_final.png       — screenshot at end of polling
    /tmp/<name>_before_confirm.png — only for confirm:True journeys
    A JSON results array printed at the end (also returned by run()).

Gotchas (see SKILL.md for the full list):
    - Tune `settle_polls` upward if the right sidebar refreshes during streaming
      and causes false-positive "settled" exits.
    - Don't loop multiple python3 invocations — keep everything in one asyncio.run().
"""
import asyncio
import json
import re
import time

from playwright.async_api import async_playwright


JOURNEYS_DEFAULT = [
    # Replace with the journeys you want to drive.
    {"name": "J1", "store": "36", "prompt": "What's the status of my store?", "confirm": False},
]


async def select_store(page, store_id):
    """Select a store by value on the first <select> element. Works for hidden-select dropdowns."""
    sel = page.locator("select").first
    await sel.select_option(value=str(store_id))
    await page.wait_for_timeout(1500)


async def get_chat_input(page):
    """Best-effort chat input locator. Tune the selector if your app differs."""
    return page.locator(
        "textarea, "
        "input[placeholder*='store'], "
        "input[placeholder*='question'], "
        "input[placeholder*='Ask']"
    ).first


async def send_prompt(page, prompt):
    chat_input = await get_chat_input(page)
    await chat_input.click()
    await chat_input.fill("")
    await chat_input.type(prompt, delay=15)
    await page.wait_for_timeout(200)
    await chat_input.press("Enter")


async def wait_for_response(page, max_wait_s=45, settle_polls=6):
    """Settle-polling on body innerText length. See SKILL.md 'Wait-for-streaming-response pattern'."""
    t0 = time.monotonic()
    base = await page.evaluate("() => document.body.innerText.length")
    last = base
    stable = 0
    grew = False
    deadline = t0 + max_wait_s
    while time.monotonic() < deadline:
        await page.wait_for_timeout(500)
        cur = await page.evaluate("() => document.body.innerText.length")
        if cur > last + 10:
            last = cur
            stable = 0
            grew = True
        elif grew:
            stable += 1
            if stable >= settle_polls:
                break
    return time.monotonic() - t0, last - base, grew


async def click_confirm_if_present(page, name, timeout_s=15):
    """Look for a Confirm-style button in the chat area. Returns True if clicked."""
    confirm_locator = page.get_by_role(
        "button",
        name=re.compile(r"^(Confirm|Yes|Approve|Run( now)?)$", re.I),
    )
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            if await confirm_locator.count() > 0:
                await page.screenshot(path=f"/tmp/{name.lower()}_before_confirm.png", full_page=False)
                await confirm_locator.first.click()
                return True
        except Exception:
            pass
        await page.wait_for_timeout(500)
    return False


async def capture_assistant_text(page):
    """Heuristic: grab the lowest-on-page large text block that isn't an input.

    Override this with an app-specific selector for cleaner extraction
    (e.g., page.locator('[data-role=assistant]').last.text_content()).
    """
    return await page.evaluate(
        """
      () => {
        const candidates = Array.from(document.querySelectorAll('div, p, article'))
          .filter(el => {
            const txt = (el.innerText || '').trim();
            if (txt.length < 60 || txt.length > 6000) return false;
            if (el.querySelector('input, textarea, button')) return false;
            const r = el.getBoundingClientRect();
            return r.top > 0 && r.bottom < window.innerHeight + 300;
          });
        if (candidates.length === 0) return '';
        candidates.sort((a,b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom);
        return candidates[0].innerText.trim().slice(0, 1500);
      }
    """
    )


FAIL_SIGNATURES = [
    "trouble connecting",
    "error_code",
    "BAD_REQUEST",
    "guardrail",
    "PERMISSION_DENIED",
    "PII",
]


async def run(journeys=None, app_url_hint="", cdp_url="http://127.0.0.1:9222"):
    journeys = journeys or JOURNEYS_DEFAULT
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=5000)
        ctx = browser.contexts[0]
        if app_url_hint:
            page = next((pg for pg in ctx.pages if app_url_hint in pg.url), ctx.pages[0])
        else:
            page = ctx.pages[0]
        await page.bring_to_front()
        print(f"[setup] connected. url={page.url}")
        results = []
        for j in journeys:
            name = j["name"]
            print(f"\n[{name}] === store={j.get('store')} prompt={j['prompt'][:60]!r}")
            try:
                if "store" in j:
                    await select_store(page, j["store"])
                t_send = time.time()
                await send_prompt(page, j["prompt"])
                print(f"[{name}] prompt sent at unix_ts={t_send:.3f}")
                confirm_clicked = False
                if j.get("confirm"):
                    await page.wait_for_timeout(3000)
                    confirm_clicked = await click_confirm_if_present(page, name)
                    print(f"[{name}] confirm clicked: {confirm_clicked}")
                elapsed, delta, grew = await wait_for_response(
                    page, max_wait_s=j.get("max_wait_s", 45), settle_polls=j.get("settle_polls", 6)
                )
                shot = f"/tmp/{name.lower()}_final.png"
                await page.screenshot(path=shot, full_page=False)
                final_text = await capture_assistant_text(page)
                fail_sig = next(
                    (s for s in FAIL_SIGNATURES if s.lower() in (final_text or "").lower()),
                    None,
                )
                results.append(
                    {
                        "journey": name,
                        "store": j.get("store"),
                        "prompt": j["prompt"],
                        "send_unix_ts": round(t_send, 3),
                        "elapsed_s": round(elapsed, 1),
                        "delta_chars": delta,
                        "grew": grew,
                        "confirm_required": j.get("confirm", False),
                        "confirm_clicked": confirm_clicked,
                        "fail_signature": fail_sig,
                        "final_text_excerpt": (final_text or "")[:500],
                        "screenshot": shot,
                    }
                )
                print(f"[{name}] done elapsed={elapsed:.1f}s grew={grew} fail_sig={fail_sig}")
            except Exception as e:
                print(f"[{name}] EXCEPTION: {e!r}")
                results.append({"journey": name, "error": repr(e)})
        await browser.close()
        print("\n=== RESULTS JSON ===")
        print(json.dumps(results, indent=2))
        return results


if __name__ == "__main__":
    asyncio.run(run())
