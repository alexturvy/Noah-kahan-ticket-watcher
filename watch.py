#!/usr/bin/env python3
"""
Noah Kahan resale-seat watcher  —  Cincinnati, Great American Ball Park, July 1, 2026.

What it does
------------
Keeps a real (logged-in) browser open to the Ticketmaster event page and, on a
loop, reads the *actual seat-availability JSON* that the page fetches behind the
scenes. The moment real seats appear (including resale), it:

  * pops a loud notification on this Mac (no app needed), and
  * optionally pushes the alert to a phone via ntfy.

Why a browser instead of a plain web request: Ticketmaster's seat data is behind
bot protection, so a normal script gets blocked. A real browser session sails
through — we just read the data it already loads instead of scraping the page
text (which is fragile and breaks whenever Ticketmaster rewords anything).

You only configure things if you want to. Sensible defaults are baked in.
"""

import json
import os
import random
import subprocess
import time

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ---------------------------------------------------------------------------
# Config  (override any of these with environment variables if you like)
# ---------------------------------------------------------------------------

# The Cincinnati show. Change EVENT_URL + EVENT_ID together to watch a different one.
EVENT_ID = os.environ.get("EVENT_ID", "16006441B2247E96")
EVENT_URL = os.environ.get(
    "EVENT_URL",
    "https://www.ticketmaster.com/noah-kahan-the-great-divide-tour-"
    "cincinnati-ohio-07-01-2026/event/16006441B2247E96",
)

# Phone push (optional). Install the free "ntfy" app, subscribe to this exact
# topic, and you'll get alerts on your phone too. Leave blank to skip phone push
# and rely only on the Mac's own notification.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "noah-kahan-cincy-resale-7c3f9a21")

# How often to check, in seconds (a little randomness is added so it looks human).
CHECK_EVERY_SECONDS = int(os.environ.get("CHECK_EVERY_SECONDS", "60"))
JITTER_SECONDS = 15

# Where the logged-in browser session is stored (so you only log in once).
PROFILE_DIR = os.environ.get("PROFILE_DIR", "tm_profile")

# Set HEADLESS=1 only for testing; Ticketmaster needs a visible window to work.
HEADLESS = os.environ.get("HEADLESS") == "1"

# On the first successful read we save the raw availability data here so the
# seat-counting logic can be double-checked against the real thing.
SAMPLE_FILE = "ismds_sample.json"


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def mac_notify(title, message):
    """Loud, app-free alert on the Mac itself: banner + spoken voice."""
    safe = message.replace('"', "'")
    safe_title = title.replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe}" with title "{safe_title}" sound name "Glass"'],
            check=False,
        )
    except Exception as e:
        print("Mac notification failed:", e)
    # Speak it so it's heard from across the room, even with the screen off.
    try:
        subprocess.run(["say", message], check=False)
    except Exception:
        pass


def phone_alert(message):
    """Optional push to a phone via ntfy. Silently skipped if no topic set."""
    if not NTFY_TOPIC:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Noah Kahan tickets!",
                "Priority": "urgent",
                "Tags": "rotating_light,tickets",
            },
            timeout=10,
        )
        print("Phone alert sent.")
    except Exception as e:
        print("Phone alert failed:", e)


def fire_alert(count, payload):
    price = lowest_price(payload)
    extra = f" from ${price}" if price is not None else ""
    message = (
        f"{count} Noah Kahan Cincinnati seat(s) available now{extra}! "
        f"Buy: {EVENT_URL}"
    )
    print("\n*** " + message + " ***\n")
    mac_notify("Noah Kahan tickets available!", message)
    phone_alert(message)


# ---------------------------------------------------------------------------
# Reading availability out of Ticketmaster's JSON
# ---------------------------------------------------------------------------

def count_available(payload):
    """
    How many seats the availability payload reports.

    Ticketmaster's seat-map ("ismds") response is a list of "facets" — groupings
    of available places, each with a "count". Summing those counts gives the
    number of buyable seats (resale included). When the show is sold out the list
    is empty and this returns 0.

    If a future payload is shaped differently, check the saved ismds_sample.json
    and adjust this one function — nothing else needs to change.
    """
    if not isinstance(payload, dict):
        return 0

    facets = payload.get("facets")
    if isinstance(facets, list):
        total = 0
        for facet in facets:
            # The feed normally only returns available facets, but guard anyway:
            # skip any facet explicitly marked unavailable.
            if isinstance(facet, dict) and facet.get("available", True):
                c = facet.get("count")
                if isinstance(c, (int, float)):
                    total += int(c)
        return total

    # Fallback: some responses expose a running total instead of a facet list.
    totals = payload.get("totals")
    if isinstance(totals, dict):
        for key in ("available", "count", "places"):
            v = totals.get(key)
            if isinstance(v, (int, float)):
                return int(v)
    return 0


