#!/usr/bin/env python3
"""Speedrun Claude Code status line — a countdown to Demo Day, plus session vitals.

Reads the session JSON on stdin and prints a single compact line:

  Opus · my-app · main +2~1 · ▓▓▓░░░░░ 31% · 🏁 Demo Day 98d 14h · speedrun ↗ · $0.42

The headline segment is a live countdown to Speedrun Demo Day. The date is read
from a small shared public config (cohort.json in a16z-speedrun/speedrun-config)
so it can be re-dated for the next cohort without anyone reinstalling — the
status line fetches it out of band (a detached `--refresh`), caches it, and reads
the cache instantly so the network never blocks the line. A baked-in default
keeps the countdown working on a fresh or offline install until the first fetch
lands.

Once Demo Day passes, the countdown shows "It's Demo Day!" for the day, then
disappears — the line cleanly reverts to your normal vitals with no stale text.

Segments degrade gracefully: missing fields are skipped, and when the terminal
is narrow the lowest-priority segments are dropped so the line never wraps. Git
state is cached per session to keep the script fast.

Config (environment variables):
  SR_STATUSLINE_NO_DEMODAY=1  hide the Demo Day countdown
  SR_STATUSLINE_NO_BRAND=1    hide the `speedrun ↗` link
  SR_STATUSLINE_CONFIG_URL    override the remote config URL (advanced)
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

# ── palette (256-color; iTerm2 renders these nicely) ───────────────────
RESET = "\033[0m"
DIM = "\033[38;5;244m"      # separators / muted text
CYAN = "\033[38;5;39m"      # model
BLUE = "\033[38;5;75m"      # directory
GREEN = "\033[38;5;78m"     # healthy / far out
YELLOW = "\033[38;5;221m"   # caution
ORANGE = "\033[38;5;215m"   # warning / getting close
RED = "\033[38;5;203m"      # danger / imminent
MAGENTA = "\033[38;5;176m"  # pr / accents
GOLD = "\033[38;5;179m"     # speedrun gold

SEP = f" {DIM}·{RESET} "

# ── version + remote config ────────────────────────────────────────────
VERSION = "1.1.0"

# A fresh or offline install still counts down using these baked-in defaults;
# the fetched config (when it lands) overrides them. ISO-8601 with an explicit
# offset so the countdown is identical on every machine, in any timezone.
DEFAULT_DEMO_DAY = "2026-10-06T09:00:00-07:00"
DEFAULT_MILESTONE = "Demo Day"

LIVE_WINDOW_SECS = 12 * 3600   # show "It's Demo Day!" for this long after the start

CACHE_DIR = os.path.expanduser("~/.claude")
CONFIG_CACHE = os.path.join(CACHE_DIR, "speedrun-statusline.json")
CONFIG_REFRESH_SECS = 6 * 3600  # dates change rarely — check ~4×/day
CONFIG_URL = os.environ.get(
    "SR_STATUSLINE_CONFIG_URL",
    "https://raw.githubusercontent.com/a16z-speedrun/speedrun-config/main/cohort.json",
)
REPO_URL = "https://github.com/a16z-speedrun/speedrun-statusline"

BRAND = "speedrun"
BRAND_URL = "https://speedrun.a16z.com/"
BRAND_DISABLED = os.environ.get("SR_STATUSLINE_NO_BRAND", "") not in ("", "0")
DEMODAY_DISABLED = os.environ.get("SR_STATUSLINE_NO_DEMODAY", "") not in ("", "0")


def link(url, text):
    """Wrap text in an OSC 8 hyperlink (clickable in iTerm2 and friends)."""
    return f"\033]8;;{url}\a{text}\033]8;;\a"


def color(text, c):
    return f"{c}{text}{RESET}"


def kfmt(n):
    """Compact token count: 180000 -> '180k', 1000000 -> '1M'."""
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n // 1000}k"
    return str(n)


def until(epoch, now):
    """Compact time-until: '1h48m', '2d3h', or '' if past/absent."""
    if not epoch:
        return ""
    secs = int(epoch - now)
    if secs <= 0:
        return ""
    d, h, m = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
    if d:
        return f"{d}d{h}h"
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def util_color(pct):
    """Green < 50, yellow >= 50, orange >= 70, red >= 90."""
    if pct >= 90:
        return RED
    if pct >= 70:
        return ORANGE
    if pct >= 50:
        return YELLOW
    return GREEN


def run(args):
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except Exception:
        return ""


def git_info(cwd, session_id):
    """Branch + dirty/ahead/behind, cached ~3s per session+dir."""
    key = f"{session_id}-{abs(hash(cwd)) % (10**8)}"
    cache = f"/tmp/cc-statusline-git-{key}"
    try:
        if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 3:
            with open(cache) as f:
                return json.load(f)
    except Exception:
        pass

    info = {}
    inside = run(["git", "-C", cwd, "rev-parse", "--is-inside-work-tree"])
    if inside == "true":
        branch = run(["git", "-C", cwd, "branch", "--show-current"])
        if not branch:  # detached HEAD
            branch = run(["git", "-C", cwd, "rev-parse", "--short", "HEAD"])
            branch = f"@{branch}" if branch else "?"
        info["branch"] = branch

        porcelain = run(["git", "-C", cwd, "status", "--porcelain"])
        staged = modified = untracked = 0
        for line in porcelain.splitlines():
            x, y = line[0], line[1] if len(line) > 1 else " "
            if x == "?" and y == "?":
                untracked += 1
            else:
                if x not in " ?":
                    staged += 1
                if y not in " ?":
                    modified += 1
        info.update(staged=staged, modified=modified, untracked=untracked)

        ab = run(["git", "-C", cwd, "rev-list", "--left-right", "--count",
                  "@{upstream}...HEAD"])
        if ab and "\t" in ab:
            behind, ahead = ab.split("\t")
            info["behind"], info["ahead"] = int(behind), int(ahead)

    try:
        with open(cache, "w") as f:
            json.dump(info, f)
    except Exception:
        pass
    return info


# ── remote config (Demo Day date + latest version) ─────────────────────
def parse_iso(s):
    """ISO-8601 -> epoch seconds, or 0. A naive value (no offset) is read as
    local time, matching how the new-tab extension parses the same date."""
    if not s:
        return 0
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0


def refresh_config():
    """Fetch speedrun.json and write the cache. Called in a detached
    `--refresh` subprocess so it never blocks rendering. Public URL, so this
    is a plain HTTPS GET — no auth, works for everyone."""
    payload = {"ts": time.time(), "ok": False, "config": {}}
    try:
        import urllib.request
        req = urllib.request.Request(
            CONFIG_URL, headers={"User-Agent": f"speedrun-statusline/{VERSION}"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            cfg = json.loads(resp.read().decode("utf-8"))
        if isinstance(cfg, dict):
            payload["ok"] = True
            payload["config"] = cfg
    except Exception:
        pass
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = CONFIG_CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, CONFIG_CACHE)
    except Exception:
        pass


def spawn_refresh():
    """Kick off a detached config refresh; cheap no-op if one ran recently."""
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--refresh"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception:
        pass


def load_config(now):
    """Read the cached config; spawn a background refresh when missing/stale.
    Returns the config dict (possibly empty — callers fall back to defaults)."""
    cfg, mtime = {}, 0
    try:
        mtime = os.path.getmtime(CONFIG_CACHE)
        with open(CONFIG_CACHE) as f:
            blob = json.load(f)
        if isinstance(blob, dict) and blob.get("ok"):
            cfg = blob.get("config", {}) or {}
    except Exception:
        pass
    if not cfg or now - mtime > CONFIG_REFRESH_SECS:
        spawn_refresh()
    return cfg


def demoday_color(secs_left):
    """Warmer as Demo Day nears: green > 30d, yellow > 7d, orange > 1d, red <= 1d."""
    days = secs_left / 86400
    if days <= 1:
        return RED
    if days <= 7:
        return ORANGE
    if days <= 30:
        return YELLOW
    return GREEN


def countdown_fmt(secs):
    """'98d 14h', '14h 03m', or '12m' — two units, coarsest first."""
    secs = int(secs)
    d, h, m = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
    if d >= 1:
        return f"{d}d {h}h"
    if h >= 1:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def demoday_segment(now, cfg):
    """Live countdown to Demo Day. Counts down, flips to 'It's Demo Day!' for the
    day, then returns None so the segment disappears once the date is well past."""
    if DEMODAY_DISABLED:
        return None
    # Founder build counts to Speedrun Demo Day; Alpha stays internal-only.
    cohort = (cfg.get("cohorts") or {}).get("speedrun") or {}
    epoch = parse_iso(cohort.get("demo_day") or DEFAULT_DEMO_DAY)
    if not epoch:
        return None
    milestone = cohort.get("milestone") or DEFAULT_MILESTONE
    diff = epoch - now
    if diff <= -LIVE_WINDOW_SECS:
        return None  # well past — revert to normal vitals
    if diff <= 0:
        live = "It's {}!".format(milestone)
        return f"🏁 {color(live, GREEN)}"
    body = f"{color(milestone, GOLD)} {color(countdown_fmt(diff), demoday_color(diff))}"
    return f"🏁 {body}"


def _semver_newer(a, b):
    """True if version string a is newer than b (best-effort dotted-int compare)."""
    def parts(v):
        out = []
        for chunk in str(v).split("."):
            num = "".join(c for c in chunk if c.isdigit())
            out.append(int(num) if num else 0)
        return out
    pa, pb = parts(a), parts(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return pa > pb


def version_segment(cfg):
    """A quiet, clickable nudge when a newer status line has shipped."""
    latest = (cfg.get("statusline") or {}).get("latest_version")
    if not latest or not _semver_newer(latest, VERSION):
        return None
    return link(REPO_URL, color("⬆ update", YELLOW))


def brand_segment():
    """Clickable branded link to speedrun — zero auth, shown for everyone."""
    if BRAND_DISABLED:
        return None
    return link(BRAND_URL, f"{color(BRAND, GOLD)} {color('↗', DIM)}")


def visible_len(s):
    """Length of a string ignoring ANSI/OSC escape sequences."""
    out, i, n = 0, 0, len(s)
    while i < n:
        c = s[i]
        if c == "\033":
            # CSI (\033[ ... letter) or OSC (\033] ... BEL)
            if i + 1 < n and s[i + 1] == "[":
                i += 2
                while i < n and not s[i].isalpha():
                    i += 1
                i += 1
            elif i + 1 < n and s[i + 1] == "]":
                i += 2
                while i < n and s[i] != "\a":
                    i += 1
                i += 1
            else:
                i += 1
        else:
            out += 1
            i += 1
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("")
        return

    ws = data.get("workspace", {}) or {}
    cwd = ws.get("current_dir") or data.get("cwd") or os.getcwd()
    ctx = data.get("context_window", {}) or {}
    cost = data.get("cost", {}) or {}
    rl = data.get("rate_limits", {}) or {}
    now = time.time()
    cfg = load_config(now)

    # segments: (priority, text). Higher priority survives truncation.
    segs = []

    # model
    model = (data.get("model", {}) or {}).get("display_name", "?")
    segs.append((100, color(model, CYAN)))

    # effort level (only present when the model supports it)
    eff = (data.get("effort", {}) or {}).get("level")
    if eff:
        eff_color = {"low": DIM, "medium": BLUE, "high": CYAN,
                     "xhigh": MAGENTA, "max": ORANGE}.get(eff, CYAN)
        segs.append((95, color(f"⚡{eff}", eff_color)))

    # directory (repo name when known, else folder); flag worktrees
    repo = ws.get("repo", {}) or {}
    dirname = repo.get("name") or os.path.basename(cwd.rstrip("/")) or "/"
    wt = (data.get("worktree", {}) or {}).get("name") or ws.get("git_worktree")
    label = f"{dirname}⑂{wt}" if wt else dirname
    segs.append((90, color(label, BLUE)))

    # git
    g = git_info(cwd, data.get("session_id", "x"))
    if g.get("branch"):
        flags = ""
        if g.get("staged"):
            flags += color(f" +{g['staged']}", GREEN)
        if g.get("modified"):
            flags += color(f" ~{g['modified']}", YELLOW)
        if g.get("untracked"):
            flags += color(f" ?{g['untracked']}", DIM)
        ab = ""
        if g.get("ahead"):
            ab += color(f" ↑{g['ahead']}", CYAN)
        if g.get("behind"):
            ab += color(f" ↓{g['behind']}", MAGENTA)
        clean = "" if (flags or ab) else color(" ✓", GREEN)
        segs.append((80, f"{color(g['branch'], DIM)}{flags}{ab}{clean}"))

    # context window usage with bar
    pct = ctx.get("used_percentage")
    if pct is not None:
        pct = int(pct)
        c = util_color(pct)
        width = 8
        filled = round(pct * width / 100)
        bar = "▓" * filled + "░" * (width - filled)
        size = ctx.get("context_window_size", 0) or 0
        used_tok = ctx.get("total_input_tokens", 0) or 0
        tag = ""
        if used_tok > 0 and size > 0:
            tag = color(f" ({kfmt(used_tok)}/{kfmt(size)})", DIM)
        segs.append((70, f"{color(bar, c)} {color(f'{pct}%', c)}{tag}"))

    # 🏁 Demo Day countdown (the headline — clickable brand link sits beside it)
    demoday = demoday_segment(now, cfg)
    if demoday:
        segs.append((65, demoday))

    # speedrun link
    brand = brand_segment()
    if brand:
        segs.append((60, brand))

    # cost
    usd = cost.get("total_cost_usd")
    if usd:
        segs.append((50, color(f"${usd:.2f}", DIM)))

    # pr (clickable in iTerm2 via OSC 8)
    pr = data.get("pr", {}) or {}
    if pr.get("number"):
        state = pr.get("review_state")
        sc = {"approved": GREEN, "changes_requested": RED,
              "pending": YELLOW, "draft": DIM}.get(state, MAGENTA)
        txt = color(f"PR#{pr['number']}", sc)
        if pr.get("url"):
            txt = f"\033]8;;{pr['url']}\a{txt}\033]8;;\a"
        segs.append((45, txt))

    # session duration
    dur = cost.get("total_duration_ms")
    if dur:
        s = dur // 1000
        h, m = s // 3600, (s % 3600) // 60
        t = f"{h}h{m:02d}m" if h else f"{m}m"
        segs.append((40, color(t, DIM)))

    # rate limits (Pro/Max only — absent otherwise), with reset countdown
    for prio, rlabel, key in ((35, "5h", "five_hour"), (34, "7d", "seven_day")):
        win = rl.get(key, {}) or {}
        p = win.get("used_percentage")
        if p is not None:
            seg = f"{DIM}{rlabel}{RESET} {color(f'{round(p)}%', util_color(p))}"
            rem = until(win.get("resets_at"), now)
            if rem:
                seg += f" {DIM}·{rem}{RESET}"
            segs.append((prio, seg))

    # update nudge (quiet; clickable to the repo)
    upd = version_segment(cfg)
    if upd:
        segs.append((32, upd))

    # ── assemble: core segments always shown; extras fill the width ──
    # Core (model/dir/git/context, priority >= 70) is kept unconditionally;
    # lower-priority extras are added by priority only while they fit, so the
    # line never wraps on a narrow terminal.
    cols = int(os.environ.get("COLUMNS", 0) or 0)
    budget = cols - 2 if cols else 10**9  # leave a little breathing room
    sep_w = 3  # " · "

    chosen = [(p, t) for p, t in segs if p >= 70]
    used = sum(visible_len(t) for _, t in chosen) + sep_w * (len(chosen) - 1)
    for prio, text in sorted((s for s in segs if s[0] < 70), key=lambda s: -s[0]):
        w = visible_len(text) + sep_w
        if used + w > budget:
            continue
        chosen.append((prio, text))
        used += w

    # display in priority-descending order
    chosen.sort(key=lambda s: -s[0])
    print(SEP.join(text for _, text in chosen))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--refresh":
        refresh_config()
    else:
        main()
