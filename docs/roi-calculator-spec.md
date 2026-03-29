# Claude Code `/roi` Command — Implementation Spec

## Overview

Build a `/roi` slash command for Claude Code that analyzes session logs, estimates the time value of each session, and generates an interactive HTML report showing whether Claude Code is delivering positive or negative ROI for the developer.

**Command:** `/roi`
**Description:** `"Generate an ROI report analyzing the value of your Claude Code sessions"`
**Output:** `~/.claude/usage-data/roi-report.html`

### Core ROI Model

For each session:

1. LLM estimates **manual effort** — how long the same task would take a competent developer without AI assistance
2. Compare against **actual session duration**
3. **Time saved** = estimated manual effort − actual duration (can be negative)
4. **Value** = time saved × developer hourly rate
5. **ROI verdict per session**: positive (saved time), negative (wasted time), or neutral (wash)

Aggregate across all sessions to produce an overall ROI verdict.

---

## Configuration

On first run, prompt the user for their hourly rate and cache it:

```
What's your approximate hourly rate (used to calculate dollar value of time saved)?
Enter a number in USD (e.g. 150): _
```

Store in `~/.claude/usage-data/roi-config.json`:

```json
{
  "hourly_rate_usd": 150,
  "currency": "USD",
  "configured_at": "2025-01-15T10:00:00Z"
}
```

On subsequent runs, skip the prompt and use the cached value. Users can override with `/roi --rate 200`.

---

## File System Paths

| Path                                                | Purpose                       |
| --------------------------------------------------- | ----------------------------- |
| `~/.claude/projects/<hash>/`                        | Raw session log files         |
| `~/.claude/usage-data/roi-facets/<session-id>.json` | Cached per-session ROI facets |
| `~/.claude/usage-data/roi-config.json`              | Developer hourly rate config  |
| `~/.claude/usage-data/roi-report.html`              | Final generated report        |

Use a **separate cache directory** (`roi-facets/`) from the insights command (`facets/`) so the two commands don't collide.

---

## Pipeline Overview

1. Load config (hourly rate)
2. Filter session logs and extract metadata
3. Summarize long transcripts (if needed)
4. Extract ROI facets per session via Claude Code subprocess
5. Score each session (time saved, dollar value, verdict)
6. Aggregate and run 4 analysis prompts
7. Generate executive summary
8. Render interactive HTML report

---

## Stage 1: Session Filtering & Metadata Extraction

Same filtering rules as the insights command. Load all session logs from `~/.claude/projects/`. Exclude:

- Filenames starting with `agent-`
- Internal/facet-extraction sessions
- Fewer than 2 user messages
- Duration under 1 minute

Extract per-session metadata:

```typescript
interface SessionMetadata {
  session_id: string;
  start_time: string; // ISO timestamp
  duration_minutes: number; // ACTUAL time spent in session
  user_message_count: number;
  input_tokens: number;
  output_tokens: number;
  tool_counts: Record<string, number>;
  languages: string[];
  git_commits: number;
  user_interruptions: number; // proxy for friction
  tool_errors: number;
  lines_added: number;
  lines_removed: number;
  files_modified: number;
  first_prompt: string;
  transcript_length: number; // chars, used to decide if summarization needed
}
```

---

## Stage 2: Transcript Summarization (Conditional)

Identical to insights command. If `transcript_length > 30,000` characters, chunk into 25,000-character segments and summarize each before ROI facet extraction.

**Summarization prompt per chunk:**

```
Summarize this portion of a Claude Code session transcript. Focus on:
1. What the user asked for and what was ultimately accomplished
2. Concrete outputs: files changed, code written, bugs fixed, configs updated
3. Any significant back-and-forth, retries, or abandoned attempts
4. Whether the task succeeded or failed

Keep it concise — 3-5 sentences. Preserve specific details like file names,
error messages, and task descriptions.

TRANSCRIPT CHUNK:
<chunk text>
```

---

## Stage 3: ROI Facet Extraction (Per-Session Claude Code Subprocess Call)

This is the core of the ROI model. A Claude Code subprocess reads the session and estimates what the work would have taken manually.

**Execution:** invoke the local Claude Code CLI via subprocess, e.g. `claude --print`
**Model selection:** use the developer's normal Claude Code account/configuration rather than hardcoding an API model name
**Max output tokens:** target roughly 2048 tokens worth of response text
**Max new sessions per run:** 50
**Caching:** Save to `~/.claude/usage-data/roi-facets/<session-id>.json`. Skip if cached.

