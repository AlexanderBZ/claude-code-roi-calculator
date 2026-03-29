"""LLM calls: summarization, ROI facet extraction, and analysis prompts."""

import json
import subprocess
import concurrent.futures
from typing import Optional

from constants import (
    MAX_FACET_TOKENS,
    MAX_ANALYSIS_TOKENS,
    MAX_SUMMARY_TOKENS,
    ROI_FACETS_DIR,
    TRANSCRIPT_SUMMARIZE_THRESHOLD,
    CHUNK_SIZE,
    MAX_MANUAL_MULTIPLIER,
    log,
)


# ─── LLM Helpers ────────────────────────────────────────────────────────────────

def call_llm(prompt: str, max_tokens: int = 2048) -> str:
    """Make a single LLM call via the claude CLI and return the text response."""
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def parse_json_response(text: str) -> dict:
    """Extract and parse the first JSON object from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        inner = []
        in_block = False
        for line in text.splitlines():
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner.append(line)
        text = "\n".join(inner)

    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


# ─── Transcript Summarization ────────────────────────────────────────────────────

SUMMARIZE_PROMPT = """Summarize this portion of a Claude Code session transcript. Focus on:
1. What the user asked for and what was ultimately accomplished
2. Concrete outputs: files changed, code written, bugs fixed, configs updated
3. Any significant back-and-forth, retries, or abandoned attempts
4. Whether the task succeeded or failed

Keep it concise — 3-5 sentences. Preserve specific details like file names,
error messages, and task descriptions.

TRANSCRIPT CHUNK:
{chunk}"""


def summarize_transcript(transcript: str) -> str:
    """Chunk and summarize a long transcript before facet extraction."""
    chunks = [transcript[i : i + CHUNK_SIZE] for i in range(0, len(transcript), CHUNK_SIZE)]
    summaries = []
    for chunk in chunks:
        try:
            summary = call_llm(SUMMARIZE_PROMPT.format(chunk=chunk), MAX_SUMMARY_TOKENS)
            summaries.append(summary)
        except Exception as e:
            summaries.append(f"[Summarization error: {e}]")
    return "\n\n---\n\n".join(summaries)


# ─── ROI Facet Extraction ────────────────────────────────────────────────────────

ROI_FACET_PROMPT = """You are analyzing a Claude Code session to estimate its ROI for the developer.

Your job is to estimate how long this task would have taken a competent mid-senior
developer working WITHOUT any AI assistance, then compare that to the actual session
duration to determine time saved or lost.

ACTUAL SESSION DURATION: {duration_minutes} minutes

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
{transcript}

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
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
}}"""

VALID_FRICTION_TYPES = {
    "excessive_retries",
    "misunderstood_task",
    "hallucinated_api",
    "scope_creep",
    "context_loss",
    "tool_failures",
    "user_pivoted",
    "environment_issues",
}


def load_cached_facet(session_id: str) -> Optional[dict]:
    path = ROI_FACETS_DIR / f"{session_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return None


def save_facet(session_id: str, facet: dict) -> None:
    ROI_FACETS_DIR.mkdir(parents=True, exist_ok=True)
    (ROI_FACETS_DIR / f"{session_id}.json").write_text(json.dumps(facet, indent=2))


def extract_facet(metadata: dict, transcript: str) -> Optional[dict]:
    """Extract ROI facet for a single session via LLM. Summarizes if transcript is long."""
    content = transcript
    if len(content) > TRANSCRIPT_SUMMARIZE_THRESHOLD:
        content = summarize_transcript(content)

    prompt = ROI_FACET_PROMPT.format(
        duration_minutes=metadata["duration_minutes"],
        transcript=content[:20_000],
    )

    try:
        raw = call_llm(prompt, MAX_FACET_TOKENS)
        facet = parse_json_response(raw)
        if not facet or "task_description" not in facet:
            return None

        # Cap outlier manual estimates
        dur = metadata["duration_minutes"]
        if dur > 0 and facet.get("estimated_manual_minutes", 0) > dur * MAX_MANUAL_MULTIPLIER:
            facet["estimated_manual_minutes"] = dur * MAX_MANUAL_MULTIPLIER

        # Sanitize friction list to known values
        friction = facet.get("friction_observed", [])
        if isinstance(friction, list):
            facet["friction_observed"] = [f for f in friction if f in VALID_FRICTION_TYPES]

        return facet
    except Exception as e:
        print(f"  Warning: facet extraction failed for {metadata['session_id'][:8]}...: {e}")
        return None


# ─── Analysis Prompts ────────────────────────────────────────────────────────────

ROI_NARRATIVE_PROMPT = """You are analyzing Claude Code ROI data for an individual developer.
Write an honest, direct assessment of whether Claude Code is delivering value.
Use second person ("you"). Don't be promotional — if the data shows negative ROI, say so clearly.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "headline": "One punchy sentence summarizing the overall ROI verdict",
  "narrative": "3-4 sentences giving the honest picture. What's working, what isn't, what's driving the overall number. Use **bold** for key figures or insights.",
  "caveat": "1 sentence noting any important caveats (e.g. small sample size, certain task types dominating the data)"
}}

