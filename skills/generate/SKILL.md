---
name: generate
description: Generate an ROI report analyzing the value of your Claude Code sessions. Calculates time saved, dollar value, and provides actionable insights to improve your Claude Code ROI.
disable-model-invocation: true
argument-hint: "[--rate AMOUNT] [--reset-cache] [--since YYYY-MM-DD]"
---

# ROI Report Generator

Generate a comprehensive ROI analysis of your Claude Code sessions.

## Steps

**1. Check for existing config:**

```bash
cat ~/.claude/usage-data/generate-config.json 2>/dev/null
```

**2. Handle missing config:**

If the config file does not exist AND `$ARGUMENTS` does not already contain `--rate`:

- Ask the user: _"What's your approximate hourly rate in USD? (e.g. 150)"_
- Wait for their response, then add `--rate <their_answer>` to the arguments when running the script in step 3.

**3. Run the ROI calculator:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/generate.py" $ARGUMENTS
```

**4. Open the report** once the script prints "Report saved":

```bash
open ~/.claude/usage-data/generate-report.html
```

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