Implementation note: the command should shell out to Claude Code as a subprocess, pass the prompt on stdin, and capture stdout/stderr for parsing and error handling. Do not depend on the Anthropic SDK or direct Claude API credentials for this workflow.

### Prompt

```
You are analyzing a Claude Code session to estimate its ROI for the developer.

Your job is to estimate how long this task would have taken a competent mid-senior
developer working WITHOUT any AI assistance, then compare that to the actual session
duration to determine time saved or lost.

ACTUAL SESSION DURATION: <duration_minutes> minutes

GUIDELINES FOR ESTIMATING MANUAL EFFORT:

- Base your estimate on what a skilled developer would need to do the same work manually:
  searching docs, reading source, writing code, debugging, testing
- For debugging tasks: manual debugging is typically 3-8x longer than AI-assisted
- For boilerplate/scaffolding: manual is typically 2-5x longer
- For understanding unfamiliar codebases: manual is typically 4-10x longer
- For simple edits or configs a developer already knows: manual effort ≈ session time (no gain)
- For failed sessions (task not achieved): manual effort = 0, Claude cost = session duration (negative ROI)
- For sessions where Claude clearly went in circles or required excessive correction:
  reduce the manual estimate accordingly — the session was inefficient

OUTCOME SIGNALS TO LOOK FOR:
- Success signals: git commits, explicit user satisfaction ("thanks", "perfect", "works"),
  task completion without major retries
- Failure signals: "that's wrong", "never mind", "I'll do it myself", abandoned mid-task,
  no meaningful output after many exchanges
- Mixed signals: partial completion, user took over partway through

SESSION:
<session transcript or summarized transcript>

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "task_description": "1-2 sentences describing what was attempted",
  "task_category": "debug_investigate | implement_feature | fix_bug | write_script_tool | refactor_code | configure_system | create_pr_commit | analyze_data | understand_codebase | write_tests | write_docs | deploy_infra | warmup_minimal",
  "outcome": "fully_achieved | mostly_achieved | partially_achieved | not_achieved | unclear",
  "outcome_evidence": "1 sentence citing specific evidence from the transcript",
  "estimated_manual_minutes": <number>,
  "manual_estimate_rationale": "2-3 sentences explaining your estimate. What would the developer have had to do manually? What made it faster or slower with AI?",
  "efficiency_rating": "highly_efficient | efficient | neutral | inefficient | counterproductive",
  "efficiency_detail": "1 sentence on what drove efficiency or inefficiency in this session",
  "friction_observed": ["list", "of", "friction", "types"],
  "value_delivered": "none | low | medium | high | exceptional",
  "brief_summary": "One sentence: what happened and the ROI implication"
}
```

### Efficiency Rating Definitions

| Rating              | Meaning                                               |
| ------------------- | ----------------------------------------------------- |
| `highly_efficient`  | Claude saved 60%+ of estimated manual time            |
| `efficient`         | Claude saved 30–60% of estimated manual time          |
| `neutral`           | Time saved within ±20% of session duration            |
| `inefficient`       | Session took longer or caused more work than it saved |
| `counterproductive` | Task failed, was abandoned, or left things worse      |

### Friction Types (for `friction_observed` array)

- `excessive_retries` — Claude needed many correction attempts
- `misunderstood_task` — Claude solved the wrong problem
- `hallucinated_api` — Claude used non-existent functions or APIs
- `scope_creep` — Claude changed more than asked
- `context_loss` — Claude forgot earlier decisions in long session
- `tool_failures` — Bash/Edit/Read tool errors
- `user_pivoted` — User changed direction mid-session
- `environment_issues` — Local env problems unrelated to Claude

---

## Stage 4: Per-Session ROI Scoring (Local Computation, No Subprocess Call)

After facets are extracted, compute scores locally — no additional Claude subprocess calls are needed for this stage.

```typescript
interface SessionROIScore {
  session_id: string;
  start_time: string;
  task_description: string;
  task_category: string;
  outcome: string;
  actual_minutes: number;
  estimated_manual_minutes: number;
  time_saved_minutes: number; // estimated_manual - actual (can be negative)
  time_saved_hours: number; // time_saved_minutes / 60
  dollar_value: number; // time_saved_hours × hourly_rate
  roi_verdict: "positive" | "negative" | "neutral";
  efficiency_rating: string;
  efficiency_detail: string;
  friction_observed: string[];
  value_delivered: string;
  brief_summary: string;
}
```

