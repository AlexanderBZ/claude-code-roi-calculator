---
name: generate
description: Generate an ROI report analyzing the value of your Claude Code sessions. Calculates time saved, dollar value, and provides actionable insights to improve your Claude Code ROI.
disable-model-invocation: true
argument-hint: "[--rate AMOUNT] [--reset-cache] [--since YYYY-MM-DD]"
---

# ROI Report Generator

Generate a comprehensive ROI analysis of your Claude Code sessions.

## Script layout

This skill now uses a split Python implementation under `scripts/`:

- `roi.py` — main CLI entrypoint; always run this file
- `sessions.py` — session discovery and filtering
- `analysis.py` — Claude subprocess summarization/facet extraction/analysis
- `scoring.py` — ROI scoring and aggregation
- `report.py` — HTML report rendering
- `constants.py` — shared paths and configuration constants

Do not try to run the helper modules directly unless you are explicitly debugging the implementation. For normal usage, invoke only `roi.py`.

## Steps

**1. Check for existing config:**

```bash
cat ~/.claude/usage-data/roi-config.json 2>/dev/null
```

**2. Handle missing config:**

If the config file does not exist AND `$ARGUMENTS` does not already contain `--rate`:

- Ask the user: _"What's your approximate hourly rate in USD? (e.g. 150)"_
- Wait for their response, then add `--rate <their_answer>` to the arguments when running the script in step 3.

**3. Run the ROI calculator:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/roi.py" $ARGUMENTS
```

The script coordinates the full pipeline by importing the helper modules above.

**4. Open the report** once the script prints `Report saved`:

```bash
open ~/.claude/usage-data/roi-report.html
```

If the script fails with a message indicating the `claude` CLI is missing or unauthenticated, stop and tell the user they need a working local Claude Code CLI session before this skill can complete.

## Available flags

| Flag                 | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `--rate <amount>`    | Override hourly rate for this run (does not update saved config)    |
| `--reset-cache`      | Delete all cached ROI facets and re-analyze everything from scratch |
| `--since YYYY-MM-DD` | Only analyze sessions on or after this date                         |

## Example usage

- `/generate` — Run with saved config
- `/generate --rate 200` — Run with a different rate
- `/generate --since 2025-01-01` — Analyze only sessions from 2025 onward
- `/generate --reset-cache` — Force re-analysis of all sessions

## Expected outputs

- Config: `~/.claude/usage-data/roi-config.json`
- Cached facets: `~/.claude/usage-data/roi-facets/<session-id>.json`
- Report: `~/.claude/usage-data/roi-report.html`
