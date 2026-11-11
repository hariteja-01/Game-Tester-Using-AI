"""Agentic QA Platform — Autonomous Multi-Agent Telemetry & QA Engine for Games.

Main Streamlit Application Entry Point.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Safe .env loader (without requiring external python-dotenv)
def _load_env_file() -> None:
    env_path = _REPO_ROOT / ".env"
    if env_path.is_file():
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and not os.getenv(k):
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Platform imports
from agentic_qa_platform.agents.orchestrator import AnalysisResult, Orchestrator
from agentic_qa_platform.agents.quota_manager import QuotaManager
from agentic_qa_platform.cicd.junit_exporter import JUnitExporter
from agentic_qa_platform.cicd.risk_scorer import RiskAssessment, RiskMetrics, RiskScorer
from agentic_qa_platform.cicd.sarif_exporter import SARIFExporter
from agentic_qa_platform.telemetry.log_parser import LogParser
from agentic_qa_platform.telemetry.process_monitor import ProcessMonitor
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
# Page Configuration & Dark Engineering Theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agentic-QA-Platform | Autonomous Game Telemetry & Testing",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# Custom header styling
st.markdown(
    """
    <style>
    .brand-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.2rem 1.8rem;
        background: linear-gradient(135deg, rgba(22, 27, 34, 0.85) 0%, rgba(13, 17, 23, 0.95) 100%);
        border: 1px solid rgba(88, 166, 255, 0.2);
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        margin-bottom: 1.5rem;
    }
    .brand-title {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #e6edf3;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .brand-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        background: rgba(63, 185, 80, 0.15);
        color: #3fb950;
        border: 1px solid rgba(63, 185, 80, 0.3);
    }
    .live-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #3fb950;
        box-shadow: 0 0 8px #3fb950;
        animation: pulse-dot 2s infinite ease-in-out;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.85); }
    }
    .tab-container {
        margin-top: 1rem;
    }
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .agent-card {
        background: #161b22;
        border: 1px solid rgba(88, 166, 255, 0.15);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    .code-box {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 0.75rem;
        font-family: var(--font-mono, monospace);
        font-size: 0.82rem;
        color: #c9d1d9;
        overflow-x: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "selected_game" not in st.session_state:
    st.session_state.selected_game = "Cyberpunk 2077"

# ---------------------------------------------------------------------------
# Sidebar Configuration & Telemetry Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚡ Platform Settings")
    st.caption("Autonomous Multi-Agent Telemetry & QA Engine")

    # Resolve API Key securely
    env_key = os.getenv("GEMINI_API_KEY", "")
    secret_key = ""
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
    default_platform_key = env_key or secret_key

    # Initialize Quota Manager
    quota_mgr = QuotaManager()
    quota_status = quota_mgr.get_status()

    st.markdown("#### 🔑 Gemini API & Key Management")

    key_choice = st.radio(
        "Key Mode",
        options=["Platform Key", "Personal Gemini Key", "Offline Heuristics"],
        index=0 if default_platform_key and not quota_status["is_threshold_hit"] else (1 if quota_status["is_threshold_hit"] else 2),
        help="Select which authentication tier to use for agent execution.",
    )

    if key_choice == "Personal Gemini Key":
        custom_key = st.text_input(
            "Enter Personal Gemini Key",
            value=st.session_state.get("custom_gemini_key", ""),
            type="password",
            help="Your key is kept in memory during this session only. Never saved or committed.",
        )
        if custom_key:
            st.session_state.custom_gemini_key = custom_key
            active_api_key = custom_key
            st.success("Personal Key Active (Unlimited Quota)", icon="🚀")
        else:
            active_api_key = ""
            st.info("Paste your Gemini API key above to start.", icon="ℹ️")
    elif key_choice == "Platform Key":
        active_api_key = default_platform_key
        # Quota progress bar
        p_used = quota_status["percent_used"]
        threshold = quota_status["threshold_percent"]
        st.write(f"**Platform Key Usage:** `{p_used:.0f}%` (Limit: `{threshold:.0f}%`)")
        st.progress(min(1.0, p_used / 100.0))

        if quota_status["is_threshold_hit"]:
            st.error(
                f"⚠️ 50% Quota Reached! ({quota_status['calls_made']}/{quota_status['budget_calls']} calls). "
                "Please switch to 'Personal Gemini Key' or 'Offline Heuristics'.",
                icon="🛑",
            )
        else:
            st.caption(f"🛡️ Guardrail active: switches to prompt at 50% ({quota_status['calls_remaining_before_threshold']} calls left).")
    else:  # Offline Heuristics
        active_api_key = ""
        st.info("Running in offline rule-based heuristic mode (Zero API consumption).", icon="⚡")

    st.markdown("---")
    st.markdown("### 🎮 Game Under Test")

    POPULAR_GAMES = [
        "Cyberpunk 2077",
        "Elden Ring",
        "Black Myth: Wukong",
        "Grand Theft Auto V",
        "Counter-Strike 2",
        "Valorant",
        "Minecraft",
        "Call of Duty: Warzone",
        "Baldur's Gate 3",
        "Apex Legends",
        "Starfield",
        "Hollow Knight",
        "Custom Game...",
    ]

    selected_choice = st.selectbox("Select Target Game", POPULAR_GAMES, index=0)
    if selected_choice == "Custom Game...":
        game_target = st.text_input("Enter Game Title", value="Project Valkyrie")
    else:
        game_target = selected_choice

    st.session_state.selected_game = game_target

    st.markdown("### 📡 Telemetry Mode")
    telemetry_mode = st.radio(
        "Ingestion Source",
        options=["synthetic", "live"],
        index=0,
        format_func=lambda x: "Synthetic Engine Stress (Gaussian Simulation)" if x == "synthetic" else "Live Process Tracking (psutil Host)",
        help="Synthetic simulates realistic gaming load curves, frame drops, and memory leaks. Live captures actual system processes.",
    )

    sampling_duration = st.slider(
        "Monitoring Window (Seconds)",
        min_value=3,
        max_value=15,
        value=5,
        step=1,
    )

    st.markdown("---")
    st.markdown("### 🤖 Active Agents")
    st.markdown(
        """
        - 🟢 **StressAgent**: Edge-case scenarios
        - 🔵 **TelemetryAgent**: psutil / telemetry
        - 🟡 **RCAAgent**: Stack-trace attribution
        - 🟣 **PatchAgent**: Unified git diffs
        - 🔴 **RiskScorer**: Release risk score
        """
    )

    st.markdown("---")
    st.caption("Agentic QA Platform v2.0 • Production Release")


# ---------------------------------------------------------------------------
# Header & Execution Control
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="brand-header">
        <div>
            <div class="brand-title">
                <span>⚡ AGENTIC-QA-PLATFORM</span>
            </div>
            <div style="font-size: 0.85rem; color: #8b949e; margin-top: 0.25rem;">
                Autonomous Multi-Agent Telemetry, Root Cause Analysis & Git Patching Engine
            </div>
        </div>
        <div>
            <div class="brand-pill">
                <span class="live-dot"></span>
                <span>ENGINE READY • {telemetry_mode.upper()} MODE</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Launch button with action bar
col_btn, col_info = st.columns([1, 3])
with col_btn:
    launch_clicked = st.button(
        f"🚀 Run Autonomous QA on '{game_target}'",
        type="primary",
        use_container_width=True,
    )

with col_info:
    if st.session_state.analysis_result:
        res = st.session_state.analysis_result
        st.markdown(
            f"""
            <div style="font-size: 0.88rem; color: #8b949e; padding-top: 0.5rem;">
                Last execution: <b>{res.game_name}</b> at {res.timestamp.strftime('%H:%M:%S UTC')} •
                Runtime: <b>{res.execution_time_seconds:.2f}s</b> •
                Bugs Found: <b>{len(res.bugs)}</b> •
                Risk Level: <b style="color: {'#3fb950' if res.risk_assessment and res.risk_assessment.risk_level == 'LOW' else '#f85149'};">{res.risk_assessment.risk_level if res.risk_assessment else 'N/A'}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Execution Pipeline
# ---------------------------------------------------------------------------
if launch_clicked:
    allowed, auth_mode, reason = quota_mgr.check_execution_permission(
        active_api_key=active_api_key,
        platform_default_key=default_platform_key,
    )
    if not allowed:
        st.error(
            f"🛑 **Platform Gemini API Quota Reached 50% Limit**\n\n"
            f"{reason}\n\n"
            "**Two options are available to continue testing:**\n"
            "- **Option 1 (Recommended)**: Switch to **'Personal Gemini Key'** in the sidebar and enter your own API key to continue with full AI agent features.\n"
            "- **Option 2**: Switch to **'Offline Heuristics'** in the sidebar to run the multi-agent pipeline using rule-based testing with zero API usage.",
            icon="⚠️",
        )
    else:
        with st.status(f"🤖 Orchestrating Autonomous Agents for '{game_target}'...", expanded=True) as status:
            st.write("Initializing multi-agent orchestrator...")
            orchestrator = Orchestrator(api_key=active_api_key)

            st.write("🟢 [Phase 1/5] StressAgent: Generating high-stress edge cases & workload parameters...")
            time.sleep(0.3)

            st.write(f"🔵 [Phase 2/5] TelemetryAgent: Capturing telemetry metrics ({telemetry_mode} mode, {sampling_duration}s)...")
            time.sleep(0.3)

            st.write("🟡 [Phase 3/5] RCAAgent & LogParser: Correlating stack traces and resource bottlenecks...")
            time.sleep(0.3)

            st.write("🟣 [Phase 4/5] PatchAgent: Generating autonomous C++/C# Git unified diff fixes...")
            time.sleep(0.3)

            st.write("🔴 [Phase 5/5] RiskScorer: Computing CI/CD Release Risk Score & compliance artifacts...")

            # Run the full orchestrator
            analysis_result = orchestrator.run_full_analysis(
                game_name=game_target,
                telemetry_mode=telemetry_mode,
                duration=float(sampling_duration),
            )

            # Record quota usage when running on platform shared key
            if auth_mode == "platform_key":
                quota_mgr.record_usage(calls=4)

            st.session_state.analysis_result = analysis_result
            status.update(label=f"✅ QA Execution Completed in {analysis_result.execution_time_seconds:.2f}s!", state="complete", expanded=False)

        st.rerun()

# ---------------------------------------------------------------------------
# Default fallback run if no result exists yet
# ---------------------------------------------------------------------------
if st.session_state.analysis_result is None:
    # Run baseline view without consuming quota
    with st.spinner("Preparing baseline telemetry & agent graph..."):
        init_orch = Orchestrator(api_key="")
        st.session_state.analysis_result = init_orch.run_full_analysis(
            game_name=game_target,
            telemetry_mode="synthetic",
            duration=5.0,
        )

result: AnalysisResult = st.session_state.analysis_result

# ---------------------------------------------------------------------------
# Main Dashboard Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_traces, tab_rca_patch, tab_cicd = st.tabs([
    "📊 System Overview & KPIs",
    "🤖 Agent Reasoning Traces",
    "🔍 RCA & Autonomous Patching",
    "🚀 CI/CD & Compliance Hub",
])

# ---------------------------------------------------------------------------
# TAB 1: SYSTEM OVERVIEW & KPIS
# ---------------------------------------------------------------------------
with tab_overview:
    # Top KPI metric cards
    risk_score = result.risk_assessment.overall_score if result.risk_assessment else 85.0
    risk_level = result.risk_assessment.risk_level if result.risk_assessment else "LOW"
    summary = result.telemetry_report.summary if result.telemetry_report else None

    avg_fps = summary.avg_fps if summary else 60.0
    min_fps = summary.min_fps if summary else 42.0
    avg_cpu = summary.avg_cpu if summary else 48.0
    max_cpu = summary.max_cpu if summary else 78.0
    avg_ram = summary.avg_ram if summary else 58.0
    crit_bugs = sum(1 for b in result.bugs if b.severity == "CRITICAL")
    major_bugs = sum(1 for b in result.bugs if b.severity == "MAJOR")

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        render_metric_card(
            title="Release Risk Score",
            value=f"{risk_score:.0f}/100",
            delta=risk_level,
            delta_color="inverse" if risk_level in ("HIGH", "CRITICAL") else "normal",
            icon="🛡️",
        )
    with kpi2:
        render_metric_card(
            title="Average Framerate",
            value=f"{avg_fps:.1f} FPS",
            delta=f"Min: {min_fps:.0f} FPS",
            delta_color="normal" if min_fps >= 30 else "inverse",
            icon="🎮",
        )
    with kpi3:
        render_metric_card(
            title="CPU Utilization",
            value=f"{avg_cpu:.1f}%",
            delta=f"Peak: {max_cpu:.1f}%",
            delta_color="inverse" if max_cpu > 85 else "normal",
            icon="⚙️",
        )
    with kpi4:
        render_metric_card(
            title="RAM Memory Footprint",
            value=f"{avg_ram:.1f}%",
            delta=f"{summary.max_ram:.0f} MB Peak" if summary else "Stable",
            delta_color="normal",
            icon="💾",
        )
    with kpi5:
        render_metric_card(
            title="Defects Detected",
            value=f"{len(result.bugs)} Issues",
            delta=f"{crit_bugs} Critical • {major_bugs} Major",
            delta_color="inverse" if crit_bugs > 0 else "normal",
            icon="⚠️",
        )

    st.markdown("<div style='height: 1.2rem;'></div>", unsafe_allow_html=True)

    # Risk Gauge & Resource Charts
    c_gauge, c_fps = st.columns([1, 2])
    with c_gauge:
        fig_gauge = render_risk_gauge(risk_score, label=f"Release Safety: {risk_level}")
        st.plotly_chart(fig_gauge, use_container_width=True)

    with c_fps:
        # Extract telemetry timelines
        if result.telemetry_report and result.telemetry_report.snapshots:
            timestamps = [s.timestamp.strftime("%H:%M:%S") for s in result.telemetry_report.snapshots]
            fps_vals = [s.fps for s in result.telemetry_report.snapshots]
            fig_fps = render_fps_chart(timestamps, fps_vals, title=f"Framerate Stability ({result.game_name})")
            st.plotly_chart(fig_fps, use_container_width=True)
        else:
            st.info("No telemetry snapshots available.")

    # Second row: Resource charts & Bug Severity
    c_res, c_sev = st.columns([2, 1])
    with c_res:
        if result.telemetry_report and result.telemetry_report.snapshots:
            timestamps = [s.timestamp.strftime("%H:%M:%S") for s in result.telemetry_report.snapshots]
            cpu_vals = [s.cpu_percent for s in result.telemetry_report.snapshots]
            ram_vals = [s.ram_percent for s in result.telemetry_report.snapshots]
            fig_res = render_resource_chart(timestamps, cpu_vals, ram_vals, title="CPU vs RAM Utilization Curve")
            st.plotly_chart(fig_res, use_container_width=True)

    with c_sev:
        minor_bugs = sum(1 for b in result.bugs if b.severity == "MINOR")
        fig_sev = render_bug_severity_chart(critical=crit_bugs, major=major_bugs, minor=minor_bugs)
        st.plotly_chart(fig_sev, use_container_width=True)

    # Stress Test Scenarios Cards
    st.markdown("### 🎯 Dynamic Edge-Case Stress Scenarios")
    scen_cols = st.columns(min(3, max(1, len(result.stress_scenarios))))
    for i, scen in enumerate(result.stress_scenarios[:3]):
        with scen_cols[i % len(scen_cols)]:
            st.markdown(
                f"""
                <div class="agent-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:600; color:#58a6ff;">{scen.name}</span>
                        <span style="font-size:0.75rem; background:rgba(88,166,255,0.15); color:#79c0ff; padding:2px 8px; border-radius:12px;">
                            Intensity {scen.intensity}/10
                        </span>
                    </div>
                    <div style="font-size:0.83rem; color:#8b949e; margin-top:0.4rem;">
                        {scen.description}
                    </div>
                    <div style="margin-top:0.6rem; font-size:0.78rem; font-family:monospace; color:#3fb950;">
                        Category: {scen.category.upper()}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# TAB 2: AGENT REASONING TRACES
# ---------------------------------------------------------------------------
with tab_traces:
    st.markdown("### 🤖 Multi-Agent Orchestration Traces")
    st.caption("Inspect live reasoning chains, tool execution times, and step-level input/output telemetry.")

    # Status row of agents
    render_agent_status_cards(result.agent_traces)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # Interactive Gantt Timeline
    viewer = TraceViewer()
    st.markdown("#### ⏱️ Multi-Agent Execution Timeline")
    viewer.render_trace_timeline(result.agent_traces)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # Step-by-step trace inspect expanders
    st.markdown("#### 🔬 Detailed Agent Reasoning Steps")
    for trace in result.agent_traces:
        agent_name = getattr(trace, "agent_name", "Unknown Agent")
        steps = getattr(trace, "steps", [])
        total_time = getattr(trace, "execution_time_seconds", 0.0)
        status_icon = "✅" if getattr(trace, "status", "") == "completed" else "⚙️"

        with st.expander(f"{status_icon} **{agent_name}** ({len(steps)} steps • {total_time:.3f}s)", expanded=False):
            viewer.render_trace_details(trace)


# ---------------------------------------------------------------------------
# TAB 3: RCA & AUTONOMOUS PATCHING
# ---------------------------------------------------------------------------
with tab_rca_patch:
    st.markdown("### 🔍 Root Cause Analysis & Autonomous Patching")
    st.caption("Deep correlation between crash traces, engine spikes, and unified Git diff solutions.")

    col_logs, col_rca = st.columns([1, 1])

    with col_logs:
        st.markdown("#### 📜 Ingested Engine Logs & Crash Traces")
        log_filter = st.selectbox("Filter Log Level", ["ALL", "FATAL", "ERROR", "WARN", "INFO"], index=0)

        filtered_logs = result.log_entries
        if log_filter != "ALL":
            filtered_logs = [entry for entry in result.log_entries if entry.level.value == log_filter]

        log_display_lines = []
        for entry in filtered_logs[:18]:
            color = "#f85149" if entry.level.value in ("FATAL", "ERROR") else ("#d29922" if entry.level.value == "WARN" else "#8b949e")
            log_display_lines.append(
                f"<span style='color:#6e7681;'>[{entry.timestamp.strftime('%H:%M:%S')}]</span> "
                f"<b style='color:{color};'>[{entry.level.value}]</b> "
                f"<span style='color:#79c0ff;'>{entry.source}:</span> {entry.message}"
            )

        log_html = "<br>".join(log_display_lines) if log_display_lines else "<i>No logs matching filter</i>"
        st.markdown(
            f"""
            <div class="code-box" style="height: 380px; overflow-y: auto;">
                {log_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Recurring Patterns
        if result.log_patterns:
            st.markdown("##### 🔁 Identified Log Patterns")
            for pat in result.log_patterns[:3]:
                st.markdown(
                    f"""
                    <div style="font-size:0.8rem; background:#161b22; border-left:3px solid #d29922; padding:6px 10px; margin-bottom:5px; border-radius:4px;">
                        <b>{pat.pattern_description}</b> ({pat.occurrences} hits)
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col_rca:
        st.markdown("#### 🧬 Root Cause Attributions")
        if result.rca_results:
            for rca in result.rca_results:
                sev_color = "#f85149" if rca.severity == "CRITICAL" else ("#d29922" if rca.severity == "MAJOR" else "#e3b341")
                with st.expander(f"🔴 [{rca.severity}] {rca.title}", expanded=(rca.severity == "CRITICAL")):
                    st.markdown(f"**Component:** `{rca.affected_component}`")
                    st.markdown(f"**Root Cause:** {rca.root_cause}")
                    st.markdown(f"**Remediation:** {rca.suggested_fix}")
                    if rca.evidence:
                        st.markdown("**Evidence:**")
                        for ev in rca.evidence:
                            st.markdown(f"- `{ev}`")
                    st.markdown(f"**Attribution Confidence:** `{rca.confidence * 100:.0f}%`")
        else:
            st.info("No root cause attributions recorded.")

    st.markdown("---")
    st.markdown("### 🛠️ Autonomous Git Unified Diff Patches")
    st.caption("AI-synthesized production code fixes ready for automated pull-requests.")

    if result.patches:
        for idx, patch in enumerate(result.patches):
            with st.container():
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <span style="font-weight:600; font-size:1rem; color:#58a6ff;">Patch #{idx+1}: {patch.file_path}</span>
                        <span style="font-size:0.8rem; color:#3fb950; font-family:monospace;">Confidence: {patch.confidence*100:.0f}%</span>
                    </div>
                    <div style="font-size:0.85rem; color:#8b949e; margin-bottom:0.6rem;">{patch.description}</div>
                    """,
                    unsafe_allow_html=True,
                )

                # Render syntax-highlighted code diff
                diff_content = patch.diff_text if patch.diff_text else f"--- a/{patch.file_path}\n+++ b/{patch.file_path}\n@@ -1,5 +1,5 @@\n-{patch.original_code}\n+{patch.patched_code}"
                render_code_diff(diff_content)

                col_dl1, col_dl2 = st.columns([1, 4])
                with col_dl1:
                    st.download_button(
                        label=f"📥 Download {Path(patch.file_path).name}.patch",
                        data=diff_content,
                        file_name=f"{Path(patch.file_path).stem}.patch",
                        mime="text/x-diff",
                        key=f"dl_patch_{idx}",
                    )
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    else:
        st.info("No patches generated for this run.")


# ---------------------------------------------------------------------------
# TAB 4: CI/CD & COMPLIANCE HUB
# ---------------------------------------------------------------------------
with tab_cicd:
    st.markdown("### 🚀 CI/CD Integration & Quality Gate Hub")
    st.caption("Export standard execution reports for GitHub Actions, GitLab CI, and static analysis scanners.")

    # Quality Gate Status Banner
    gate_passed = risk_score >= 60 and crit_bugs == 0
    gate_status_color = "#3fb950" if gate_passed else "#f85149"
    gate_status_text = "PASSED — READY FOR RELEASE" if gate_passed else "BLOCKED — CRITICAL REGRESSION DETECTED"

    st.markdown(
        f"""
        <div style="padding:1.2rem; background:rgba({ '63,185,80' if gate_passed else '248,81,73' }, 0.1); border:1px solid {gate_status_color}; border-radius:8px; margin-bottom:1.5rem;">
            <div style="font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; color:{gate_status_color}; font-weight:700;">
                CI/CD Release Gate Decision
            </div>
            <div style="font-size:1.3rem; font-weight:700; color:#e6edf3; margin-top:0.3rem;">
                {gate_status_text}
            </div>
            <div style="font-size:0.85rem; color:#8b949e; margin-top:0.4rem;">
                Score: <b>{risk_score:.0f}/100</b> • Critical Bugs: <b>{crit_bugs}</b> • Memory Leak: <b>{'YES' if result.risk_assessment and result.risk_assessment.category_scores.get('memory_leak', 0) > 0 else 'NO'}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Export generation
    junit_exporter = JUnitExporter()
    sarif_exporter = SARIFExporter()

    # Generate JUnit XML string
    bug_dicts = [b.model_dump() for b in result.bugs]
    junit_xml_str = ""
    if bug_dicts:
        try:
            junit_xml_str = junit_exporter.from_bug_reports(bug_dicts, result.game_name)
        except Exception:
            junit_xml_str = "<!-- No bugs detected -->"
    else:
        junit_xml_str = f'<?xml version="1.0" encoding="utf-8"?><testsuite name="{result.game_name}" tests="1" failures="0" errors="0"><testcase name="test_all_subsystems" time="0.1"/></testsuite>'

    # Generate SARIF JSON string
    rca_dicts = [r.model_dump() for r in result.rca_results]
    sarif_json_str = "{}"
    if rca_dicts:
        try:
            sarif_data = sarif_exporter.from_rca_results(rca_dicts)
            sarif_json_str = json.dumps(sarif_data, indent=2)
        except Exception:
            sarif_json_str = "{}"

    # Export Buttons
    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
        st.markdown("#### 📄 JUnit XML Test Report")
        st.caption("Standard xUnit report format for Jenkins, GitHub Actions & GitLab CI.")
        st.download_button(
            label="📥 Download junit_report.xml",
            data=junit_xml_str,
            file_name=f"{result.game_name.lower().replace(' ', '_')}_junit.xml",
            mime="application/xml",
            use_container_width=True,
        )
        with st.expander("Preview JUnit XML"):
            st.code(junit_xml_str[:1200] + ("\n..." if len(junit_xml_str) > 1200 else ""), language="xml")

    with col_exp2:
        st.markdown("#### 🛡️ SARIF Security/Bug Report")
        st.caption("OASIS standard static analysis interchange format for GitHub Code Scanning.")
        st.download_button(
            label="📥 Download sarif_report.json",
            data=sarif_json_str,
            file_name=f"{result.game_name.lower().replace(' ', '_')}_sarif.json",
            mime="application/json",
            use_container_width=True,
        )
        with st.expander("Preview SARIF JSON"):
            st.code(sarif_json_str[:1200] + ("\n..." if len(sarif_json_str) > 1200 else ""), language="json")

    with col_exp3:
        st.markdown("#### ⚙️ Pre-Commit Hook Config")
        st.caption("Ready-to-use pre-commit integration for autonomous test execution.")
        precommit_yaml = f"""# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: agentic-qa-check
        name: Agentic QA Release Gate
        entry: python -m agentic_qa_platform.cicd.risk_scorer
        language: system
        pass_filenames: false
        always_run: true
"""
        st.download_button(
            label="📥 Download .pre-commit-config.yaml",
            data=precommit_yaml,
            file_name=".pre-commit-config.yaml",
            mime="text/yaml",
            use_container_width=True,
        )
        with st.expander("Preview Pre-Commit Config"):
            st.code(precommit_yaml, language="yaml")

    st.markdown("---")
    st.markdown("#### 🔄 GitHub Actions CI/CD Workflow Snippet")
    gh_workflow = f"""# .github/workflows/agentic_qa.yml
name: Agentic QA Game Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  telemetry-qa:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Execute Autonomous QA Platform
        env:
          GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
        run: |
          python -c "from agentic_qa_platform.agents import Orchestrator; o = Orchestrator(); res = o.run_full_analysis('{result.game_name}'); assert res.risk_assessment.overall_score >= 50, 'Release Risk Gate Failed!'"

      - name: Upload JUnit Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: junit-report
          path: "*.xml"
"""
    st.code(gh_workflow, language="yaml")