**Scoring rules:**

```typescript
function scoreSession(
  metadata: SessionMetadata,
  facet: ROIFacet,
  hourlyRate: number,
): SessionROIScore {
  const timeSavedMinutes =
    facet.estimated_manual_minutes - metadata.duration_minutes;
  const timeSavedHours = timeSavedMinutes / 60;
  const dollarValue = timeSavedHours * hourlyRate;

  let roiVerdict: "positive" | "negative" | "neutral";
  if (timeSavedMinutes > 5) {
    roiVerdict = "positive";
  } else if (timeSavedMinutes < -5) {
    roiVerdict = "negative";
  } else {
    roiVerdict = "neutral";
  }

  // Override: counterproductive sessions are always negative
  if (facet.efficiency_rating === "counterproductive") {
    roiVerdict = "negative";
  }

  // Override: warmup/minimal sessions are always neutral
  if (facet.task_category === "warmup_minimal") {
    roiVerdict = "neutral";
  }

  return {
    ...facet,
    ...metadata,
    timeSavedMinutes,
    timeSavedHours,
    dollarValue,
    roiVerdict,
  };
}
```

---

## Stage 5: Aggregation

Compute aggregate stats across all scored sessions:

```typescript
interface AggregatedROI {
  // Counts
  total_sessions: number;
  positive_sessions: number;
  negative_sessions: number;
  neutral_sessions: number;

  // Time
  total_actual_hours: number;
  total_estimated_manual_hours: number;
  total_time_saved_hours: number;
  average_time_saved_per_session_minutes: number;

  // Money
  hourly_rate: number;
  total_dollar_value: number; // can be negative
  average_dollar_value_per_session: number;
  subscription_cost_usd: number; // hardcoded: $100/month (Claude Code Pro)
  net_roi_usd: number; // total_dollar_value - subscription_cost

  // Verdict
  overall_verdict:
    | "strongly_positive"
    | "positive"
    | "neutral"
    | "negative"
    | "strongly_negative";
  roi_percentage: number; // (time_saved / actual_time) × 100

  // Breakdowns
  by_category: Record<
    string,
    {
      sessions: number;
      avg_time_saved_minutes: number;
      avg_dollar_value: number;
      positive_rate: number; // % of sessions that were positive ROI
    }
  >;
  by_efficiency: Record<string, number>; // count per efficiency_rating
  by_outcome: Record<string, number>;
  top_friction_types: [string, number][]; // sorted by frequency

  // Date range
  date_range: { start: string; end: string };
  active_days: number;

  // Samples
  best_sessions: SessionROIScore[]; // top 3 by dollar_value
  worst_sessions: SessionROIScore[]; // bottom 3 by dollar_value
  session_summaries: string[]; // brief_summary from each facet, up to 50
}
```

**Overall verdict thresholds:**

| Verdict             | Condition                                       |
| ------------------- | ----------------------------------------------- |
| `strongly_positive` | >60% sessions positive AND roi_percentage > 40% |
| `positive`          | >50% sessions positive OR roi_percentage > 20%  |
| `neutral`           | roi_percentage between -10% and +20%            |
| `negative`          | roi_percentage < -10% OR >40% sessions negative |
| `strongly_negative` | >60% sessions negative OR roi_percentage < -30% |

---

## Stage 6: Claude Code Analysis Prompts (4 Subprocess Calls, Run in Parallel)

**Execution:** run 4 Claude Code subprocess calls in parallel
**Model selection:** use the developer's configured Claude Code environment
**Max output tokens:** target roughly 4096 tokens per prompt

Each prompt receives the full `AggregatedROI` JSON.

---

### 6.1 ROI Narrative

```
You are analyzing Claude Code ROI data for an individual developer.
Write an honest, direct assessment of whether Claude Code is delivering value.
Use second person ("you"). Don't be promotional — if the data shows negative ROI,
say so clearly. If it's nuanced, say that.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "headline": "One punchy sentence summarizing the overall ROI verdict",
  "narrative": "3-4 sentences giving the honest picture. What's working, what isn't, what's driving the overall number. Use **bold** for key figures or insights.",
  "caveat": "1 sentence noting any important caveats (e.g. small sample size, certain task types dominating the data)"
}

DATA:
<aggregated ROI JSON>
```

