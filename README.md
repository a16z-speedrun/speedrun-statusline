# speedrun-statusline

A [Claude Code](https://claude.com/claude-code) status line for Speedrun founders — a **live countdown to Demo Day** sitting alongside the session vitals you actually want while pairing with Claude.

```
Opus · my-app · main +2~1 · ▓▓▓░░░░░ 31% (62k/200k) · 🏁 Demo Day 98d 14h · speedrun ↗ · $0.42
```

As Demo Day nears the countdown warms from green → gold → red. On the day it flips to **🏁 It's Demo Day!**, and once it's past it quietly disappears — your line reverts to its normal vitals.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/a16z-speedrun/speedrun-statusline/main/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/a16z-speedrun/speedrun-statusline.git
cd speedrun-statusline
./install.sh
```

Either way it copies `statusline.py` to `~/.claude/speedrun-statusline.py` and wires the `statusLine` block into `~/.claude/settings.json` (your other settings are preserved; any existing `statusLine` is backed up to `settings.json.statusLine.bak`). Open a new Claude Code session — or wait ~10s — and it appears.

## What it shows

| Segment | Meaning |
|---|---|
| `Opus` | Active model |
| `⚡high` | Reasoning effort (when the model exposes it) |
| `my-app` | Current repo / directory (`⑂` marks a git worktree) |
| `main +2~1 ?3 ↑1` | Branch, then staged `+`, modified `~`, untracked `?`, ahead `↑` / behind `↓`. `✓` when clean |
| `▓▓▓░░░░░ 31% (62k/200k)` | Context-window usage, colored by pressure |
| **`🏁 Demo Day 98d 14h`** | **Live countdown to Speedrun Demo Day**, warming as it approaches |
| **`speedrun ↗`** | Clickable link to [speedrun.a16z.com](https://speedrun.a16z.com/) |
| `$0.42` | Session cost |
| `PR#123` | Current PR, colored by review state, clickable |
| `5h23m` | Session duration |
| `5h 23% · 1h48m` | Pro/Max rate-limit windows with reset countdown |
| `⬆ update` | Shown only when a newer version of this status line has shipped |

Segments degrade gracefully — anything unavailable is simply omitted — and on a narrow terminal the lowest-priority segments drop first so the line never wraps.

## How the countdown stays current

The Demo Day date isn't hard-coded into your install — it lives in [`speedrun.json`](./speedrun.json) in this repo. The status line fetches it **out of band** (a detached background refresh, cached to `~/.claude/speedrun-statusline.json`, checked a few times a day) and reads the cache instantly, so the network never blocks your prompt. A baked-in default keeps the countdown working on a fresh or offline install until the first fetch lands.

That means **the date can be re-pointed for the next cohort by editing one file here** — every install picks it up within hours, no reinstall. The same file carries `latest_version`, which drives the `⬆ update` nudge when the script itself changes.

## Configuration

Environment variables (set in your shell profile):

| Variable | Effect |
|---|---|
| `SR_STATUSLINE_NO_DEMODAY=1` | Hide the Demo Day countdown |
| `SR_STATUSLINE_NO_BRAND=1` | Hide the `speedrun ↗` link |
| `SR_STATUSLINE_CONFIG_URL` | Override the remote config URL (advanced) |

## Maintainers

To re-date for the next cohort: edit `speedrun.json` (`demo_day`, `milestone`, `cohort`) and commit. To ship a script change: bump `VERSION` **and** `latest_version` in `speedrun.json` so installs surface the `⬆ update` nudge.
