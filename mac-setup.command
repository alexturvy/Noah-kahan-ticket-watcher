#!/bin/bash
#
# Noah Kahan ticket watcher — one-step setup + launch for macOS.
#
# This is safe to paste again any time: it picks up where it left off.
#
set -u

REPO_URL="https://github.com/alexturvy/noah-kahan-ticket-watcher.git"
APP_DIR="$HOME/noah-kahan-ticket-watcher"

echo ""
echo "=================================================="
echo "  Noah Kahan ticket watcher — setup"
echo "=================================================="
echo ""

# 1. Make sure the basic tools (git + python3) are installed.
#    On a fresh Mac these come bundled with Apple's "Command Line Tools".
if ! command -v git >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  echo "First-time setup: macOS needs to install a small set of developer tools."
  echo "A popup should appear — click \"Install\" and wait for it to finish"
  echo "(it can take several minutes)."
  echo ""
  echo ">>> When it's done, paste the SAME command again to continue. <<<"
  echo ""
  xcode-select --install 2>/dev/null
  exit 0
fi

# 2. Download (or update) the watcher.
if [ -d "$APP_DIR/.git" ]; then
  echo "Updating the watcher..."
  git -C "$APP_DIR" pull --quiet || true
else
  echo "Downloading the watcher..."
  git clone --depth 1 "$REPO_URL" "$APP_DIR" || {
    echo "Could not download the watcher. Check your internet connection and try again."
    exit 1
  }
fi

cd "$APP_DIR" || { echo "Could not open $APP_DIR"; exit 1; }

# 3. Set up an isolated Python environment and install what's needed.
if [ ! -d "venv" ]; then
  echo "Setting up (this part only happens once and may take a few minutes)..."
  python3 -m venv venv || { echo "Could not create the Python environment."; exit 1; }
  ./venv/bin/python -m pip install --quiet --upgrade pip
  ./venv/bin/python -m pip install --quiet -r requirements.txt || {
    echo "Could not install the required packages."; exit 1; }
  echo "Installing the background browser..."
  ./venv/bin/python -m playwright install chromium || {
    echo "Could not install the browser."; exit 1; }
else
  echo "Already set up — skipping installation."
fi

# 4. Launch. caffeinate (built into macOS) keeps the Mac awake while it runs.
echo ""
echo "=================================================="
echo "  Starting the watcher!"
echo ""
echo "  * A browser window will open. If it asks, log into"
echo "    Ticketmaster once — it'll be remembered."
echo "  * Leave THIS window and the browser open."
echo "  * To stop later: close this window, or press Control-C."
echo "=================================================="
echo ""

exec caffeinate -i ./venv/bin/python watch.py