---

### 6.2 Category Analysis

```
Analyze which task categories are generating the best and worst ROI for this developer.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "best_categories": [
    {
      "category": "category_key",
      "label": "Human-readable label",
      "why": "2 sentences explaining why Claude Code excels at this for this user specifically"
    }
  ],
  "worst_categories": [
    {
      "category": "category_key",
      "label": "Human-readable label",
      "why": "2 sentences explaining why ROI is low here and what's driving it"
    }
  ],
  "insight": "1-2 sentences of overall pattern insight across categories"
}

Include up to 3 best and 3 worst. Only include categories with at least 2 sessions.

DATA:
<aggregated ROI JSON>
```

---

### 6.3 Friction Analysis

```
Analyze the friction patterns that are destroying ROI for this developer.
Be specific. Use second person ("you"). Reference actual patterns from the data.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "intro": "1 sentence on the biggest ROI killer",
  "friction_patterns": [
    {
      "pattern": "Short name for this friction pattern",
      "impact": "How much ROI this is costing (qualitative: low/medium/high)",
      "description": "2-3 sentences explaining this pattern and why it costs ROI",
      "fix": "1-2 sentences on what the developer could do differently to reduce this friction"
    }
  ]
}

Include 3 friction patterns ranked by ROI impact (highest first).

DATA:
<aggregated ROI JSON>
```

---

### 6.4 Recommendations

```
Based on this developer's ROI data, give specific, actionable recommendations
to increase their ROI from Claude Code. Focus on things that would move the
number — not generic advice.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "quick_wins": [
    {
      "title": "Short action title",
      "description": "2-3 sentences explaining what to do and why it will improve ROI",
      "estimated_impact": "low | medium | high",
      "copyable_prompt": "A specific prompt or workflow instruction to try"
    }
  ],
  "strategic_shifts": [
    {
      "title": "Short title",
      "description": "2-3 sentences on a bigger behavioral or workflow change",
      "rationale": "Why this applies specifically to this user's patterns"
    }
  ]
}

Include 3 quick wins and 2 strategic shifts.

DATA:
<aggregated ROI JSON>
```

---

## Stage 7: Executive Summary (1 Claude Code Subprocess Call)

Run after all Stage 6 calls complete. Receives all Stage 6 outputs as context.

**Execution:** one final Claude Code subprocess call
**Max output tokens:** target roughly 2048 tokens

```
Write a 4-part executive summary for a developer's Claude Code ROI report.
Be direct, honest, and specific. Use second person ("you").
Don't pad or hedge unless the data genuinely warrants it.

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "verdict_line": "One sentence overall verdict, e.g. 'Claude Code is saving you ~8 hours/week'",
  "whats_driving_roi": "2-3 sentences on the primary positive drivers",
  "whats_hurting_roi": "2-3 sentences on the primary negative drivers — be honest",
  "top_action": "The single highest-impact thing this developer should change"
}

ROI NARRATIVE:
<roi_narrative JSON>

CATEGORY ANALYSIS:
<category_analysis JSON>

FRICTION ANALYSIS:
<friction_analysis JSON>

RECOMMENDATIONS:
<recommendations JSON>

AGGREGATE DATA:
<aggregated ROI JSON>
```

---

## Stage 8: HTML Report Generation

Generate a single self-contained HTML file at `~/.claude/usage-data/roi-report.html`.

---

## Runtime Architecture

The implementation should be local-first and reuse the installed Claude Code CLI instead of calling Anthropic APIs directly.

### LLM Execution Strategy

- Use Python `subprocess.run(...)` to invoke `claude --print`
- Send the assembled prompt via stdin
- Read structured JSON responses from stdout
- Treat non-zero exit codes, timeouts, or malformed JSON as recoverable per-session/per-prompt failures
- Continue processing other sessions when one subprocess call fails

### Why This Design

- No separate `ANTHROPIC_API_KEY` management is required
- The command uses the same Claude Code environment/auth the developer already has configured
- This matches how the rest of the plugin operates in local Claude Code workflows
- It keeps the implementation simpler than maintaining a direct SDK/API integration

### Required Sections (in order)

**1. Header**