def lowest_price(payload):
    """Best-effort lowest price for a nicer alert; None if we can't find one."""
    prices = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("currentPrice", "price", "faceValue", "totalPrice") and \
                        isinstance(v, (int, float)) and v > 0:
                    prices.append(float(v))
                elif k == "listPriceRange" and isinstance(v, list):
                    # ismds facets carry price as [{"currency","min","max"}].
                    for rng in v:
                        if isinstance(rng, dict):
                            m = rng.get("min")
                            if isinstance(m, (int, float)) and m > 0:
                                prices.append(float(m))
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    try:
        walk(payload)
    except Exception:
        return None
    if not prices:
        return None
    return round(min(prices), 2)


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def close_cookie_banner(page):
    for selector in (
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button:has-text('OK')",
        "button:has-text('Got It')",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=2000)
                time.sleep(1)
                return
        except Exception:
            pass


def open_ticket_map(page):
    """Best-effort: click into the seat map so the availability JSON loads.

    The event URL usually goes straight to the map, but some layouts gate it
    behind a button. Failures here are fine — it's just a nudge.
    """
    for selector in (
        "button:has-text('Find Tickets')",
        "a:has-text('Find Tickets')",
        "button:has-text('Get Tickets')",
        "button:has-text('Buy')",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=2000)
                time.sleep(2)
                return
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def is_availability_response(response):
    """True for the Ticketmaster background feed that carries seat availability.

    The feed lives under the path /api/ismds/event/, but Ticketmaster serves it
    from different hosts depending on the event/market — today it's
    offeradapter.ticketmaster.com (it used to be services.ticketmaster.com).
    Match on the path, not a hardcoded host, so a host change can't silently
    break capture (which looks like "No availability data captured" every cycle).
    """
    url = response.url
    return "/api/ismds/event/" in url and \
        any(tag in url for tag in ("facets", "quickpicks", "availability"))


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def fetch_in_page(page, url):
    """
    Ask Ticketmaster for the availability feed from *inside* the page's own
    JavaScript. This carries the real session/cookies and runs as the genuine
    page, so it passes bot protection and works even when the page's UI is just
    showing "sold out" and never redraws the seat map. Returns parsed JSON or None.
    """
    try:
        text = page.evaluate(
            """async (u) => {
                try {
                    const r = await fetch(u, {
                        credentials: 'include',
                        headers: {'Accept': 'application/json'},
                    });
                    if (!r.ok) return null;
                    return await r.text();
                } catch (e) { return null; }
            }""",
            url,
        )
    except Exception:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def get_payload(page, context, learned):
    """
    Fetch the seat-availability data for one cycle, reliably.

    Strategy:
      1. Once we've learned the feed's URL, fetch it from inside the page (most
         reliable — it's the real page asking, so bot protection lets it through,
         and it doesn't depend on the UI re-drawing the seat map).
      2. Backup: ask via the browser's request session directly.
      3. First time, or if both direct paths fail, load the event page, wait for
         the feed to fire, and learn its URL for next time.
    """
    if learned["url"]:
        payload = fetch_in_page(page, learned["url"])
        if payload is not None:
            return payload
        try:
            r = context.request.get(
                learned["url"],
                headers={"Accept": "application/json", "Referer": EVENT_URL},
            )
            if r.ok:
                payload = safe_json(r)
                if payload is not None:
                    return payload
        except Exception:
            pass

    # (Re)learn the feed URL by loading the page and waiting for the feed.
    try:
        with page.expect_response(is_availability_response, timeout=30000) as resp_info:
            page.goto(EVENT_URL, wait_until="domcontentloaded")
            close_cookie_banner(page)
            open_ticket_map(page)
        resp = resp_info.value
        learned["url"] = resp.url
        return safe_json(resp)
    except PlaywrightTimeoutError:
        return None


def main():
    learned = {"url": None}

    print("Noah Kahan ticket watcher starting...")
    print(f"Event:  {EVENT_URL}")
    print(f"Phone alerts: {'on (ntfy topic ' + NTFY_TOPIC + ')' if NTFY_TOPIC else 'off'}")
    print("A browser window will open. Log into Ticketmaster once if asked,")
    print("then just leave this window and the browser open.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS,
            viewport={"width": 1400, "height": 900},
        )
        page = browser.new_page()

        prev_available = None
        sample_saved = False

        while True:
            stamp = time.strftime("%I:%M:%S %p")
            try:
                payload = get_payload(page, browser, learned)
                if payload is None:
                    print(f"[{stamp}] No availability data captured this cycle "
                          "(page may still be loading or needs login).")
                else:
                    if not sample_saved:
                        try:
                            with open(SAMPLE_FILE, "w") as f:
                                json.dump(payload, f, indent=2)
                            print(f"[{stamp}] Saved a sample of the availability "
                                  f"data to {SAMPLE_FILE}.")
                        except Exception:
                            pass
                        sample_saved = True

                    count = count_available(payload)
                    print(f"[{stamp}] Seats available: {count}")

                    if count > 0 and (prev_available is None or prev_available == 0):
                        fire_alert(count, payload)
                    prev_available = count

            except KeyboardInterrupt:
                print("\nStopped. Bye!")
                break
            except Exception as e:
                print(f"[{stamp}] Hiccup (will keep trying):", e)

            delay = CHECK_EVERY_SECONDS + random.randint(-JITTER_SECONDS, JITTER_SECONDS)
            delay = max(20, delay)
            print(f"Next check in {delay}s...\n")
            try:
                time.sleep(delay)
            except KeyboardInterrupt:
                print("\nStopped. Bye!")
                break

        browser.close()


if __name__ == "__main__":
    main()
