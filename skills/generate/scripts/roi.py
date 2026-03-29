#!/usr/bin/env python3
"""
Claude Code ROI Calculator — entrypoint.

Usage: python3 roi.py [--rate RATE] [--reset-cache] [--since DATE]
"""

import sys
import argparse
import shutil
import concurrent.futures
from datetime import datetime, timezone

from constants import (
    ROI_CONFIG_FILE,
    ROI_FACETS_DIR,
    ROI_REPORT_FILE,
    USAGE_DIR,
    MAX_NEW_SESSIONS,
    log,
)
from sessions import load_sessions
from analysis import extract_facet, load_cached_facet, save_facet, run_analysis
from scoring import score_session, aggregate
from report import render_html


# ─── Config ──────────────────────────────────────────────────────────────────────

def load_config(rate_override: float | None = None) -> dict:
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    ROI_FACETS_DIR.mkdir(parents=True, exist_ok=True)

    if ROI_CONFIG_FILE.exists():
        try:
            import json
            config = json.loads(ROI_CONFIG_FILE.read_text())
            if rate_override is not None:
                config = dict(config)
                config["hourly_rate_usd"] = rate_override
            return config
        except Exception:
            pass

    if rate_override is not None:
        import json
        config = {
            "hourly_rate_usd": rate_override,
            "currency": "USD",
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        ROI_CONFIG_FILE.write_text(json.dumps(config, indent=2))
        return config

    print("Error: No hourly rate configured. Run: /roi --rate 150")
    sys.exit(1)


# ─── CLI ─────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude Code ROI Calculator")
    parser.add_argument("--rate", type=float, help="Override hourly rate (USD)")
    parser.add_argument("--reset-cache", action="store_true", help="Delete all cached ROI facets")
    parser.add_argument("--since", type=str, help="Only analyze sessions after YYYY-MM-DD")
    return parser.parse_args()


def print_summary(aggregated: dict) -> None:
    net = aggregated.get("net_roi_usd", 0)
    saved = aggregated.get("total_time_saved_hours", 0)
    pos = aggregated.get("positive_sessions", 0)
    neu = aggregated.get("neutral_sessions", 0)
    neg = aggregated.get("negative_sessions", 0)
    sign = "+" if net >= 0 else ""
    print(f"\n  💰 Net value generated: {sign}${net:,.2f}")
    print(f"  ⏱  Time saved: {saved:.1f} hours")
    print(f"  📊 Sessions: {pos} positive / {neu} neutral / {neg} negative")
    print(f"\n✓ Report saved to {ROI_REPORT_FILE}")


# ─── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.reset_cache and ROI_FACETS_DIR.exists():
        shutil.rmtree(ROI_FACETS_DIR)
        print("→ Cache cleared.")

    config = load_config(args.rate)
    hourly_rate = config["hourly_rate_usd"]
    print(f"→ {'Loading config...':<30} Hourly rate: ${hourly_rate}/hr")

    since_date = None
    if args.since:
        try:
            since_date = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Error: Invalid date for --since: {args.since}. Use YYYY-MM-DD.")
            sys.exit(1)

    # Stage 1: Load sessions
    log("Loading sessions...", "Scanning ~/.claude/projects/")
    sessions = load_sessions(since_date)
    log("Loading sessions...", f"Found {len(sessions)} eligible sessions")

    if not sessions:
        print("\nNo eligible sessions found. Expected at ~/.claude/projects/")
        sys.exit(0)

    # Stages 2–3: Extract ROI facets (with caching)
    new_sessions = [s for s in sessions if load_cached_facet(s["session_id"]) is None][:MAX_NEW_SESSIONS]
    cached_count = len(sessions) - len(new_sessions)
    log("Extracting ROI facets...", f"{len(new_sessions)} new, {cached_count} cached")

    def process_session(sess: dict) -> None:
        facet = extract_facet(sess["metadata"], sess["transcript"])
        if facet:
            save_facet(sess["session_id"], facet)

    if new_sessions:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(process_session, new_sessions))

    # Stage 4: Score sessions
    scores = []
    for s in sessions:
        facet = load_cached_facet(s["session_id"])
        if facet:
            scores.append(score_session(s["metadata"], facet, hourly_rate))

    log("Scoring sessions...", f"{len(scores)} sessions scored")

    if not scores:
        print("\nCould not score any sessions. Check that the claude CLI is installed and authenticated.")
        sys.exit(1)

    # Stage 5: Aggregate
    aggregated = aggregate(scores, config)
    overall = aggregated.get("overall_verdict", "neutral").replace("_", " ").upper()
    log("Aggregating...", f"Overall verdict: {overall}")

    # Stages 6–7: LLM analysis
    insights = run_analysis(aggregated)

    # Stage 8: Render report
    log("Rendering report...")
    html = render_html(scores, aggregated, insights, config)
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    ROI_REPORT_FILE.write_text(html, encoding="utf-8")

    print_summary(aggregated)


if __name__ == "__main__":
    main()