- Report title: "Claude Code ROI Report"
- Date range covered
- Overall verdict badge: STRONGLY POSITIVE / POSITIVE / NEUTRAL / NEGATIVE / STRONGLY NEGATIVE
  - Color-coded: green for positive, gray for neutral, red for negative

**2. Executive Summary**

- `verdict_line` as a large headline
- Four cards: What's Driving ROI / What's Hurting ROI / Top Action
- Net dollar value prominently displayed (e.g. "+$2,340 value generated")

**3. Key Metrics Bar**
A horizontal row of metric tiles:

- Total time saved (hours)
- Dollar value generated
- Net ROI (value − subscription cost)
- Sessions analyzed
- Positive / Neutral / Negative session counts (with percentages)
- ROI percentage

**4. ROI Over Time Chart**
Line or bar chart showing cumulative dollar value over the date range. Each data point = one session. Positive sessions push the line up, negative push it down. X-axis = date, Y-axis = cumulative $ value. Use Chart.js.

**5. Session-by-Session Breakdown**
A scrollable table or card list of every session with:

- Date/time
- Task description
- Category badge
- Actual duration
- Estimated manual duration
- Time saved (colored: green if positive, red if negative)
- Dollar value (colored)
- Outcome badge
- Efficiency rating badge
- Expandable row showing: outcome evidence, efficiency detail, friction observed

Default sort: most recent first. Allow sorting by dollar value, date, category.

**6. Category Breakdown**
Bar chart or table showing per-category stats:

- Session count
- Average time saved per session
- Average dollar value per session
- Positive session rate (%)

Highlight best and worst categories.

**7. ROI Narrative**
Full narrative text from Stage 6.1 with caveat in a muted callout box. Render `**bold**` markdown.

**8. Category Analysis**
Best categories (green cards) and worst categories (red cards), each with label and explanation.

**9. Friction Patterns**
Three friction cards showing pattern name, impact level (color-coded chip), description, and fix.

**10. Recommendations**

- Quick Wins: three cards with title, description, impact badge, and copyable prompt block
- Strategic Shifts: two cards with title, description, rationale

**11. Footer**

- Hourly rate used, with a note: "Update with `/roi --rate <amount>`"
- Subscription cost assumption ($100/month)
- Report generated timestamp

### HTML Report Technical Requirements

- Fully self-contained (no external dependencies except Chart.js from cdnjs)
- Dark mode via `prefers-color-scheme: dark`
- All copyable prompt blocks have a one-click copy button
- Sticky top nav for jumping between sections
- Session table is sortable by clicking column headers
- Expandable session rows (click to reveal detail)
- Responsive down to ~900px wide
- Verdict badge color system:
  - `strongly_positive` → `#16a34a` (green-600)
  - `positive` → `#65a30d` (lime-600)
  - `neutral` → `#737373` (neutral-500)
  - `negative` → `#dc2626` (red-600)
  - `strongly_negative` → `#7f1d1d` (red-900)
- Positive dollar values displayed in green, negative in red, neutral in gray

---

## CLI Behavior

### Progress Output

```
→ Loading config...           Hourly rate: $150/hr
→ Loading sessions...         Found 142 sessions, 89 eligible
→ Extracting ROI facets...    23 new, 66 cached
→ Scoring sessions...         89 sessions scored
→ Aggregating...              Overall verdict: POSITIVE
→ Analyzing...                Running 4 analysis prompts
→ Generating summary...
→ Rendering report...
✓ Report saved to ~/.claude/usage-data/roi-report.html

  💰 Net value generated: +$2,340
  ⏱  Time saved: 15.6 hours
  📊 Sessions: 61 positive / 18 neutral / 10 negative
```

### First Run (No Config)

```
Welcome to /roi — Claude Code ROI Calculator

To calculate dollar value of time saved, we need your approximate hourly rate.
This is stored locally and never shared.

What's your hourly rate in USD? (e.g. 150): _
```

### Flags

- `/roi --rate 200` — override hourly rate for this run (does not update cached config)
- `/roi --reset-cache` — delete all cached ROI facets and re-analyze everything
- `/roi --since 2025-01-01` — only analyze sessions after this date

---

## Implementation Notes

### Estimating Manual Effort — Key Design Decision

The quality of the whole report depends on Stage 3's manual effort estimates. A few guidelines to pass to the LLM or use for validation:

