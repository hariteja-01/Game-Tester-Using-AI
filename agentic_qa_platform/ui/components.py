"""Streamlit UI custom components for the Agentic QA Platform.

Provides dark-themed, glass-morphism styled metric cards, Plotly charts
for risk gauges, FPS monitoring, resource utilization, bug severity
breakdowns, agent status displays, and code-diff rendering.  Every Plotly
figure uses a consistent transparent-dark palette so it blends seamlessly
into the engineering dashboard shell.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Dark engineering-dashboard CSS
# ---------------------------------------------------------------------------

DARK_THEME_CSS: str = """
<style>
/* ── Root colour tokens ─────────────────────────────────────────────── */
:root {
    --bg-deep:       #0a0e17;
    --bg-surface:    #0d1117;
    --bg-card:       #161b22;
    --border-subtle: rgba(88, 166, 255, 0.12);
    --border-glow:   rgba(88, 166, 255, 0.45);
    --accent-blue:   #58a6ff;
    --accent-green:  #3fb950;
    --accent-amber:  #d29922;
    --accent-red:    #f85149;
    --text-primary:  #e6edf3;
    --text-secondary:#8b949e;
    --font-mono:     'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

/* ── Global background ──────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"] {
    background-color: var(--bg-deep) !important;
    color: var(--text-primary) !important;
}
[data-testid="stHeader"] {
    background-color: rgba(10, 14, 23, 0.85) !important;
    backdrop-filter: blur(8px);
}
[data-testid="stSidebar"] {
    background-color: var(--bg-surface) !important;
    border-right: 1px solid var(--border-subtle);
}

/* ── Glass-morphism card base ───────────────────────────────────────── */
.glass-card {
    background: linear-gradient(135deg,
        rgba(22, 27, 34, 0.92),
        rgba(13, 17, 23, 0.88));
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    backdrop-filter: blur(12px);
    transition: border-color 0.25s ease, box-shadow 0.25s ease,
                transform 0.15s ease;
}
.glass-card:hover {
    border-color: var(--border-glow);
    box-shadow: 0 0 20px rgba(88, 166, 255, 0.08);
    transform: translateY(-1px);
}

/* ── Metric card ────────────────────────────────────────────────────── */
.metric-card {
    background: linear-gradient(135deg,
        rgba(22, 27, 34, 0.95),
        rgba(13, 17, 23, 0.9));
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.25s ease, box-shadow 0.25s ease,
                transform 0.15s ease;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg,
        var(--accent-blue), var(--accent-green));
    border-radius: 14px 14px 0 0;
}
.metric-card:hover {
    border-color: var(--border-glow);
    box-shadow: 0 4px 24px rgba(88, 166, 255, 0.12);
    transform: translateY(-2px);
}
.metric-card .metric-icon {
    font-size: 1.6rem;
    margin-bottom: 0.25rem;
}
.metric-card .metric-value {
    font-family: var(--font-mono);
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.15;
}
.metric-card .metric-title {
    font-size: 0.82rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 0.35rem;
}
.metric-card .metric-delta {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    margin-top: 0.35rem;
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
}
.metric-delta.delta-positive {
    color: var(--accent-green);
    background: rgba(63, 185, 80, 0.12);
}
.metric-delta.delta-negative {
    color: var(--accent-red);
    background: rgba(248, 81, 73, 0.12);
}
.metric-delta.delta-normal {
    color: var(--text-secondary);
    background: rgba(139, 148, 158, 0.12);
}

/* ── Agent status cards ─────────────────────────────────────────────── */
.agent-card {
    background: linear-gradient(135deg,
        rgba(22, 27, 34, 0.95),
        rgba(13, 17, 23, 0.88));
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}
.agent-card:hover {
    border-color: var(--border-glow);
    box-shadow: 0 0 18px rgba(88, 166, 255, 0.1);
}
.agent-card .agent-name {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary);
    margin-bottom: 0.4rem;
}
.agent-card .agent-meta {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--text-secondary);
}
.status-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.status-running  { background: rgba(88,166,255,0.15); color: var(--accent-blue); }
.status-completed{ background: rgba(63,185,80,0.15);  color: var(--accent-green); }
.status-error    { background: rgba(248,81,73,0.15);   color: var(--accent-red); }

