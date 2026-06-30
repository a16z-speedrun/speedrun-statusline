# CLAUDE.md — speedrun-statusline

A [Claude Code](https://claude.com/claude-code) status line for Speedrun founders: core session vitals plus a live **countdown to Demo Day**. Public repo; the new-tab extension ([`sr-chrome-extension`](https://github.com/a16z-speedrun/sr-chrome-extension)) links founders here to install it.

**Single Python file, stdlib only, no build/deps.** `statusline.py` reads Claude Code's session JSON on stdin and prints one line to stdout. See the [README](./README.md) for the user-facing view; this file is the maintainer's view.

## Files

| File | Role |
|---|---|
| `statusline.py` | The whole status line. Also self-invokes with `--refresh` to fetch config. |
| `install.sh` | Copies the script to `~/.claude/speedrun-statusline.py` and merges a `statusLine` block into `~/.claude/settings.json`. Works from a clone **or** `curl … | bash`. |
| `VERSION` | The baked-in self-version. |

## Load-bearing conventions & gotchas

- **Segments are `(priority, text)`; the line never wraps.** Core segments (priority ≥ 70: model, dir, git, context) always render; lower-priority extras are added by priority only while they fit the `COLUMNS` budget. New segments pick a priority deliberately and must compute their *visible* width via `visible_len()` (which skips ANSI/OSC escapes).
- **Network never blocks the render.** Config is fetched out of band: a detached `python … --refresh` subprocess writes `~/.claude/speedrun-statusline.json`; the render reads that cache instantly and only spawns a refresh when it's missing/stale (~6h TTL). Don't add a blocking fetch to the render path.
- **There's always a baked-in fallback.** `DEFAULT_DEMO_DAY` keeps the countdown working on a fresh or offline install before the first fetch lands. Keep it current-ish.
- **The countdown is three-state and self-clearing**: counts down → `It's Demo Day!` for `LIVE_WINDOW_SECS` after the start → returns `None` (segment disappears) once well past. Don't make it render a stale/negative value.

## Dates & versioning live in the shared config — NOT here

The date and the update-nudge version come from [`a16z-speedrun/speedrun-config`](https://github.com/a16z-speedrun/speedrun-config) (`cohort.json`), shared with the extension. `statusline.py` reads `cohorts.speedrun` for the date and `statusline.latest_version` for the `⬆ update` nudge.

- **Re-date for the next cohort:** edit `cohorts.speedrun` in `speedrun-config`. Installs pick it up within the cache TTL — no reinstall.
- **Ship a script change:** bump `VERSION` here **and** `statusline.latest_version` in `speedrun-config`, so installs surface the `⬆ update` nudge (the nudge fires only when remote `latest_version` is newer than the installed `VERSION`). Code itself is NOT auto-pulled — the nudge prompts a manual re-install (deliberate: no auto-exec of pulled code).
- The founder build counts only to **Speedrun Demo Day**; Alpha stays internal-only here even though `cohort.json` carries it.

## Testing

No framework. Pipe a session JSON in:

```bash
echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":31}}' | python3 statusline.py
COLUMNS=60 echo '…' | python3 statusline.py   # confirm extras drop, core stays
python3 statusline.py --refresh && cat ~/.claude/speedrun-statusline.json   # exercise the live fetch
```

Env toggles: `SR_STATUSLINE_NO_DEMODAY=1`, `SR_STATUSLINE_NO_BRAND=1`, `SR_STATUSLINE_CONFIG_URL=…`.

## Commits (sr007 convention)

No `Co-Authored-By:` lines. Use `-`/`--`, never em/en dashes.