| Task Type                                 | Typical Manual Multiplier        |
| ----------------------------------------- | -------------------------------- |
| Understanding unfamiliar codebase         | 4–10× session time               |
| Debugging complex issue                   | 3–8×                             |
| Implementing feature from scratch         | 2–5×                             |
| Writing boilerplate/scaffolding           | 2–4×                             |
| Refactoring existing code                 | 1.5–3×                           |
| Writing tests                             | 1.5–3×                           |
| Writing docs                              | 1.5–2×                           |
| Simple config change developer knows well | 0.8–1.2× (near neutral)          |
| Failed/abandoned session                  | 0× manual equivalent (pure cost) |

Consider adding a validation step: if `estimated_manual_minutes` is more than 10× `actual_duration_minutes`, flag it as an outlier and cap at 10×.

### Subscription Cost Assumption

Hardcode Claude Code Pro at **$100/month** for the net ROI calculation. Display this assumption clearly in the report footer. If the user is on a different plan, they can mentally adjust — this is a reasonable default for an individual dev.

### Confidence Indicators

For sessions where the transcript is very short (< 5 user messages) or the outcome is `unclear`, mark the ROI estimate as **low confidence** and display a small indicator in the session breakdown table. These sessions still count toward aggregates but are flagged.

### Error Handling

- If config file doesn't exist, prompt for hourly rate before proceeding
- If a facet JSON fails to parse, log the error, skip that session, continue
- If an LLM analysis call fails, retry once, then render that section as "unavailable"
- If fewer than 5 eligible sessions exist, display a warning: "ROI estimates are more reliable with more sessions. Keep using Claude Code and re-run /roi next week."

---

## Pseudocode

```typescript
async function generateROIReport() {
  // Load or prompt for config
  const config = await loadOrPromptConfig();

  // Stage 1
  const rawSessions = await loadSessionLogs("~/.claude/projects/");
  const sessions = rawSessions.filter(
    (s) =>
      !isAgentSession(s) &&
      !isInternalSession(s) &&
      s.userMessageCount >= 2 &&
      s.durationMinutes >= 1,
  );
  const metadata = sessions.map(extractMetadata);

  // Stage 2 & 3: Extract ROI facets with caching
  const newSessions = sessions
    .filter((s) => !roiFacetCacheExists(s.session_id))
    .slice(0, 50);

  await Promise.all(
    newSessions.map(async (session) => {
      let transcript = session.transcript;
      if (transcript.length > 30_000) {
        transcript = await summarizeInChunks(transcript, 25_000);
      }
      const facet = await callLLM(
        ROI_FACET_PROMPT(session.duration_minutes) + transcript,
      );
      saveROIFacetCache(session.session_id, facet);
    }),
  );

  // Load all facets (cached + newly extracted)
  const facets = sessions.reduce((acc, s) => {
    acc[s.session_id] = loadROIFacetCache(s.session_id);
    return acc;
  }, {});

  // Stage 4: Score sessions locally
  const scores = sessions
    .filter((s) => facets[s.session_id])
    .map((s) =>
      scoreSession(
        metadata.find((m) => m.session_id === s.session_id),
        facets[s.session_id],
        config.hourly_rate_usd,
      ),
    );

  // Stage 5: Aggregate
  const aggregated = aggregateROI(scores, config);

  // Stage 6: Run analysis prompts in parallel
  const [roi_narrative, category_analysis, friction_analysis, recommendations] =
    await Promise.all([
      callLLM(ROI_NARRATIVE_PROMPT, aggregated),
      callLLM(CATEGORY_ANALYSIS_PROMPT, aggregated),
      callLLM(FRICTION_ANALYSIS_PROMPT, aggregated),
      callLLM(RECOMMENDATIONS_PROMPT, aggregated),
    ]);

  // Stage 7: Executive summary
  const insights = {
    roi_narrative,
    category_analysis,
    friction_analysis,
    recommendations,
  };
  const executive_summary = await callLLM(EXECUTIVE_SUMMARY_PROMPT, {
    aggregated,
    ...insights,
  });

  // Stage 8: Render report
  const html = renderROIReport(
    scores,
    aggregated,
    { ...insights, executive_summary },
    config,
  );
  await writeFile("~/.claude/usage-data/roi-report.html", html);

  printSummary(aggregated, config);
}
```
