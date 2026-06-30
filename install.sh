#!/usr/bin/env bash
#
# Install the Speedrun Claude Code status line.
#
#   ./install.sh                 # from a local clone
#   curl -fsSL https://raw.githubusercontent.com/a16z-speedrun/speedrun-statusline/main/install.sh | bash
#
# Copies statusline.py into your Claude config dir and wires the `statusLine`
# block into settings.json (merging, never clobbering your other settings).
# An existing statusLine config is backed up first.
#
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/a16z-speedrun/speedrun-statusline/main"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DEST="$CLAUDE_DIR/speedrun-statusline.py"
SETTINGS="$CLAUDE_DIR/settings.json"

# Resolve the source script: prefer a sibling file (local clone), otherwise
# download it from the public repo so the curl|bash one-liner works too.
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

echo "→ Installing Speedrun status line"

mkdir -p "$CLAUDE_DIR"
if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/statusline.py" ]; then
  cp "$SRC_DIR/statusline.py" "$DEST"
  echo "  • copied script → $DEST"
else
  echo "  • downloading statusline.py from $RAW_BASE"
  curl -fsSL "$RAW_BASE/statusline.py" -o "$DEST"
  echo "  • saved script → $DEST"
fi
chmod +x "$DEST"

# Merge the statusLine block into settings.json, preserving everything else.
python3 - "$SETTINGS" "$DEST" <<'PY'
import json, os, shutil, sys

settings_path, dest = sys.argv[1], sys.argv[2]

data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            data = json.load(f)
    except Exception:
        # Don't destroy an unparseable file — back it up and start fresh.
        shutil.copy(settings_path, settings_path + ".bak")
        print("  • existing settings.json was unparseable; backed up to "
              "settings.json.bak")

if "statusLine" in data:
    with open(settings_path + ".statusLine.bak", "w") as f:
        json.dump({"statusLine": data["statusLine"]}, f, indent=2)
    print("  • backed up prior statusLine → settings.json.statusLine.bak")

# Use ~ so the path stays portable across machines/users.
home = os.path.expanduser("~")
cmd = dest.replace(home, "~", 1) if dest.startswith(home) else dest
data["statusLine"] = {
    "type": "command",
    "command": cmd,
    "padding": 1,
    "refreshInterval": 10,
}

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  • wired statusLine → {settings_path}")
PY

echo
echo "✓ Installed. Open a new Claude Code session (or wait ~10s) to see it."
echo "  🏁 Counting down to Demo Day. Good luck out there."
