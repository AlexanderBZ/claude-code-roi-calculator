# Claude Code ROI Calculator

Generate an ROI report from your Claude Code sessions. Run one command, automatically get an interactive HTML report showing time saved, dollar value created, and actionable insights on where AI is—and isn't—working for you.

[![License](https://img.shields.io/github/license/AlexanderBZ/claude-code-roi-calculator)](LICENSE) [![Stars](https://img.shields.io/github/stars/AlexanderBZ/claude-code-roi-calculator)](https://github.com/AlexanderBZ/claude-code-roi-calculator)

<video src="roi-calculator-video-mini.mp4" autoplay loop muted playsinline></video>

## Install

Inside a Claude Code instance, run:

**Step 1: Add the marketplace**

```
/plugin marketplace add AlexanderBZ/claude-code-roi-calculator
```

**Step 2: Install the plugin**

```
/plugin install roi-calculator
```

**Step 3: Install the Python dependency**

```
pip install anthropic
```

Done! Run `/roi-calculator:generate` in any project to generate your report.

---

## What is Claude Code ROI Calculator?

ROI Calculator reads your Claude Code session history and generates a self-contained interactive HTML report answering the question every developer should ask: _Is Claude Code actually saving me time?_

| What You Get                | Why It Matters                                       |
| --------------------------- | ---------------------------------------------------- |
| **Time saved per session**  | Estimates what each task would have taken without AI |
| **Dollar value**            | Time saved × your hourly rate                        |
| **Net ROI**                 | Value generated minus the $100/mo subscription cost  |
| **Category breakdown**      | Which task types have the highest and lowest ROI     |
| **Friction patterns**       | What's destroying your ROI and how to fix it         |
| **Recommendations**         | Specific, actionable prompts and workflow changes    |
| **Interactive HTML report** | Sortable session table, charts, expandable rows      |
| **Local processing**        | All session data stays on-device                     |

---

## Usage

```
/roi-calculator:generate
```

On first run, you'll be asked for your hourly rate (stored locally, never shared).

### Flags

| Flag                 | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `--rate 200`         | Override hourly rate for this run (does not update saved config)    |
| `--reset-cache`      | Delete all cached ROI facets and re-analyze everything from scratch |
| `--since 2025-01-01` | Only analyze sessions on or after this date                         |

**Examples:**

```
/roi-calculator:generate --rate 200
/roi-calculator:generate --since 2025-03-01
/roi-calculator:generate --reset-cache
```

---

## How It Works

```
/roi-calculator:generate
       ↓
Load config (hourly rate) — prompt on first run, cached after
       ↓
Scan ~/.claude/projects/**/*.jsonl
Filter: exclude agent sessions, <2 user messages, <1 min duration
       ↓
[Per session, up to 50 new] Haiku call: extract ROI facets
  → task category, outcome, estimated manual effort, friction observed
  → cached to ~/.claude/usage-data/roi-facets/<session-id>.json
       ↓
Score each session locally (no LLM)
  → time saved = estimated manual − actual duration
  → dollar value = time saved × hourly rate
  → verdict: positive / neutral / negative
       ↓
Aggregate across all sessions
  → overall verdict, by-category stats, top friction types
       ↓
[4 parallel Haiku calls] Analysis prompts
  → ROI narrative, category analysis, friction analysis, recommendations
       ↓
[1 Haiku call] Executive summary
       ↓
Render interactive HTML report → ~/.claude/usage-data/roi-report.html
```

**Key details:**

- All LLM calls use `claude-haiku-4-5` to keep cost minimal
- Facets are cached — subsequent runs only process new sessions
- Long transcripts (>30k chars) are summarized before analysis
- Manual effort outliers are capped at 10× session duration

---

## Report Sections

1. **Executive Summary** — verdict line, net dollar value, driving/hurting ROI cards
2. **Key Metrics** — time saved, value generated, net ROI, session counts, ROI %
3. **ROI Over Time** — cumulative value chart (Chart.js)
4. **Session Breakdown** — sortable, expandable table with every session
5. **Category Breakdown** — per-category bar chart and best/worst analysis
6. **ROI Narrative** — honest plain-English assessment of your overall ROI
7. **Friction Patterns** — top patterns destroying ROI with specific fixes
8. **Recommendations** — quick wins with copyable prompts + strategic shifts

Report is saved to `~/.claude/usage-data/roi-report.html`.

---

## Requirements

- **Python 3.10+**
- **`anthropic` Python package** (`pip install anthropic`)
- **`ANTHROPIC_API_KEY`** environment variable set
- Claude Code with plugin support

---

## Privacy

**All processing is local:**

- Sessions are read from your local `~/.claude/projects/` directory
- LLM calls go only to Anthropic's API (same as your normal Claude Code usage)
- No session data is sent to any third-party service
- Config and cache are stored locally in `~/.claude/usage-data/`

---

## License

MIT — see [LICENSE](LICENSE)

---

## Star History

<a href="https://www.star-history.com/?repos=AlexanderBZ%2Fclaude-code-roi-calculator&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=AlexanderBZ/claude-code-roi-calculator&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=AlexanderBZ/claude-code-roi-calculator&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=AlexanderBZ/claude-code-roi-calculator&type=date&legend=top-left" />
 </picture>
</a>