/* ── Diff viewer ────────────────────────────────────────────────────── */
.diff-block {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    font-family: var(--font-mono);
    font-size: 0.82rem;
    line-height: 1.55;
    overflow-x: auto;
    white-space: pre;
}
.diff-add  { color: var(--accent-green); }
.diff-del  { color: var(--accent-red); }
.diff-hunk { color: var(--accent-blue); font-style: italic; }

/* ── Streamlit tab overrides ────────────────────────────────────────── */
[data-testid="stTabs"] button {
    color: var(--text-secondary) !important;
    font-weight: 500;
    border-bottom: 2px solid transparent !important;
    transition: color 0.2s ease, border-color 0.2s ease;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent-blue) !important;
    border-bottom: 2px solid var(--accent-blue) !important;
}
[data-testid="stTabs"] button:hover {
    color: var(--text-primary) !important;
}

/* ── Custom scrollbars ──────────────────────────────────────────────── */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: var(--bg-surface); }
::-webkit-scrollbar-thumb {
    background: rgba(139, 148, 158, 0.35);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(139, 148, 158, 0.55); }

/* ── Focus glow ─────────────────────────────────────────────────────── */
input:focus, textarea:focus, select:focus,
[data-testid="stTextInput"] input:focus {
    outline: none !important;
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.18) !important;
}
</style>
"""

# ---------------------------------------------------------------------------
# Shared Plotly layout helper
# ---------------------------------------------------------------------------

_PLOTLY_LAYOUT_DEFAULTS: dict[str, Any] = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(13,17,23,0.8)",
    "font": {"color": "#e6edf3", "family": "Inter, sans-serif"},
    "margin": {"l": 48, "r": 24, "t": 48, "b": 40},
    "xaxis": {
        "gridcolor": "rgba(255,255,255,0.07)",
        "zerolinecolor": "rgba(255,255,255,0.1)",
    },
    "yaxis": {
        "gridcolor": "rgba(255,255,255,0.07)",
        "zerolinecolor": "rgba(255,255,255,0.1)",
    },
}


def _base_layout(**overrides: Any) -> dict[str, Any]:
    """Return a deep-copy-ish merged layout dict for Plotly."""
    import copy

    layout = copy.deepcopy(_PLOTLY_LAYOUT_DEFAULTS)
    for key, val in overrides.items():
        if isinstance(val, dict) and key in layout and isinstance(layout[key], dict):
            layout[key].update(val)
        else:
            layout[key] = val
    return layout


# ---------------------------------------------------------------------------
# Metric card
# ---------------------------------------------------------------------------


def render_metric_card(
    title: str,
    value: str,
    delta: str = "",
    delta_color: str = "normal",
    icon: str = "",
) -> None:
    """Render a sleek glass-morphism metric card.

    Parameters
    ----------
    title:
        Short label displayed below the value (e.g. "Total Bugs").
    value:
        The large numeric / text value shown prominently.
    delta:
        Optional change indicator (e.g. "+12 %").
    delta_color:
        One of ``"normal"``, ``"positive"``, or ``"negative"``.  Controls the
        badge colour.
    icon:
        An emoji or short string rendered above the value.
    """
    delta_class = {
        "positive": "delta-positive",
        "inverse": "delta-negative",
        "negative": "delta-negative",
        "normal": "delta-normal",
        "off": "delta-normal",
    }.get(delta_color, "delta-normal")

    delta_html = ""
    if delta:
        delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>'

    icon_html = ""
    if icon:
        icon_html = f'<div class="metric-icon">{icon}</div>'

    html = f"""
    <div class="metric-card">
        {icon_html}
        <div class="metric-value">{value}</div>
        <div class="metric-title">{title}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Risk gauge
# ---------------------------------------------------------------------------


