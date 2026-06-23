# Noah Kahan ticket watcher 🎟️

Watches the sold-out **Noah Kahan — Cincinnati, Great American Ball Park, July 1, 2026**
show and alerts you the instant real seats (including resale) become available.

It keeps a real, logged-in browser open and reads Ticketmaster's own
seat-availability data in the background. When seats appear, it pops a loud
notification on the Mac and (optionally) pushes an alert to your phone.

---

## How to run it (Mac)

1. Open **Terminal** (press `Cmd`+`Space`, type `Terminal`, hit Enter).
2. Paste this one line and press Enter:

   ```
   curl -fsSL https://raw.githubusercontent.com/alexturvy/noah-kahan-ticket-watcher/main/mac-setup.command | bash
   ```

3. That's it. It downloads everything, sets itself up, and starts watching.

### What to expect the first time

- **A developer-tools popup may appear** (only on a Mac that's never had it).
  Click **Install**, wait for it to finish, then paste the same line again.
- **A browser window will open.** If Ticketmaster asks, **log in once** — it's
  remembered after that.
- **Leave the Terminal window and the browser open.** Closing them stops the watcher.

When seats show up you'll hear and see an alert on the Mac. To stop it, close the
Terminal window or press `Control`+`C`.

---

## Want the alert on your phone too? (optional)

The Mac alerts on its own — no phone app required. If you *also* want a push
notification on a phone:

1. Install the free **ntfy** app (App Store / Google Play).
2. In the app, **subscribe** to this topic (type it exactly):

   ```
   noah-kahan-cincy-resale-7c3f9a21
   ```

That's all. Anyone subscribed to that topic gets the alert.

---

## Good to know (the honest version)

- **The Mac has to stay awake and online**, with the Terminal and browser open.
  The watcher keeps the Mac from going to sleep on its own, but closing the lid
  or shutting down will stop it.
- **This improves your odds; it's not a guarantee.** It checks about once a
  minute, which catches normal resale listings well, but professional bots can
  grab instant drops faster. Treat it as a very good extra set of eyes.
- **As a free backup**, also tap **"Notify Me"** on the Ticketmaster event page
  and turn on resale alerts there.
- Automated checking is against Ticketmaster's terms of service. This runs gently
  (one personal check at a time), but that's worth knowing.

---

## Watching a different show?

Open `watch.py` and change `EVENT_URL` and `EVENT_ID` near the top to the event
you want. Everything else works the same.