DATA:
{data}"""

CATEGORY_ANALYSIS_PROMPT = """Analyze which task categories are generating the best and worst ROI for this developer.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "best_categories": [
    {{
      "category": "category_key",
      "label": "Human-readable label",
      "why": "2 sentences explaining why Claude Code excels at this for this user specifically"
    }}
  ],
  "worst_categories": [
    {{
      "category": "category_key",
      "label": "Human-readable label",
      "why": "2 sentences explaining why ROI is low here and what's driving it"
    }}
  ],
  "insight": "1-2 sentences of overall pattern insight across categories"
}}

Include up to 3 best and 3 worst. Only include categories with at least 2 sessions.

DATA:
{data}"""

FRICTION_ANALYSIS_PROMPT = """Analyze the friction patterns that are destroying ROI for this developer.
Be specific. Use second person ("you"). Reference actual patterns from the data.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "intro": "1 sentence on the biggest ROI killer",
  "friction_patterns": [
    {{
      "pattern": "Short name for this friction pattern",
      "impact": "low | medium | high",
      "description": "2-3 sentences explaining this pattern and why it costs ROI",
      "fix": "1-2 sentences on what the developer could do differently to reduce this friction"
    }}
  ]
}}

Include 3 friction patterns ranked by ROI impact (highest first).

DATA:
{data}"""

RECOMMENDATIONS_PROMPT = """Based on this developer's ROI data, give specific, actionable recommendations
to increase their ROI from Claude Code. Focus on things that would move the number — not generic advice.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "quick_wins": [
    {{
      "title": "Short action title",
      "description": "2-3 sentences explaining what to do and why it will improve ROI",
      "estimated_impact": "low | medium | high",
      "copyable_prompt": "A specific prompt or workflow instruction to try"
    }}
  ],
  "strategic_shifts": [
    {{
      "title": "Short title",
      "description": "2-3 sentences on a bigger behavioral or workflow change",
      "rationale": "Why this applies specifically to this user's patterns"
    }}
  ]
}}

Include 3 quick wins and 2 strategic shifts.

DATA:
{data}"""

EXECUTIVE_SUMMARY_PROMPT = """Write a 4-part executive summary for a developer's Claude Code ROI report.
Be direct, honest, and specific. Use second person ("you").
Don't pad or hedge unless the data genuinely warrants it.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "verdict_line": "One sentence overall verdict, e.g. 'Claude Code is saving you ~8 hours/week'",
  "whats_driving_roi": "2-3 sentences on the primary positive drivers",
  "whats_hurting_roi": "2-3 sentences on the primary negative drivers — be honest",
  "top_action": "The single highest-impact thing this developer should change"
}}

ROI NARRATIVE:
{roi_narrative}

CATEGORY ANALYSIS:
{category_analysis}

FRICTION ANALYSIS:
{friction_analysis}

RECOMMENDATIONS:
{recommendations}

AGGREGATE DATA:
{aggregated}"""


def run_analysis(aggregated: dict) -> dict:
    """Run 4 analysis prompts in parallel, then the executive summary."""
    agg_json = json.dumps(aggregated, indent=2)[:8000]

    def call(prompt_template: str, **kwargs) -> dict:
        try:
            raw = call_llm(prompt_template.format(**kwargs), MAX_ANALYSIS_TOKENS)
            result = parse_json_response(raw)
            return result if result else {}
        except Exception as e:
            print(f"  Warning: analysis call failed: {e}")
            return {}

    log("Analyzing...", "Running 4 analysis prompts in parallel")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            "roi_narrative": executor.submit(call, ROI_NARRATIVE_PROMPT, data=agg_json),
            "category_analysis": executor.submit(call, CATEGORY_ANALYSIS_PROMPT, data=agg_json),
            "friction_analysis": executor.submit(call, FRICTION_ANALYSIS_PROMPT, data=agg_json),
            "recommendations": executor.submit(call, RECOMMENDATIONS_PROMPT, data=agg_json),
        }
        results = {k: f.result() for k, f in futures.items()}

    log("Generating summary...")
    results["executive_summary"] = call(
        EXECUTIVE_SUMMARY_PROMPT,
        roi_narrative=json.dumps(results["roi_narrative"])[:2000],
        category_analysis=json.dumps(results["category_analysis"])[:2000],
        friction_analysis=json.dumps(results["friction_analysis"])[:2000],
        recommendations=json.dumps(results["recommendations"])[:2000],
        aggregated=agg_json,
    )
    return results