def render_risk_gauge(
    score: float,
    label: str = "Release Risk Score",
) -> go.Figure:
    """Create a Plotly gauge indicator showing a 0–100 risk score.

    Colour zones:
    * 0–30   → red   (high risk)
    * 30–50  → orange
    * 50–75  → yellow
    * 75–100 → green (low risk / ready)

    Parameters
    ----------
    score:
        Numeric value in ``[0, 100]``.
    label:
        Subtitle text shown beneath the gauge.

    Returns
    -------
    go.Figure
        The fully-configured Plotly figure.
    """
    score = max(0.0, min(100.0, float(score)))

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": label, "font": {"size": 16, "color": "#8b949e"}},
            number={"font": {"size": 48, "color": "#e6edf3", "family": "JetBrains Mono, monospace"}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#8b949e",
                    "dtick": 25,
                    "tickfont": {"color": "#8b949e"},
                },
                "bar": {"color": "#58a6ff", "thickness": 0.25},
                "bgcolor": "rgba(22,27,34,0.6)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(248,81,73,0.25)"},
                    {"range": [30, 50], "color": "rgba(210,153,34,0.25)"},
                    {"range": [50, 75], "color": "rgba(210,210,34,0.20)"},
                    {"range": [75, 100], "color": "rgba(63,185,80,0.25)"},
                ],
                "threshold": {
                    "line": {"color": "#e6edf3", "width": 3},
                    "thickness": 0.8,
                    "value": score,
                },
            },
        )
    )

    fig.update_layout(
        **_base_layout(
            height=280,
            margin={"l": 32, "r": 32, "t": 32, "b": 16},
        )
    )
    return fig


# ---------------------------------------------------------------------------
# FPS chart
# ---------------------------------------------------------------------------


def render_fps_chart(
    timestamps: List[Any],
    fps_values: List[float],
    title: str = "FPS Over Time",
) -> go.Figure:
    """Create an area-filled line chart of FPS with 60 & 30 FPS reference lines.

    Parameters
    ----------
    timestamps:
        X-axis values (datetime or numeric).
    fps_values:
        Corresponding frames-per-second readings.
    title:
        Chart title.

    Returns
    -------
    go.Figure
    """
    fig = go.Figure()

    # Main FPS trace with gradient-style area fill
    fig.add_trace(
        go.Scatter(
            x=list(timestamps),
            y=list(fps_values),
            mode="lines",
            name="FPS",
            line={"color": "#58a6ff", "width": 2, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(88,166,255,0.12)",
            hovertemplate="<b>%{y:.1f}</b> FPS<extra></extra>",
        )
    )

    # Reference lines
    n = len(timestamps)
    for ref_fps, color, dash_style in [
        (60, "#3fb950", "dash"),
        (30, "#d29922", "dot"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=[timestamps[0], timestamps[-1]] if n else [],
                y=[ref_fps, ref_fps],
                mode="lines",
                name=f"{ref_fps} FPS",
                line={"color": color, "width": 1.5, "dash": dash_style},
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        **_base_layout(
            title={"text": title, "font": {"size": 15}},
            height=340,
            xaxis={"title": "Time"},
            yaxis={"title": "FPS", "rangemode": "tozero"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "font": {"size": 11},
            },
            hovermode="x unified",
        )
    )
    return fig


# ---------------------------------------------------------------------------
# Resource utilization (dual-axis)
# ---------------------------------------------------------------------------


def render_resource_chart(
    timestamps: List[Any],
    cpu_values: List[float],
    ram_values: List[float],
    title: str = "Resource Utilization",
) -> go.Figure:
    """Create a dual-axis chart with CPU % (left) and RAM % (right).

    Parameters
    ----------
    timestamps:
        X-axis values.
    cpu_values:
        CPU utilization percentages.
    ram_values:
        RAM utilization percentages.
    title:
        Chart title.

    Returns
    -------
    go.Figure
    """
    from plotly.subplots import make_subplots

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=list(timestamps),
            y=list(cpu_values),
            mode="lines",
            name="CPU %",
            line={"color": "#58a6ff", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(88,166,255,0.08)",
            hovertemplate="CPU: <b>%{y:.1f}%</b><extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=list(timestamps),
            y=list(ram_values),
            mode="lines",
            name="RAM %",
            line={"color": "#3fb950", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(63,185,80,0.08)",
            hovertemplate="RAM: <b>%{y:.1f}%</b><extra></extra>",
        ),
        secondary_y=True,
    )

    layout = _base_layout(
        title={"text": title, "font": {"size": 15}},
        height=340,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11},
        },
        hovermode="x unified",
    )
    fig.update_layout(**layout)

    axis_common = {
        "gridcolor": "rgba(255,255,255,0.07)",
        "zerolinecolor": "rgba(255,255,255,0.1)",
        "range": [0, 100],
    }
    fig.update_yaxes(
        title_text="CPU %",
        secondary_y=False,
        **axis_common,
    )
    fig.update_yaxes(
        title_text="RAM %",
        secondary_y=True,
        **axis_common,
    )
    return fig


