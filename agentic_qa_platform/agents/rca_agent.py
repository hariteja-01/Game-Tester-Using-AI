"""
RCA Agent — AI-powered Root Cause Analysis for game bugs.

Combines telemetry anomalies with log patterns to identify root causes
of bugs discovered during automated testing. Uses Google Gemini for
intelligent analysis and falls back to rule-based heuristics.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agentic_qa_platform.agents.stress_agent import AgentTrace, TraceStep


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BugReport(BaseModel):
    """A single bug report discovered during testing."""

    id: str = Field(default_factory=lambda: f"BUG-{uuid.uuid4().hex[:8].upper()}")
    title: str
    description: str
    category: str
    severity: str = Field(description="CRITICAL, MAJOR, or MINOR")
    affected_file: Optional[str] = None
    line_number: Optional[int] = None


class RCAResult(BaseModel):
    """Root Cause Analysis result for a single bug."""

    bug_id: str
    title: str
    root_cause: str
    severity: str = Field(description="CRITICAL, MAJOR, or MINOR")
    affected_component: str
    reproduction_steps: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    suggested_fix: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


# ---------------------------------------------------------------------------
# Rule-based severity classification
# ---------------------------------------------------------------------------

_CRITICAL_KEYWORDS = {
    "crash", "segfault", "deadlock", "data loss", "corruption",
    "out of memory", "oom", "unhandled exception", "fatal", "bsod",
    "access violation", "null pointer", "stack overflow",
}

_MAJOR_KEYWORDS = {
    "freeze", "hang", "memory leak", "frame drop", "stutter",
    "desync", "disconnect", "timeout", "high latency", "regression",
    "rendering artifact", "shader error", "asset missing",
}


# ---------------------------------------------------------------------------
# RCAAgent
# ---------------------------------------------------------------------------

class RCAAgent:
    """Performs Root Cause Analysis on bugs using Gemini AI.

    Parameters
    ----------
    api_key : str
        Google Gemini API key.  Pass ``""`` to use rule-based RCA only.
    """

    MODEL = "gemini-flash-latest"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None
        self._trace = AgentTrace(
            agent_name="RCAAgent",
            started_at=datetime.now(timezone.utc),
        )

        if self._api_key:
            try:
                from google import genai  # type: ignore[import-untyped]
                from google.genai import types  # type: ignore[import-untyped]

                self._client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=5.0))
                logger.info("RCAAgent: Gemini client initialised.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("RCAAgent: Gemini client init failed (%s).", exc)
                self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_bugs(
        self,
        game_name: str,
        telemetry_report: Any,
        log_entries: List[Dict[str, Any]],
    ) -> List[RCAResult]:
        """Perform root-cause analysis on bugs found during testing.

        Parameters
        ----------
        game_name:
            Name of the game under test.
        telemetry_report:
            A ``TelemetryReport`` instance (or compatible dict) with
            anomaly and summary data.
        log_entries:
            Parsed log entries, each a dict with at least ``level``,
            ``message``, and optionally ``timestamp``, ``source``.

        Returns
        -------
        List[RCAResult]
            One RCA result per identified bug.
        """
        t0 = time.perf_counter()
        results: List[RCAResult] = []

        # 1. Extract bug signals from telemetry + logs
        bugs = self._extract_bugs(telemetry_report, log_entries)

        if not bugs:
            self._record_step(
                "analyze_bugs",
                input_data=f"game={game_name}, logs={len(log_entries)}",
                output_data="No bugs identified",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            self._trace.status = "completed"
            self._trace.completed_at = datetime.now(timezone.utc)
            return results

        # 2. RCA via Gemini or heuristics
        if self._client is not None:
            try:
                results = self._rca_via_gemini(game_name, bugs, telemetry_report, log_entries)
            except Exception as exc:  # noqa: BLE001
                logger.warning("RCAAgent: Gemini RCA failed (%s). Using rule-based RCA.", exc)
                self._record_step(
                    "gemini_rca_fallback_trigger",
                    input_data=game_name,
                    output_data=f"Error: {exc}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
                results = self._rca_heuristic(game_name, bugs, telemetry_report)
        else:
            results = self._rca_heuristic(game_name, bugs, telemetry_report)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "analyze_bugs",
            input_data=f"game={game_name}, bugs={len(bugs)}, logs={len(log_entries)}",
            output_data=f"{len(results)} RCA results produced",
            duration_ms=elapsed_ms,
        )
        self._trace.status = "completed"
        self._trace.completed_at = datetime.now(timezone.utc)
        return results

    def classify_severity(self, bug_description: str, metrics: Dict[str, Any]) -> str:
        """Classify bug severity as CRITICAL, MAJOR, or MINOR.

        Uses keyword matching and metric thresholds.
        """
        t0 = time.perf_counter()
        desc_lower = bug_description.lower()

        # Check critical keywords
        for kw in _CRITICAL_KEYWORDS:
            if kw in desc_lower:
                severity = "CRITICAL"
                self._record_step(
                    "classify_severity",
                    input_data=bug_description[:120],
                    output_data=severity,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
                return severity

        # Check major keywords
        for kw in _MAJOR_KEYWORDS:
            if kw in desc_lower:
                severity = "MAJOR"
                self._record_step(
                    "classify_severity",
                    input_data=bug_description[:120],
                    output_data=severity,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
                return severity

        # Metric-based escalation
        cpu = metrics.get("max_cpu", 0)
        fps = metrics.get("min_fps", 60)
        if cpu > 95 or fps < 10:
            severity = "CRITICAL"
        elif cpu > 85 or fps < 20:
            severity = "MAJOR"
        else:
            severity = "MINOR"

        self._record_step(
            "classify_severity",
            input_data=bug_description[:120],
            output_data=severity,
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
        return severity

    def get_trace(self) -> AgentTrace:
        """Return the execution trace for this agent."""
        if not self._trace.start_time:
            self._trace.start_time = self._trace.started_at
        if not self._trace.end_time:
            self._trace.end_time = self._trace.completed_at or datetime.now(timezone.utc)
        if self._trace.start_time and self._trace.end_time:
            self._trace.execution_time_seconds = round(
                max(0.01, (self._trace.end_time - self._trace.start_time).total_seconds()), 3
            )
        return self._trace

    # ------------------------------------------------------------------
    # Bug extraction
    # ------------------------------------------------------------------

    def _extract_bugs(
        self,
        telemetry_report: Any,
        log_entries: List[Dict[str, Any]],
    ) -> List[BugReport]:
        """Heuristically extract bug signals from telemetry and logs."""
        bugs: List[BugReport] = []

        # Extract from telemetry anomalies
        anomalies: list = []
        if hasattr(telemetry_report, "anomalies"):
            anomalies = telemetry_report.anomalies
        elif isinstance(telemetry_report, dict):
            anomalies = telemetry_report.get("anomalies", [])

        anomaly_categories: Dict[str, List[Any]] = {}
        for a in anomalies:
            metric = a.metric if hasattr(a, "metric") else a.get("metric", "unknown")
            anomaly_categories.setdefault(metric, []).append(a)

        for metric, group in anomaly_categories.items():
            msg = group[0].message if hasattr(group[0], "message") else group[0].get("message", "")
            severity = "MAJOR" if len(group) > 3 else "MINOR"
            if "cpu" in metric.lower() and len(group) > 5:
                severity = "CRITICAL"

            bugs.append(
                BugReport(
                    title=f"Telemetry anomaly: {metric}",
                    description=f"{len(group)} occurrences detected. Sample: {msg}",
                    category="performance",
                    severity=severity,
                )
            )

        # Extract from log entries (ERROR and CRITICAL level)
        for entry in log_entries:
            raw_level = getattr(entry, "level", None) or (entry.get("level") if isinstance(entry, dict) else "")
            if hasattr(raw_level, "value"):
                raw_level = raw_level.value
            level = str(raw_level).upper()

            if level in ("ERROR", "CRITICAL", "FATAL"):
                message = getattr(entry, "message", None) or (entry.get("message") if isinstance(entry, dict) else "Unknown error")
                source = getattr(entry, "source", None) or (entry.get("source") if isinstance(entry, dict) else "unknown")
                meta = getattr(entry, "metadata", None) or (entry.get("metadata", {}) if isinstance(entry, dict) else {})
                file_val = meta.get("file") if isinstance(meta, dict) else (entry.get("file") if isinstance(entry, dict) else None)
                line_val = meta.get("line") if isinstance(meta, dict) else (entry.get("line") if isinstance(entry, dict) else None)

                desc_lower = str(message).lower()
                severity = "MINOR"
                for kw in _CRITICAL_KEYWORDS:
                    if kw in desc_lower:
                        severity = "CRITICAL"
                        break
                else:
                    for kw in _MAJOR_KEYWORDS:
                        if kw in desc_lower:
                            severity = "MAJOR"
                            break

                bugs.append(
                    BugReport(
                        title=f"Log error in {source}",
                        description=str(message),
                        category=str(source),
                        severity=severity,
                        affected_file=file_val,
                        line_number=line_val,
                    )
                )

        return bugs

    # ------------------------------------------------------------------
    # Gemini RCA
    # ------------------------------------------------------------------

    def _rca_via_gemini(
        self,
        game_name: str,
        bugs: List[BugReport],
        telemetry_report: Any,
        log_entries: List[Dict[str, Any]],
    ) -> List[RCAResult]:
        """Use Gemini AI for deep root-cause analysis."""
        t0 = time.perf_counter()

        # Build summary context
        summary_data: Dict[str, Any] = {}
        if hasattr(telemetry_report, "summary"):
            s = telemetry_report.summary
            summary_data = {
                "avg_cpu": getattr(s, "avg_cpu", 0),
                "max_cpu": getattr(s, "max_cpu", 0),
                "avg_ram": getattr(s, "avg_ram", 0),
                "max_ram": getattr(s, "max_ram", 0),
                "avg_fps": getattr(s, "avg_fps", 0),
                "min_fps": getattr(s, "min_fps", 0),
            }

        bugs_json = [b.model_dump() for b in bugs[:10]]  # Limit to 10
        log_sample = [
            (e.model_dump() if hasattr(e, "model_dump") else e) for e in log_entries[:20]
        ]

        prompt = (
            "You are an expert game QA engineer performing Root Cause Analysis.\n"
            f"Game: {game_name}\n\n"
            f"Telemetry Summary: {json.dumps(summary_data)}\n\n"
            f"Bugs found: {json.dumps(bugs_json, default=str)}\n\n"
            f"Recent log entries: {json.dumps(log_sample, default=str)}\n\n"
            "For EACH bug, determine the root cause. Return ONLY a JSON array where "
            "each element has:\n"
            '  "bug_id": string (from input),\n'
            '  "title": string,\n'
            '  "root_cause": string (detailed technical explanation),\n'
            '  "severity": "CRITICAL" | "MAJOR" | "MINOR",\n'
            '  "affected_component": string,\n'
            '  "reproduction_steps": [string, ...],\n'
            '  "evidence": [string, ...],\n'
            '  "suggested_fix": string,\n'
            '  "confidence": float 0.0-1.0\n\n'
            "Return ONLY valid JSON — no markdown fences, no commentary."
        )

        response = self._client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )
        raw_text: str = response.text.strip()

        # Strip markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        data = json.loads(raw_text)
        if not isinstance(data, list):
            raise ValueError("Gemini RCA response is not a JSON array.")

        results: List[RCAResult] = []
        for item in data:
            results.append(
                RCAResult(
                    bug_id=item.get("bug_id", f"BUG-{uuid.uuid4().hex[:8].upper()}"),
                    title=item.get("title", "Unknown"),
                    root_cause=item.get("root_cause", "Undetermined"),
                    severity=item.get("severity", "MINOR"),
                    affected_component=item.get("affected_component", "Unknown"),
                    reproduction_steps=item.get("reproduction_steps", []),
                    evidence=item.get("evidence", []),
                    suggested_fix=item.get("suggested_fix", ""),
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                )
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "gemini_rca",
            input_data=f"{len(bugs)} bugs",
            output_data=f"Produced {len(results)} RCA results via Gemini",
            duration_ms=elapsed_ms,
        )
        return results

    # ------------------------------------------------------------------
    # Heuristic RCA (fallback)
    # ------------------------------------------------------------------

    def _rca_heuristic(
        self,
        game_name: str,
        bugs: List[BugReport],
        telemetry_report: Any,
    ) -> List[RCAResult]:
        """Deterministic, rule-based root-cause analysis."""
        results: List[RCAResult] = []

        for bug in bugs:
            root_cause, component, fix, confidence = self._classify_bug_heuristic(bug)

            results.append(
                RCAResult(
                    bug_id=bug.id,
                    title=bug.title,
                    root_cause=root_cause,
                    severity=bug.severity,
                    affected_component=component,
                    reproduction_steps=[
                        f"Launch {game_name}",
                        "Reproduce the workload described in the bug",
                        f"Observe: {bug.description[:200]}",
                    ],
                    evidence=[
                        f"Bug category: {bug.category}",
                        f"Description: {bug.description[:300]}",
                    ],
                    suggested_fix=fix,
                    confidence=confidence,
                )
            )

        return results

    def _classify_bug_heuristic(
        self, bug: BugReport
    ) -> tuple[str, str, str, float]:
        """Return (root_cause, component, fix, confidence) for a bug."""
        desc = bug.description.lower()

        if "cpu" in desc or "performance" in bug.category:
            return (
                "Excessive CPU utilisation caused by unoptimised per-frame workloads.",
                "Engine/Core Loop",
                "Profile the main-thread hot path and offload expensive computations to worker threads.",
                0.65,
            )
        if "ram" in desc or "memory" in desc:
            return (
                "Uncontrolled memory growth — likely unreleased asset references or pool overflow.",
                "Memory Manager",
                "Implement RAII / ref-counted handles and add pool-size caps with eviction policies.",
                0.60,
            )
        if "fps" in desc or "frame" in desc:
            return (
                "Frame-time spikes exceeding budget, potentially GPU-bound or draw-call limited.",
                "Rendering Pipeline",
                "Reduce overdraw, batch draw calls, and audit shader complexity on affected scenes.",
                0.55,
            )
        if "crash" in desc or "fatal" in desc or "exception" in desc:
            return (
                "Unhandled exception or null-pointer dereference leading to process termination.",
                "Runtime / Exception Handler",
                "Add defensive null-checks and structured exception handling around the crash site.",
                0.70,
            )
        if "network" in desc or "desync" in desc or "timeout" in desc:
            return (
                "Network subsystem failure under adverse latency / packet-loss conditions.",
                "Netcode / Replication",
                "Implement client-side prediction, server reconciliation, and retry with exponential backoff.",
                0.50,
            )

        # Generic fallback
        return (
            f"Undetermined root cause for: {bug.title}",
            "Unknown",
            "Investigate with a debugger attached and collect a detailed reproduction trace.",
            0.30,
        )

    # ------------------------------------------------------------------
    # Trace helper
    # ------------------------------------------------------------------

    def _record_step(
        self,
        step_name: str,
        input_data: str,
        output_data: str,
        duration_ms: float,
    ) -> None:
        self._trace.steps.append(
            TraceStep(
                step_name=step_name,
                input_data=input_data,
                output_data=output_data,
                duration_ms=duration_ms,
            )
        )
