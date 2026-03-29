# Claude Code ROI Calculator

Generate an ROI report from your Claude Code sessions. Run one command, automatically get a shareable HTML report of time saved and value created.

[![License](https://img.shields.io/github/license/AlexanderBZ/claude-code-roi-calculator)](LICENSE) [![Stars](https://img.shields.io/github/stars/AlexanderBZ/claude-code-roi-calculator)](https://github.com/AlexanderBZ/claude-code-roi-calculator)

![cover](cover.png)

## Install

Inside a Claude Code instance, run the following commands:

**Step 1: Add the marketplace**

```
/plugin marketplace add AlexanderBZ/claude-code-roi-calculator
```

**Step 2: Install the plugin**

```
/plugin install roi-calculator
```

Done! Run `/roi-calculator:generate` in any project to generate your ROI report.

---

## What is Claude Code ROI Calculator?

ROI Calculator reads your Claude Code session history and generates a clear, shareable HTML report showing the time you saved, the dollar value created, and where AI is accelerating your work most.

| What You Get              | Why It Matters                                                       |
| ------------------------- | -------------------------------------------------------------------- |
| **Time saved**            | Per-session estimate of what the task would have taken without AI    |
| **Acceleration multiple** | How much faster you worked with Claude vs. manually                  |
| **Dollar value**          | Time saved × hourly rate (default: $75/hr)                           |
| **Global insights**       | High-ROI areas, low-ROI patterns, and optimization suggestions       |
| **HTML report**           | Saved locally to `~/.claude/roi-data/` — shareable with stakeholders |
| **Zero manual input**     | Reads directly from your Claude Code session traces                  |
| **Local processing**      | All session data stays on-device; nothing leaves your machine        |

### How It Works

```
/roi-calculator:generate
       ↓
Python CLI scans ~/.claude/projects/**/*.jsonl
       ↓
Filters low-signal sessions (<2 user messages, <1 min duration, agent/subagent sessions)
       ↓
Haiku call per session: splits user messages into individual task units
       ↓
Haiku call per task: estimates manual time, task type, confidence, reasoning
       ↓
Computes ROI metrics: time saved, acceleration multiple, dollar value
       ↓
Haiku call over all tasks: generates high-ROI areas, low-ROI patterns, suggestions
       ↓
HTML report saved to ~/.claude/roi-data/report-YYYY-MM-DD.html
```

**Key details:**

- LLM (Haiku-tier) handles estimation and insight generation only
- Low-cost model used for all LLM calls to keep operating cost minimal
- All data stays local; no session content is sent to external services

---

## Output

The report includes three sections:

**Summary dashboard**

- Total time saved across all sessions
- Total value created (at your hourly rate)
- Overall acceleration multiple

**Task table**

- Per-session breakdown: AI time, estimated manual time, time saved, acceleration, dollar value

**Insights**

- High-ROI areas (where Claude accelerates you most)
- Low-ROI patterns (where AI adds less value)
- Optimization suggestions

Report is saved to `~/.claude/roi-data/report-YYYY-MM-DD.html`.

---

## Requirements

- **Python 3.10+**
- Claude Code with skill support

---

## Commands

| Command                    | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `/roi-calculator:generate` | Generate an ROI report from your Claude sessions |

---

## Privacy

**All processing is local:**

- Sessions are read from your local `~/.claude/projects/` directory
- Python CLI runs entirely on-device
- No session data is sent anywhere beyond your local Claude instance
- Report is saved locally to `~/.claude/roi-data/`

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
