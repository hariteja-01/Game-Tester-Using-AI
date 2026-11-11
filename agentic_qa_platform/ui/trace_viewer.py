"""Interactive agent reasoning-trace viewer for the Agentic QA Platform.

Renders Gantt-style timelines of agent execution, expandable step details,
and summary statistics — all via Streamlit and Plotly.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Union

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Colour palette for agent lanes
# ---------------------------------------------------------------------------

_AGENT_COLOURS: list[str] = [
    "#58a6ff",  # electric blue
    "#3fb950",  # emerald green
    "#d29922",  # amber
    "#bc8cff",  # violet
    "#f778ba",  # pink
    "#79c0ff",  # sky
    "#56d364",  # lime
    "#e3b341",  # gold
    "#ff7b72",  # salmon
    "#a5d6ff",  # light blue
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve a value from an object by attribute or dict key."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_datetime(val: Any) -> Optional[datetime]:
    """Best-effort conversion of an arbitrary value to a ``datetime``."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val)
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _format_seconds(seconds: float) -> str:
    """Return a compact human-readable duration string."""
    if seconds < 0.001:
        return "<1 ms"
    if seconds < 1.0:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60.0:
        return f"{seconds:.2f} s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}m {remainder:.1f}s"


def _pretty_json(data: Any) -> str:
    """Return indented JSON, falling back to ``repr`` for non-serialisable data."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError):
        return repr(data)


# ---------------------------------------------------------------------------
# TraceViewer
# ---------------------------------------------------------------------------


class TraceViewer:
    """Interactive viewer for agent reasoning traces.

    Each *trace* passed to the public methods is expected to expose (via
    attribute or dict key):

    * ``agent_name``  — display name of the agent.
    * ``status``      — ``"running"`` | ``"completed"`` | ``"error"``.
    * ``start_time``  — ISO-8601 string, unix timestamp, or ``datetime``.
    * ``end_time``    — same formats as ``start_time``.
    * ``execution_time_seconds`` — total wall-clock seconds.
    * ``steps``       — list of step objects, each with:
        * ``step_name``
        * ``start_time`` / ``end_time``
        * ``duration_seconds``
        * ``input_data``
        * ``output_data``
        * ``status``
    """

    # ------------------------------------------------------------------
    # Timeline (Gantt-like)
    # ------------------------------------------------------------------

    def render_trace_timeline(self, traces: List[Any]) -> None:
        """Render a Plotly Gantt-style horizontal bar timeline of all agents.

        Each agent occupies its own row; each step is a coloured bar placed
        from its start to its end time.

        Parameters
        ----------
        traces:
            Sequence of trace objects (see class docstring).
        """
        if not traces:
            st.info("No traces to display.")
            return

        fig = go.Figure()

        colour_map: dict[str, str] = {}
        for idx, trace in enumerate(traces):
            agent = str(_get(trace, "agent_name", f"Agent-{idx}"))
            colour_map.setdefault(agent, _AGENT_COLOURS[idx % len(_AGENT_COLOURS)])

        # Build horizontal bars per step
        for idx, trace in enumerate(traces):
            agent = str(_get(trace, "agent_name", f"Agent-{idx}"))
            steps = _get(trace, "steps", []) or []
            colour = colour_map[agent]

            if not steps:
                # If the trace has no granular steps, show a single bar
                t_start = _to_datetime(_get(trace, "start_time"))
                t_end = _to_datetime(_get(trace, "end_time"))
                if t_start and t_end:
                    fig.add_trace(
                        go.Bar(
                            y=[agent],
                            x=[(t_end - t_start).total_seconds()],
                            base=[t_start.isoformat()],
                            orientation="h",
                            marker={"color": colour, "opacity": 0.85},
                            name=agent,
                            showlegend=(idx == 0 or agent not in [
                                str(_get(traces[j], "agent_name", ""))
                                for j in range(idx)
                            ]),
                            hovertemplate=(
                                f"<b>{agent}</b><br>"
                                "Duration: %{x:.2f}s<extra></extra>"
                            ),
                        )
                    )
                continue

            for step_idx, step in enumerate(steps):
                step_name = str(_get(step, "step_name", f"Step {step_idx + 1}"))
                s_start = _to_datetime(_get(step, "start_time"))
                s_end = _to_datetime(_get(step, "end_time"))
                duration = _get(step, "duration_seconds", 0) or 0

                if s_start and s_end:
                    bar_width = (s_end - s_start).total_seconds()
                    base_iso = s_start.isoformat()
                elif s_start and duration:
                    bar_width = float(duration)
                    base_iso = s_start.isoformat()
                else:
                    continue

                fig.add_trace(
                    go.Bar(
                        y=[agent],
                        x=[bar_width],
                        base=[base_iso],
                        orientation="h",
                        marker={
                            "color": colour,
                            "opacity": 0.80,
                            "line": {"color": "rgba(255,255,255,0.15)", "width": 0.5},
                        },
                        name=step_name,
                        showlegend=False,
                        hovertemplate=(
                            f"<b>{agent}</b> — {step_name}<br>"
                            f"Duration: {_format_seconds(bar_width)}<extra></extra>"
                        ),
                    )
                )

        fig.update_layout(
            barmode="stack",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(13,17,23,0.8)",
            font={"color": "#e6edf3", "family": "Inter, sans-serif"},
            title={"text": "Agent Execution Timeline", "font": {"size": 15}},
            height=max(200, 80 * len(traces)),
            margin={"l": 120, "r": 24, "t": 48, "b": 40},
            xaxis={
                "title": "Time",
                "type": "date",
                "gridcolor": "rgba(255,255,255,0.07)",
            },
            yaxis={
                "autorange": "reversed",
                "gridcolor": "rgba(255,255,255,0.07)",
            },
            showlegend=False,
            hovermode="closest",
        )

        st.plotly_chart(fig, use_container_width=True, key="trace_timeline")

    # ------------------------------------------------------------------
    # Per-trace step details
    # ------------------------------------------------------------------

    def render_trace_details(self, trace: Any) -> None:
        """Render expandable details for a single agent trace.

        Each step is shown inside its own ``st.expander`` with input/output
        code blocks, timing badge, and a status indicator.

        Parameters
        ----------
        trace:
            A single trace object (see class docstring).
        """
        agent = str(_get(trace, "agent_name", "Agent"))
        status = str(_get(trace, "status", "unknown")).lower()
        steps = _get(trace, "steps", []) or []
        exec_time = _get(trace, "execution_time_seconds", 0) or 0

        status_icon = {"running": "🔄", "completed": "✅", "error": "❌"}.get(status, "⏳")

        st.markdown(
            f"### {status_icon} {agent} "
            f'<span style="font-size:0.75rem;color:#8b949e;">'
            f"({_format_seconds(float(exec_time))})</span>",
            unsafe_allow_html=True,
        )

        if not steps:
            st.caption("No granular steps recorded for this trace.")
            return

        for step_idx, step in enumerate(steps):
            step_name = str(_get(step, "step_name", f"Step {step_idx + 1}"))
            duration = float(_get(step, "duration_seconds", 0) or 0)
            step_status = str(_get(step, "status", "unknown")).lower()
            input_data = _get(step, "input_data")
            output_data = _get(step, "output_data")

            step_icon = "✅" if step_status in ("completed", "success") else (
                "❌" if step_status == "error" else "🔄"
            )
            badge = _format_seconds(duration)

            with st.expander(f"{step_icon} **{step_name}** — `{badge}`", expanded=False):
                if input_data is not None:
                    st.markdown("**Input**")
                    st.code(_pretty_json(input_data), language="json")
                if output_data is not None:
                    st.markdown("**Output**")
                    st.code(_pretty_json(output_data), language="json")

                # Metadata row
                meta_parts: list[str] = [f"Status: **{step_status}**"]
                s_start = _to_datetime(_get(step, "start_time"))
                s_end = _to_datetime(_get(step, "end_time"))
                if s_start:
                    meta_parts.append(f"Start: `{s_start.isoformat()}`")
                if s_end:
                    meta_parts.append(f"End: `{s_end.isoformat()}`")
                st.markdown(" &nbsp;·&nbsp; ".join(meta_parts))

    # ------------------------------------------------------------------
    # Execution summary
    # ------------------------------------------------------------------

    def render_execution_summary(self, traces: List[Any]) -> None:
        """Render aggregate summary statistics for all agent traces.

        Displays total execution time, agent count, step count, and an
        error summary (if any).

        Parameters
        ----------
        traces:
            Sequence of trace objects (see class docstring).
        """
        if not traces:
            st.info("No traces to summarise.")
            return

        total_time: float = 0.0
        total_steps: int = 0
        error_agents: list[str] = []

        for trace in traces:
            exec_time = float(_get(trace, "execution_time_seconds", 0) or 0)
            total_time += exec_time

            steps = _get(trace, "steps", []) or []
            total_steps += len(steps) if isinstance(steps, (list, tuple)) else 0

            if str(_get(trace, "status", "")).lower() == "error":
                error_agents.append(str(_get(trace, "agent_name", "unknown")))

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                _summary_card("⏱️", "Total Time", _format_seconds(total_time)),
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                _summary_card("🤖", "Agents", str(len(traces))),
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                _summary_card("📋", "Total Steps", str(total_steps)),
                unsafe_allow_html=True,
            )
        with col4:
            error_count = len(error_agents)
            colour = "#f85149" if error_count else "#3fb950"
            label = f"{error_count} Error{'s' if error_count != 1 else ''}"
            st.markdown(
                _summary_card("⚠️" if error_count else "✅", "Errors", label, value_colour=colour),
                unsafe_allow_html=True,
            )

        if error_agents:
            st.error(
                f"Agents with errors: **{', '.join(error_agents)}**",
                icon="🚨",
            )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _summary_card(
    icon: str,
    title: str,
    value: str,
    value_colour: str = "#e6edf3",
) -> str:
    """Return an HTML snippet for a compact summary card."""
    return f"""
    <div style="
        background: linear-gradient(135deg,
            rgba(22,27,34,0.95), rgba(13,17,23,0.88));
        border: 1px solid rgba(88,166,255,0.12);
        border-radius: 12px;
        padding: 1rem 1.15rem;
        text-align: center;
    ">
        <div style="font-size:1.4rem;">{icon}</div>
        <div style="
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.35rem;
            font-weight: 700;
            color: {value_colour};
            margin-top: 0.2rem;
        ">{value}</div>
        <div style="
            font-size: 0.78rem;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.2rem;
        ">{title}</div>
    </div>
    """