# ---------------------------------------------------------------------------
# Bug severity chart
# ---------------------------------------------------------------------------


def render_bug_severity_chart(
    critical: int,
    major: int,
    minor: int,
) -> go.Figure:
    """Horizontal bar chart of bug counts by severity.

    Parameters
    ----------
    critical:
        Number of critical bugs.
    major:
        Number of major bugs.
    minor:
        Number of minor bugs.

    Returns
    -------
    go.Figure
    """
    labels = ["Minor", "Major", "Critical"]
    values = [minor, major, critical]
    colors = ["#d29922", "#e3872d", "#f85149"]

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=values,
            orientation="h",
            marker={
                "color": colors,
                "line": {"color": "rgba(255,255,255,0.08)", "width": 1},
            },
            text=[str(v) for v in values],
            textposition="auto",
            textfont={"family": "JetBrains Mono, monospace", "size": 13},
            hovertemplate="%{y}: <b>%{x}</b><extra></extra>",
        )
    )

    fig.update_layout(
        **_base_layout(
            title={"text": "Bug Severity Distribution", "font": {"size": 15}},
            height=240,
            xaxis={"title": "Count"},
            yaxis={"categoryorder": "array", "categoryarray": labels},
            showlegend=False,
        )
    )
    return fig


# ---------------------------------------------------------------------------
# Agent status cards
# ---------------------------------------------------------------------------


def render_agent_status_cards(traces: List[Any]) -> None:
    """Render a responsive row of status cards for each agent trace.

    Each element of *traces* is expected to expose (via attribute or dict key):
    ``agent_name``, ``status``, ``execution_time_seconds``, ``steps``.

    Parameters
    ----------
    traces:
        Sequence of trace-like objects or dicts with agent execution data.
    """
    if not traces:
        st.info("No agent traces available.")
        return

    def _get(obj: Any, key: str, default: Any = "") -> Any:
        """Retrieve a value from an object by attribute or dict key."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    cols = st.columns(min(len(traces), 4))
    for idx, trace in enumerate(traces):
        col = cols[idx % len(cols)]
        name = _get(trace, "agent_name", "Agent")
        status = str(_get(trace, "status", "unknown")).lower()
        exec_time = _get(trace, "execution_time_seconds", 0)
        steps = _get(trace, "steps", [])
        step_count = len(steps) if isinstance(steps, (list, tuple)) else int(steps or 0)

        status_cls = {
            "running": "status-running",
            "completed": "status-completed",
            "error": "status-error",
        }.get(status, "status-running")

        status_icon = {"running": "🔄", "completed": "✅", "error": "❌"}.get(status, "⏳")

        html = f"""
        <div class="agent-card">
            <div class="agent-name">{status_icon} {name}</div>
            <span class="status-badge {status_cls}">{status}</span>
            <div class="agent-meta" style="margin-top:0.5rem;">
                ⏱ {exec_time:.2f}s &nbsp;·&nbsp; 📋 {step_count} step{"s" if step_count != 1 else ""}
            </div>
        </div>
        """
        col.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Code diff renderer
# ---------------------------------------------------------------------------


def render_code_diff(diff_text: str) -> None:
    """Render a syntax-highlighted git diff block.

    Lines beginning with ``+`` are coloured green, ``-`` red, and ``@@``
    hunk headers blue.

    Parameters
    ----------
    diff_text:
        Raw unified-diff string.
    """
    if not diff_text:
        st.info("No diff data to display.")
        return

    escaped_lines: list[str] = []
    for raw_line in diff_text.splitlines():
        line = (
            raw_line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if line.startswith("@@"):
            escaped_lines.append(f'<span class="diff-hunk">{line}</span>')
        elif line.startswith("+"):
            escaped_lines.append(f'<span class="diff-add">{line}</span>')
        elif line.startswith("-"):
            escaped_lines.append(f'<span class="diff-del">{line}</span>')
        else:
            escaped_lines.append(line)

    html = '<div class="diff-block">' + "\n".join(escaped_lines) + "</div>"
    st.markdown(html, unsafe_allow_html=True)
