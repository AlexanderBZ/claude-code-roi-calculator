"""Session scoring and aggregation — no LLM calls, pure computation."""

from constants import SUBSCRIPTION_COST_USD


# ─── Per-Session Scoring ─────────────────────────────────────────────────────────

def score_session(metadata: dict, facet: dict, hourly_rate: float) -> dict:
    """Compute ROI score for a single session."""
    actual = metadata["duration_minutes"]
    estimated_manual = facet.get("estimated_manual_minutes", actual)

    time_saved_minutes = estimated_manual - actual
    time_saved_hours = time_saved_minutes / 60.0
    dollar_value = time_saved_hours * hourly_rate

    if time_saved_minutes > 5:
        roi_verdict = "positive"
    elif time_saved_minutes < -5:
        roi_verdict = "negative"
    else:
        roi_verdict = "neutral"

    # Counterproductive sessions are always negative regardless of time delta
    if facet.get("efficiency_rating") == "counterproductive":
        roi_verdict = "negative"

    # Warmup/minimal sessions are always neutral
    if facet.get("task_category") == "warmup_minimal":
        roi_verdict = "neutral"

    low_confidence = (
        metadata.get("user_message_count", 0) < 5
        or facet.get("outcome") == "unclear"
    )

    return {
        "session_id": metadata["session_id"],
        "start_time": metadata["start_time"],
        "task_description": facet.get("task_description", ""),
        "task_category": facet.get("task_category", ""),
        "outcome": facet.get("outcome", ""),
        "outcome_evidence": facet.get("outcome_evidence", ""),
        "actual_minutes": round(actual, 1),
        "estimated_manual_minutes": round(estimated_manual, 1),
        "time_saved_minutes": round(time_saved_minutes, 1),
        "time_saved_hours": round(time_saved_hours, 3),
        "dollar_value": round(dollar_value, 2),
        "roi_verdict": roi_verdict,
        "efficiency_rating": facet.get("efficiency_rating", ""),
        "efficiency_detail": facet.get("efficiency_detail", ""),
        "manual_estimate_rationale": facet.get("manual_estimate_rationale", ""),
        "friction_observed": facet.get("friction_observed", []),
        "value_delivered": facet.get("value_delivered", ""),
        "brief_summary": facet.get("brief_summary", ""),
        "low_confidence": low_confidence,
        "languages": metadata.get("languages", []),
        "git_commits": metadata.get("git_commits", 0),
        "input_tokens": metadata.get("input_tokens", 0),
        "output_tokens": metadata.get("output_tokens", 0),
    }


# ─── Aggregation ─────────────────────────────────────────────────────────────────

def _compute_overall_verdict(positive_pct: float, roi_percentage: float, negative_pct: float) -> str:
    if positive_pct > 0.6 and roi_percentage > 40:
        return "strongly_positive"
    if positive_pct > 0.5 or roi_percentage > 20:
        return "positive"
    if negative_pct > 0.6 or roi_percentage < -30:
        return "strongly_negative"
    if roi_percentage < -10 or negative_pct > 0.4:
        return "negative"
    return "neutral"


def aggregate(scores: list[dict], config: dict) -> dict:
    """Aggregate ROI scores across all sessions into report-level stats."""
    if not scores:
        return {}

    hourly_rate = config["hourly_rate_usd"]
    total = len(scores)
    positive = sum(1 for s in scores if s["roi_verdict"] == "positive")
    negative = sum(1 for s in scores if s["roi_verdict"] == "negative")
    neutral = total - positive - negative

    total_actual_hours = sum(s["actual_minutes"] for s in scores) / 60.0
    total_manual_hours = sum(s["estimated_manual_minutes"] for s in scores) / 60.0
    total_saved_hours = sum(s["time_saved_hours"] for s in scores)
    total_dollar = sum(s["dollar_value"] for s in scores)
    avg_time_saved = sum(s["time_saved_minutes"] for s in scores) / total if total else 0
    avg_dollar = total_dollar / total if total else 0
    net_roi = total_dollar - SUBSCRIPTION_COST_USD
    roi_pct = (total_saved_hours / total_actual_hours * 100) if total_actual_hours > 0 else 0

    overall_verdict = _compute_overall_verdict(
        positive / total if total else 0,
        roi_pct,
        negative / total if total else 0,
    )

    # By category
    by_category: dict = {}
    for s in scores:
        cat = s["task_category"] or "unknown"
        if cat not in by_category:
            by_category[cat] = {"sessions": 0, "time_saved": 0, "dollar": 0, "pos": 0}
        by_category[cat]["sessions"] += 1
        by_category[cat]["time_saved"] += s["time_saved_minutes"]
        by_category[cat]["dollar"] += s["dollar_value"]
        if s["roi_verdict"] == "positive":
            by_category[cat]["pos"] += 1

    by_category_out = {
        cat: {
            "sessions": d["sessions"],
            "avg_time_saved_minutes": round(d["time_saved"] / d["sessions"], 1),
            "avg_dollar_value": round(d["dollar"] / d["sessions"], 2),
            "positive_rate": round(d["pos"] / d["sessions"] * 100, 1),
        }
        for cat, d in by_category.items()
    }

    # By efficiency / outcome
    by_efficiency: dict[str, int] = {}
    for s in scores:
        er = s["efficiency_rating"] or "unknown"
        by_efficiency[er] = by_efficiency.get(er, 0) + 1

    by_outcome: dict[str, int] = {}
    for s in scores:
        o = s["outcome"] or "unknown"
        by_outcome[o] = by_outcome.get(o, 0) + 1

    # Top friction types
    friction_counts: dict[str, int] = {}
    for s in scores:
        for f in s["friction_observed"]:
            friction_counts[f] = friction_counts.get(f, 0) + 1
    top_friction = sorted(friction_counts.items(), key=lambda x: -x[1])[:5]

    # Date range
    times = [s["start_time"] for s in scores if s["start_time"]]
    date_start = min(times)[:10] if times else ""
    date_end = max(times)[:10] if times else ""
    active_days = len({t[:10] for t in times})

    # Best / worst sessions
    sorted_by_value = sorted(scores, key=lambda s: s["dollar_value"])
    best = sorted_by_value[-3:][::-1]
    worst = sorted_by_value[:3]

    return {
        "total_sessions": total,
        "positive_sessions": positive,
        "negative_sessions": negative,
        "neutral_sessions": neutral,
        "total_actual_hours": round(total_actual_hours, 2),
        "total_estimated_manual_hours": round(total_manual_hours, 2),
        "total_time_saved_hours": round(total_saved_hours, 2),
        "average_time_saved_per_session_minutes": round(avg_time_saved, 1),
        "hourly_rate": hourly_rate,
        "total_dollar_value": round(total_dollar, 2),
        "average_dollar_value_per_session": round(avg_dollar, 2),
        "subscription_cost_usd": SUBSCRIPTION_COST_USD,
        "net_roi_usd": round(net_roi, 2),
        "overall_verdict": overall_verdict,
        "roi_percentage": round(roi_pct, 1),
        "by_category": by_category_out,
        "by_efficiency": by_efficiency,
        "by_outcome": by_outcome,
        "top_friction_types": top_friction,
        "date_range": {"start": date_start, "end": date_end},
        "active_days": active_days,
        "best_sessions": best,
        "worst_sessions": worst,
        "session_summaries": [s["brief_summary"] for s in scores if s.get("brief_summary")][:50],
    }
