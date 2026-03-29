"""HTML report generation."""

import json
import re
from datetime import datetime

from constants import (
    VERDICT_COLORS,
    EFFICIENCY_COLORS,
    OUTCOME_COLORS,
    CATEGORY_LABELS,
)


# ─── Formatting Helpers ──────────────────────────────────────────────────────────

def fmt_dollars(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}${v:,.2f}"


def render_bold_markdown(text: str) -> str:
    """Convert **bold** markdown to <strong> tags."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


# ─── Section Renderers ───────────────────────────────────────────────────────────

def _render_narrative_section(roi_narrative: dict) -> str:
    if not roi_narrative:
        return ""
    hl = render_bold_markdown(roi_narrative.get("headline", ""))
    narr = render_bold_markdown(roi_narrative.get("narrative", ""))
    cav = roi_narrative.get("caveat", "")
    return f"""
    <h2 class="section-title">ROI Narrative</h2>
    <div class="card">
      <h3 style="margin:0 0 12px;font-size:1.1rem">{hl}</h3>
      <p style="line-height:1.7;margin:0 0 16px">{narr}</p>
      <div class="callout">{cav}</div>
    </div>"""


def _render_category_section(category_analysis: dict) -> str:
    if not category_analysis:
        return ""
    best_html = "".join(
        f'<div class="cat-card cat-positive"><div class="cat-label">{c.get("label", c.get("category",""))}</div>'
        f'<p class="cat-why">{c.get("why","")}</p></div>'
        for c in category_analysis.get("best_categories", [])
    )
    worst_html = "".join(
        f'<div class="cat-card cat-negative"><div class="cat-label">{c.get("label", c.get("category",""))}</div>'
        f'<p class="cat-why">{c.get("why","")}</p></div>'
        for c in category_analysis.get("worst_categories", [])
    )
    insight = category_analysis.get("insight", "")
    return f"""
    <h2 class="section-title">Category Analysis</h2>
    <div class="card">
      {"<h3 class='sub-section-title' style='color:var(--green)'>Best Performing</h3><div class='cat-grid'>" + best_html + "</div>" if best_html else ""}
      {"<h3 class='sub-section-title' style='color:var(--red)'>Needs Improvement</h3><div class='cat-grid'>" + worst_html + "</div>" if worst_html else ""}
      {"<div class='callout'>" + insight + "</div>" if insight else ""}
    </div>"""


def _render_friction_section(friction_analysis: dict) -> str:
    if not friction_analysis:
        return ""
    intro = friction_analysis.get("intro", "")
    impact_colors = {"high": "#dc2626", "medium": "#f97316", "low": "#eab308"}
    patterns_html = "".join(
        f"""<div class="friction-card">
          <div class="friction-header">
            <span class="friction-name">{fp.get("pattern","")}</span>
            <span class="badge" style="background:{impact_colors.get(fp.get("impact",""),"#737373")}20;color:{impact_colors.get(fp.get("impact",""),"#737373")};border:1px solid {impact_colors.get(fp.get("impact",""),"#737373")}40">{fp.get("impact","").upper()} IMPACT</span>
          </div>
          <p style="margin:8px 0 6px;color:var(--text-secondary)">{fp.get("description","")}</p>
          <div class="fix-block">💡 {fp.get("fix","")}</div>
        </div>"""
        for fp in friction_analysis.get("friction_patterns", [])
    )
    return f"""
    <h2 class="section-title">Friction Patterns</h2>
    {"<div class='callout' style='margin-bottom:20px'>" + intro + "</div>" if intro else ""}
    <div class="friction-grid">{patterns_html}</div>"""


def _render_recommendations_section(recommendations: dict) -> str:
    if not recommendations:
        return ""
    impact_colors = {"high": "#16a34a", "medium": "#65a30d", "low": "#eab308"}
    qw_html = "".join(
        f"""<div class="rec-card">
          <div class="rec-header">
            <span class="rec-title">{qw.get("title","")}</span>
            <span class="badge" style="background:{impact_colors.get(qw.get("estimated_impact",""),"#737373")}20;color:{impact_colors.get(qw.get("estimated_impact",""),"#737373")};border:1px solid {impact_colors.get(qw.get("estimated_impact",""),"#737373")}40">{qw.get("estimated_impact","").upper()} IMPACT</span>
          </div>
          <p style="margin:8px 0 12px;color:var(--text-secondary)">{qw.get("description","")}</p>
          <div class="prompt-block">
            <button class="copy-btn" onclick="navigator.clipboard.writeText(`{qw.get("copyable_prompt","").replace(chr(92), chr(92)*2).replace("`","\\`")}`)">Copy</button>
            <code>{qw.get("copyable_prompt","").replace("`","&#96;").replace('"',"&quot;")}</code>
          </div>
        </div>"""
        for qw in recommendations.get("quick_wins", [])
    )
    ss_html = "".join(
        f"""<div class="rec-card">
          <div class="rec-header"><span class="rec-title">{ss.get("title","")}</span></div>
          <p style="margin:8px 0 6px;color:var(--text-secondary)">{ss.get("description","")}</p>
          <div class="callout">{ss.get("rationale","")}</div>
        </div>"""
        for ss in recommendations.get("strategic_shifts", [])
    )
    return f"""
    <h2 class="section-title">Recommendations</h2>
    {"<h3 class='sub-section-title'>Quick Wins</h3><div class='rec-grid'>" + qw_html + "</div>" if qw_html else ""}
    {"<h3 class='sub-section-title'>Strategic Shifts</h3><div class='rec-grid'>" + ss_html + "</div>" if ss_html else ""}"""


def _render_exec_cards(exec_summary: dict) -> str:
    if not exec_summary:
        return ""
    return f"""
    <div class="exec-grid">
      <div class="exec-card">
        <div class="exec-label">What's Driving ROI</div>
        <div class="exec-body">{exec_summary.get("whats_driving_roi","")}</div>
      </div>
      <div class="exec-card">
        <div class="exec-label">What's Hurting ROI</div>
        <div class="exec-body">{exec_summary.get("whats_hurting_roi","")}</div>
      </div>
      <div class="exec-card exec-card-wide">
        <div class="exec-label">Top Action</div>
        <div class="exec-body" style="font-weight:600">{exec_summary.get("top_action","")}</div>
      </div>
    </div>"""


# ─── Main Report Renderer ────────────────────────────────────────────────────────

def render_html(scores: list[dict], aggregated: dict, insights: dict, config: dict) -> str:
    """Generate a fully self-contained HTML ROI report."""
    hourly_rate = config["hourly_rate_usd"]
    verdict = aggregated.get("overall_verdict", "neutral")
    verdict_color = VERDICT_COLORS.get(verdict, "#737373")
    verdict_label = verdict.replace("_", " ").upper()

    exec_summary = insights.get("executive_summary", {})
    roi_narrative = insights.get("roi_narrative", {})
    category_analysis = insights.get("category_analysis", {})
    friction_analysis = insights.get("friction_analysis", {})
    recommendations = insights.get("recommendations", {})

    # Chart: cumulative ROI over time
    sorted_by_date = sorted(scores, key=lambda s: s["start_time"])
    cumulative = 0.0
    chart_labels, chart_data = [], []
    for s in sorted_by_date:
        cumulative += s["dollar_value"]
        chart_labels.append(json.dumps(s["start_time"][:10]))
        chart_data.append(round(cumulative, 2))

    # Chart: avg value per category
    by_cat = aggregated.get("by_category", {})
    cat_keys = sorted(by_cat, key=lambda k: by_cat[k].get("avg_dollar_value", 0), reverse=True)
    cat_labels_js = json.dumps([CATEGORY_LABELS.get(k, k) for k in cat_keys])
    cat_values_js = json.dumps([by_cat[k]["avg_dollar_value"] for k in cat_keys])
    cat_colors_js = json.dumps([
        "#30d158" if by_cat[k]["avg_dollar_value"] >= 0 else "#ff453a"
        for k in cat_keys
    ])

    sessions_json = json.dumps(scores, default=str)
    date_range = aggregated.get("date_range", {})
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    net_roi = aggregated.get("net_roi_usd", 0)
    net_class = "metric-positive" if net_roi >= 0 else "metric-negative"

    warning_html = (
        '<div class="callout callout-warn">ROI estimates are more reliable with more sessions. '
        "Keep using Claude Code and re-run /roi next week.</div>"
        if aggregated.get("total_sessions", 0) < 5
        else ""
    )

    # Pre-render sections
    narrative_html = _render_narrative_section(roi_narrative)
    cat_analysis_html = _render_category_section(category_analysis)
    friction_html = _render_friction_section(friction_analysis)
    recs_html = _render_recommendations_section(recommendations)
    exec_html = _render_exec_cards(exec_summary)

    def metric_class(v: float) -> str:
        return "metric-positive" if v >= 0 else "metric-negative"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code ROI Report</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #f2f2f7;
    --surface: #ffffff;
    --surface2: #f2f2f7;
    --surface3: #e5e5ea;
    --border: rgba(0,0,0,0.08);
    --border-strong: rgba(0,0,0,0.14);
    --text: #1c1c1e;
    --text-secondary: #6e6e73;
    --text-tertiary: #aeaeb2;
    --green: #30d158;
    --red: #ff453a;
    --blue: #007aff;
    --yellow: #ff9f0a;
    --orange: #ff6b35;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.05);
    --shadow-lg: 0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06);
    --radius: 18px;
    --radius-sm: 10px;
    --radius-xs: 7px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #000000;
      --surface: #1c1c1e;
      --surface2: #2c2c2e;
      --surface3: #3a3a3c;
      --border: rgba(255,255,255,0.08);
      --border-strong: rgba(255,255,255,0.14);
      --text: #ffffff;
      --text-secondary: #ebebf599;
      --text-tertiary: #ebebf54d;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
      --shadow-md: 0 4px 16px rgba(0,0,0,0.5);
      --shadow-lg: 0 8px 32px rgba(0,0,0,0.6);
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
    background: var(--bg); color: var(--text); font-size: 15px; line-height: 1.5;
    -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
  a {{ color: var(--blue); text-decoration: none; }}

  .nav {{
    position: sticky; top: 0; z-index: 100; display: flex; overflow-x: auto;
    background: rgba(242,242,247,0.72); backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid var(--border);
  }}
  @media (prefers-color-scheme: dark) {{
    .nav {{ background: rgba(28,28,30,0.72); }}
  }}
  .nav a {{ padding: 13px 18px; color: var(--text-secondary); font-size: 13px; font-weight: 500;
    white-space: nowrap; border-bottom: 2px solid transparent; transition: color 0.15s; }}
  .nav a:hover {{ color: var(--blue); border-bottom-color: var(--blue); }}

  .container {{ max-width: 1160px; margin: 0 auto; padding: 40px 24px; }}
  .section {{ margin-bottom: 56px; scroll-margin-top: 60px; }}

  .header {{ text-align: center; margin-bottom: 48px; }}
  .header h1 {{ font-size: 2.4rem; font-weight: 700; letter-spacing: -0.025em; margin-bottom: 8px; }}
  .date-range {{ color: var(--text-secondary); margin-bottom: 20px; font-size: 15px; }}
  .verdict-badge {{ display: inline-block; padding: 7px 22px; border-radius: 9999px;
    font-weight: 600; font-size: 0.82rem; letter-spacing: 0.06em;
    background: {verdict_color}18; color: {verdict_color}; }}

  .card {{ background: var(--surface); border-radius: var(--radius); padding: 28px;
    box-shadow: var(--shadow-md); border: 1px solid var(--border); }}
  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 9999px;
    font-size: 11px; font-weight: 600; white-space: nowrap; letter-spacing: 0.02em; }}
  .callout {{ background: var(--surface2); border-radius: var(--radius-sm);
    padding: 14px 18px; color: var(--text-secondary); font-size: 13.5px; line-height: 1.6;
    border: 1px solid var(--border); }}
  .callout-warn {{ border-left: 3px solid var(--yellow); }}

  .metrics-bar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
    gap: 14px; margin-bottom: 36px; }}
  .metric-tile {{ background: var(--surface); border-radius: var(--radius); padding: 20px 16px;
    text-align: center; box-shadow: var(--shadow-sm); border: 1px solid var(--border);
    transition: box-shadow 0.2s; }}
  .metric-tile:hover {{ box-shadow: var(--shadow-md); }}
  .metric-value {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 5px; }}
  .metric-label {{ font-size: 12px; color: var(--text-secondary); font-weight: 500; letter-spacing: 0.01em; }}
  .metric-positive {{ color: var(--green); }}
  .metric-negative {{ color: var(--red); }}

  .section-title {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.015em; margin-bottom: 16px; }}
  .sub-section-title {{ font-size: 1rem; font-weight: 600; margin: 24px 0 14px; color: var(--text-secondary); letter-spacing: 0.01em; }}

  .verdict-line {{ font-size: 1.45rem; font-weight: 700; text-align: center; margin: 12px 0 20px;
    letter-spacing: -0.02em; }}
  .dollar-display {{ font-size: 3rem; font-weight: 800; text-align: center; margin: 4px 0 28px;
    letter-spacing: -0.04em; }}
  .exec-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 24px; }}
  .exec-card {{ background: var(--surface2); border-radius: var(--radius-sm); padding: 18px;
    border: 1px solid var(--border); }}
  .exec-card-wide {{ grid-column: 1 / -1; }}
  .exec-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em;
    color: var(--text-secondary); margin-bottom: 8px; font-weight: 600; }}
  .exec-body {{ font-size: 14px; line-height: 1.65; }}

  .chart-container {{ position: relative; height: 280px; }}

  .table-controls {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .sort-btn {{ background: var(--surface2); border: 1px solid var(--border); color: var(--text-secondary);
    padding: 7px 14px; border-radius: 9999px; cursor: pointer; font-size: 12.5px; font-weight: 500;
    transition: all 0.15s; }}
  .sort-btn:hover {{ color: var(--text); border-color: var(--border-strong); }}
  .sort-btn.active {{ background: var(--blue); border-color: var(--blue); color: #fff; }}
  .session-table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  .session-table th {{ background: var(--surface2); padding: 11px 14px; text-align: left;
    border-bottom: 1px solid var(--border); cursor: pointer; user-select: none;
    white-space: nowrap; color: var(--text-secondary); font-weight: 600; font-size: 12px;
    letter-spacing: 0.03em; }}
  .session-table th:first-child {{ border-radius: var(--radius-xs) 0 0 0; }}
  .session-table th:last-child {{ border-radius: 0 var(--radius-xs) 0 0; }}
  .session-table th:hover {{ color: var(--text); }}
  .session-table td {{ padding: 11px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  .session-table tr:hover td {{ background: var(--surface2); }}
  .detail-content {{ background: var(--surface2); padding: 18px; border-bottom: 1px solid var(--border); }}
  .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; font-size: 13px; }}
  .detail-label {{ color: var(--text-secondary); font-size: 11px; margin-bottom: 4px;
    font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }}
  .confidence-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--yellow);
    display: inline-block; margin-left: 4px; vertical-align: middle; }}

  .cat-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }}
  .cat-card {{ background: var(--surface2); border-radius: var(--radius-sm); padding: 18px;
    border: 1px solid var(--border); transition: box-shadow 0.2s; }}
  .cat-card:hover {{ box-shadow: var(--shadow-sm); }}
  .cat-positive {{ border-left: 3px solid var(--green); }}
  .cat-negative {{ border-left: 3px solid var(--red); }}
  .cat-label {{ font-weight: 600; margin-bottom: 7px; font-size: 14px; }}
  .cat-why {{ color: var(--text-secondary); font-size: 13px; line-height: 1.6; margin: 0; }}

  .friction-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  .friction-card {{ background: var(--surface); border-radius: var(--radius); padding: 22px;
    box-shadow: var(--shadow-sm); border: 1px solid var(--border); transition: box-shadow 0.2s; }}
  .friction-card:hover {{ box-shadow: var(--shadow-md); }}
  .friction-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
  .friction-name {{ font-weight: 600; font-size: 14.5px; }}
  .fix-block {{ background: var(--surface2); border-radius: var(--radius-xs); padding: 11px 14px;
    font-size: 13px; color: var(--text-secondary); margin-top: 12px; line-height: 1.6;
    border: 1px solid var(--border); }}

  .rec-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  .rec-card {{ background: var(--surface); border-radius: var(--radius); padding: 22px;
    box-shadow: var(--shadow-sm); border: 1px solid var(--border); transition: box-shadow 0.2s; }}
  .rec-card:hover {{ box-shadow: var(--shadow-md); }}
  .rec-header {{ display: flex; justify-content: space-between; align-items: flex-start;
    gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }}
  .rec-title {{ font-weight: 600; font-size: 14.5px; }}
  .prompt-block {{ position: relative; background: var(--surface2); border-radius: var(--radius-xs);
    padding: 12px 44px 12px 14px; font-family: "SF Mono", ui-monospace, monospace; font-size: 12px;
    color: var(--text-secondary); word-break: break-word; border: 1px solid var(--border); }}
  .copy-btn {{ position: absolute; top: 8px; right: 8px; background: var(--blue);
    color: white; border: none; border-radius: 6px; padding: 4px 10px; cursor: pointer;
    font-size: 11px; font-weight: 600; transition: opacity 0.15s; }}
  .copy-btn:hover {{ opacity: 0.8; }}

  .footer {{ text-align: center; padding: 40px 20px; color: var(--text-secondary);
    font-size: 12.5px; line-height: 2.2; }}

  @media (max-width: 900px) {{
    .exec-grid, .detail-grid {{ grid-template-columns: 1fr; }}
    .metrics-bar {{ grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }}
    .header h1 {{ font-size: 1.9rem; }}
    .dollar-display {{ font-size: 2.4rem; }}
  }}
</style>
</head>
<body>

<nav class="nav">
  <a href="#summary">Summary</a>
  <a href="#metrics">Metrics</a>
  <a href="#chart">ROI Over Time</a>
  <a href="#sessions">Sessions</a>
  <a href="#categories">Categories</a>
  <a href="#narrative">Narrative</a>
  <a href="#friction">Friction</a>
  <a href="#recommendations">Recommendations</a>
</nav>

<div class="container">

  {warning_html}

  <div class="header">
    <h1>Claude Code ROI Report</h1>
    <div class="date-range">{date_range.get("start","")} — {date_range.get("end","")}</div>
    <div class="verdict-badge">{verdict_label}</div>
  </div>

  <section class="section" id="summary">
    <div class="card">
      <div class="verdict-line">{exec_summary.get("verdict_line", roi_narrative.get("headline",""))}</div>
      <div class="dollar-display {net_class}">{fmt_dollars(net_roi)} net value</div>
      {exec_html}
    </div>
  </section>

  <section class="section" id="metrics">
    <div class="metrics-bar">
      <div class="metric-tile">
        <div class="metric-value {metric_class(aggregated.get('total_time_saved_hours',0))}">{aggregated.get("total_time_saved_hours",0):+.1f}h</div>
        <div class="metric-label">Time Saved</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value {metric_class(aggregated.get('total_dollar_value',0))}">{fmt_dollars(aggregated.get("total_dollar_value",0))}</div>
        <div class="metric-label">Value Generated</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value {metric_class(net_roi)}">{fmt_dollars(net_roi)}</div>
        <div class="metric-label">Net ROI (vs $100/mo)</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value">{aggregated.get("total_sessions",0)}</div>
        <div class="metric-label">Sessions Analyzed</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value metric-positive">{aggregated.get("positive_sessions",0)}</div>
        <div class="metric-label">Positive Sessions</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value" style="color:var(--text-secondary)">{aggregated.get("neutral_sessions",0)}</div>
        <div class="metric-label">Neutral Sessions</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value metric-negative">{aggregated.get("negative_sessions",0)}</div>
        <div class="metric-label">Negative Sessions</div>
      </div>
      <div class="metric-tile">
        <div class="metric-value {metric_class(aggregated.get('roi_percentage',0))}">{aggregated.get("roi_percentage",0):+.0f}%</div>
        <div class="metric-label">ROI %</div>
      </div>
    </div>
  </section>

  <section class="section" id="chart">
    <h2 class="section-title">ROI Over Time</h2>
    <div class="card"><div class="chart-container"><canvas id="roiChart"></canvas></div></div>
  </section>

  <section class="section" id="sessions">
    <h2 class="section-title">Session Breakdown</h2>
    <div class="card" style="padding:16px;overflow-x:auto">
      <div class="table-controls">
        <button class="sort-btn active" onclick="sortSessions('start_time','desc',this)">Sort: Recent</button>
        <button class="sort-btn" onclick="sortSessions('dollar_value','desc',this)">Sort: Best Value</button>
        <button class="sort-btn" onclick="sortSessions('dollar_value','asc',this)">Sort: Worst Value</button>
        <button class="sort-btn" onclick="sortSessions('actual_minutes','desc',this)">Sort: Longest</button>
      </div>
      <div id="sessionTableContainer"></div>
    </div>
  </section>

  <section class="section" id="categories">
    <h2 class="section-title">Category Breakdown</h2>
    <div class="card"><div class="chart-container" style="height:220px"><canvas id="catChart"></canvas></div></div>
    {cat_analysis_html}
  </section>

  <section class="section" id="narrative">{narrative_html}</section>
  <section class="section" id="friction">{friction_html}</section>
  <section class="section" id="recommendations">{recs_html}</section>

</div>

<div class="footer">
  Hourly rate: ${hourly_rate}/hr &nbsp;·&nbsp; Update with <code>/roi --rate &lt;amount&gt;</code>
  &nbsp;·&nbsp; Subscription assumption: $100/month (Claude Code Pro)
  &nbsp;·&nbsp; Generated {generated_at}
</div>

<script>
const SESSIONS = {sessions_json};
const CATEGORY_LABELS = {json.dumps(CATEGORY_LABELS)};
const VERDICT_COLORS = {json.dumps(VERDICT_COLORS)};
const EFFICIENCY_COLORS = {json.dumps(EFFICIENCY_COLORS)};
const OUTCOME_COLORS = {json.dumps(OUTCOME_COLORS)};

// ── Theme-aware colors ───────────────────────────────────────────────────────
const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const tickColor = isDark ? '#ebebf599' : '#6e6e73';
const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';

// ── Charts ───────────────────────────────────────────────────────────────────
new Chart(document.getElementById('roiChart').getContext('2d'), {{
  type: 'line',
  data: {{
    labels: [{",".join(chart_labels)}],
    datasets: [{{ label: 'Cumulative Value ($)', data: {json.dumps(chart_data)},
      borderColor: '{verdict_color}', backgroundColor: '{verdict_color}22',
      fill: true, tension: 0.3, pointRadius: 4, pointHoverRadius: 6 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => '$' + ctx.parsed.y.toFixed(2) }} }} }},
    scales: {{
      x: {{ ticks: {{ color: tickColor, maxTicksLimit: 8 }}, grid: {{ color: gridColor }} }},
      y: {{ ticks: {{ color: tickColor, callback: v => '$' + v }}, grid: {{ color: gridColor }} }}
    }}
  }}
}});

new Chart(document.getElementById('catChart').getContext('2d'), {{
  type: 'bar',
  data: {{ labels: {cat_labels_js}, datasets: [{{
    label: 'Avg $ Value/Session', data: {cat_values_js}, backgroundColor: {cat_colors_js}
  }}] }},
  options: {{
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => '$' + ctx.parsed.x.toFixed(2) }} }} }},
    scales: {{
      x: {{ ticks: {{ color: tickColor, callback: v => '$' + v }}, grid: {{ color: gridColor }} }},
      y: {{ ticks: {{ color: tickColor }}, grid: {{ color: gridColor }} }}
    }}
  }}
}});

// ── Session Table ────────────────────────────────────────────────────────────
let currentSort = {{field: 'start_time', dir: 'desc'}};

function pill(val, colorMap) {{
  const c = colorMap[val] || '#737373';
  return `<span class="badge" style="background:${{c}}22;color:${{c}};border:1px solid ${{c}}44">${{val.replace(/_/g,' ')}}</span>`;
}}
function fmtMins(m) {{
  if (!m && m !== 0) return '—';
  return m >= 60 ? (m/60).toFixed(1) + 'h' : Math.round(m) + 'm';
}}
function fmtDollars(v) {{
  const color = v > 0 ? '#30d158' : v < 0 ? '#ff453a' : '#6e6e73';
  return `<span style="color:${{color}};font-weight:600">${{v >= 0 ? '+' : ''}}$${{Math.abs(v).toFixed(2)}}</span>`;
}}

function renderTable() {{
  const sorted = [...SESSIONS].sort((a, b) => {{
    let [av, bv] = [a[currentSort.field], b[currentSort.field]];
    if (typeof av === 'string') {{ av = av.toLowerCase(); bv = bv.toLowerCase(); }}
    return currentSort.dir === 'asc' ? (av > bv ? 1 : av < bv ? -1 : 0) : (av < bv ? 1 : av > bv ? -1 : 0);
  }});
  const rows = sorted.map((s, i) => `
    <tr onclick="toggleDetail('d${{i}}')" style="cursor:pointer">
      <td style="color:var(--text-secondary);font-size:12px">${{s.start_time ? s.start_time.substring(0,16).replace('T',' ') : '—'}}</td>
      <td style="max-width:280px">${{s.task_description || '—'}}${{s.low_confidence ? '<span class="confidence-dot" title="Low confidence"></span>' : ''}}</td>
      <td><span class="badge" style="background:#3b82f622;color:#3b82f6;border:1px solid #3b82f644">${{CATEGORY_LABELS[s.task_category] || s.task_category || ''}}</span></td>
      <td style="white-space:nowrap">${{fmtMins(s.actual_minutes)}}</td>
      <td style="white-space:nowrap">${{fmtMins(s.estimated_manual_minutes)}}</td>
      <td style="white-space:nowrap">${{fmtMins(s.time_saved_minutes)}}</td>
      <td>${{fmtDollars(s.dollar_value)}}</td>
      <td>${{pill(s.outcome, OUTCOME_COLORS)}}</td>
      <td>${{pill(s.efficiency_rating, EFFICIENCY_COLORS)}}</td>
    </tr>
    <tr id="d${{i}}" style="display:none">
      <td colspan="9"><div class="detail-content"><div class="detail-grid">
        <div><div class="detail-label">Outcome Evidence</div>${{s.outcome_evidence || '—'}}</div>
        <div><div class="detail-label">Efficiency Detail</div>${{s.efficiency_detail || '—'}}</div>
        <div><div class="detail-label">Manual Estimate Rationale</div>${{s.manual_estimate_rationale || '—'}}</div>
        <div><div class="detail-label">Friction Observed</div>${{(s.friction_observed || []).join(', ') || '—'}}</div>
      </div></div></td>
    </tr>`).join('');

  document.getElementById('sessionTableContainer').innerHTML = `
    <table class="session-table"><thead><tr>
      <th onclick="sortSessions('start_time',null,null)">Date</th>
      <th>Task</th><th>Category</th>
      <th onclick="sortSessions('actual_minutes',null,null)">Actual</th>
      <th onclick="sortSessions('estimated_manual_minutes',null,null)">Manual Est.</th>
      <th onclick="sortSessions('time_saved_minutes',null,null)">Saved</th>
      <th onclick="sortSessions('dollar_value',null,null)">Value</th>
      <th>Outcome</th><th>Efficiency</th>
    </tr></thead><tbody>${{rows}}</tbody></table>`;
}}

function toggleDetail(id) {{
  const r = document.getElementById(id);
  if (r) r.style.display = r.style.display === 'none' ? 'table-row' : 'none';
}}

function sortSessions(field, dir, btn) {{
  dir = dir ?? (currentSort.field === field && currentSort.dir === 'desc' ? 'asc' : 'desc');
  currentSort = {{field, dir}};
  if (btn) {{ document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active')); btn.classList.add('active'); }}
  renderTable();
}}

renderTable();
</script>
</body>
</html>"""
