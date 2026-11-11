"""UI components package for the Agentic QA Platform.

Exports the primary rendering functions and theme constant so that
consumers can do::

    from agentic_qa_platform.ui import (
        DARK_THEME_CSS,
        render_metric_card,
        render_risk_gauge,
        render_trace_viewer,
        render_agent_timeline,
    )
"""

from __future__ import annotations

from agentic_qa_platform.ui.components import (
    DARK_THEME_CSS,
    render_agent_status_cards,
    render_bug_severity_chart,
    render_code_diff,
    render_fps_chart,
    render_metric_card,
    render_resource_chart,
    render_risk_gauge,
)
from agentic_qa_platform.ui.trace_viewer import TraceViewer

# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

_viewer = TraceViewer()

render_trace_viewer = _viewer.render_trace_details
"""Render expandable step-by-step details for a single agent trace."""

render_agent_timeline = _viewer.render_trace_timeline
"""Render a Plotly Gantt-style timeline of all agent executions."""

__all__: list[str] = [
    # Theme
    "DARK_THEME_CSS",
    # Component functions
    "render_metric_card",
    "render_risk_gauge",
    "render_fps_chart",
    "render_resource_chart",
    "render_bug_severity_chart",
    "render_agent_status_cards",
    "render_code_diff",
    # Trace viewer
    "TraceViewer",
    "render_trace_viewer",
    "render_agent_timeline",
]
