"""
Telemetry Agent — System metrics collection and AI-powered analysis.

Supports two collection modes:
  * **live** — captures real CPU, RAM, and I/O via ``psutil``
    (optionally delegating to ``ProcessMonitor`` from the telemetry package).
  * **synthetic** — generates realistic metric curves for demo / CI
    environments where live monitoring is unavailable.

Analysis is performed by Gemini AI when an API key is provided;
otherwise a deterministic, rule-based heuristic grades performance.
"""

from __future__ import annotations

import logging
import math
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Re-use trace models from stress_agent (single source of truth)
# ---------------------------------------------------------------------------
from agentic_qa_platform.agents.stress_agent import AgentTrace, TraceStep  # noqa: E402


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TelemetrySnapshot(BaseModel):
    """A single point-in-time telemetry reading."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_percent: float = 0.0
    fps: float = 60.0
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    gpu_percent: Optional[float] = None


class TelemetryAnomaly(BaseModel):
    """An anomaly detected during telemetry collection."""

    metric: str
    value: float
    threshold: float
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetrySummary(BaseModel):
    """Aggregate statistics over a telemetry collection window."""

    avg_cpu: float = 0.0
    max_cpu: float = 0.0
    avg_ram: float = 0.0
    max_ram: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = 0.0
    total_io_mb: float = 0.0


class TelemetryReport(BaseModel):
    """Complete telemetry collection report."""

    game_name: str
    collection_mode: str
    duration_seconds: float
    snapshots: List[TelemetrySnapshot] = Field(default_factory=list)
    anomalies: List[TelemetryAnomaly] = Field(default_factory=list)
    summary: TelemetrySummary = Field(default_factory=TelemetrySummary)


class TelemetryAnalysis(BaseModel):
    """AI or heuristic analysis of a telemetry report."""

    summary: str
    performance_grade: str = Field(
        description="Letter grade A through F"
    )
    bottlenecks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    memory_leak_probability: float = Field(ge=0.0, le=1.0, default=0.0)


# ---------------------------------------------------------------------------
# Thresholds for anomaly & heuristic analysis
# ---------------------------------------------------------------------------
_CPU_ANOMALY_THRESHOLD = 90.0
_RAM_ANOMALY_THRESHOLD_MB = 3500.0
_FPS_ANOMALY_THRESHOLD = 25.0
_IO_ANOMALY_THRESHOLD_MB = 150.0


# ---------------------------------------------------------------------------
# TelemetryAgent
# ---------------------------------------------------------------------------

class TelemetryAgent:
    """Collects system telemetry and analyses it for game QA.

    Parameters
    ----------
    api_key : str
        Google Gemini API key.  Pass ``""`` to rely on rule-based analysis.
    """

    MODEL = "gemini-flash-latest"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None
        self._trace = AgentTrace(
            agent_name="TelemetryAgent",
            started_at=datetime.now(timezone.utc),
        )

        if self._api_key:
            try:
                from google import genai  # type: ignore[import-untyped]
                from google.genai import types  # type: ignore[import-untyped]

                self._client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=5.0))
                logger.info("TelemetryAgent: Gemini client initialised.")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TelemetryAgent: Gemini client init failed (%s). "
                    "Analysis will use heuristics.",
                    exc,
                )
                self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect_telemetry(
        self,
        game_name: str,
        duration: float = 5.0,
        mode: str = "synthetic",
    ) -> TelemetryReport:
        """Collect telemetry snapshots for *duration* seconds.

        Parameters
        ----------
        game_name:
            Display name of the game under test.
        duration:
            Collection window in seconds.
        mode:
            ``"live"`` to sample real system metrics via psutil /
            ``ProcessMonitor``; ``"synthetic"`` to generate realistic curves.
        """
        t0 = time.perf_counter()
        snapshots: List[TelemetrySnapshot] = []

        if mode == "live":
            snapshots = self._collect_live(duration)
        else:
            snapshots = self._collect_synthetic(duration)

        anomalies = self._detect_anomalies(snapshots)
        summary = self._compute_summary(snapshots)

        report = TelemetryReport(
            game_name=game_name,
            collection_mode=mode,
            duration_seconds=duration,
            snapshots=snapshots,
            anomalies=anomalies,
            summary=summary,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "collect_telemetry",
            input_data=f"game={game_name}, mode={mode}, duration={duration}s",
            output_data=(
                f"{len(snapshots)} snapshots, {len(anomalies)} anomalies, "
                f"avg_cpu={summary.avg_cpu:.1f}%, avg_fps={summary.avg_fps:.1f}"
            ),
            duration_ms=elapsed_ms,
        )
        return report

    def analyze_telemetry(self, report: TelemetryReport) -> TelemetryAnalysis:
        """Analyse a telemetry report and produce a graded assessment."""
        t0 = time.perf_counter()

        if self._client is not None:
            try:
                analysis = self._analyze_via_gemini(report)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TelemetryAgent: Gemini analysis failed (%s). Using heuristics.",
                    exc,
                )
                self._record_step(
                    "gemini_analysis_fallback_trigger",
                    input_data=report.game_name,
                    output_data=f"Error: {exc}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
                analysis = self._analyze_heuristic(report)
        else:
            analysis = self._analyze_heuristic(report)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "analyze_telemetry",
            input_data=report.game_name,
            output_data=f"Grade={analysis.performance_grade}, bottlenecks={len(analysis.bottlenecks)}",
            duration_ms=elapsed_ms,
        )
        self._trace.status = "completed"
        self._trace.completed_at = datetime.now(timezone.utc)
        return analysis

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
    # Live collection
    # ------------------------------------------------------------------

    def _collect_live(self, duration: float) -> List[TelemetrySnapshot]:
        """Sample real system metrics via ``psutil`` / ``ProcessMonitor``."""
        snapshots: List[TelemetrySnapshot] = []
        interval = 0.5
        deadline = time.monotonic() + duration

        # Attempt to use ProcessMonitor from the telemetry package
        process_monitor: Any = None
        try:
            from agentic_qa_platform.telemetry.process_monitor import ProcessMonitor

            process_monitor = ProcessMonitor()
            logger.info("TelemetryAgent: Using ProcessMonitor for live collection.")
        except ImportError:
            logger.info(
                "TelemetryAgent: ProcessMonitor not available — "
                "falling back to raw psutil."
            )

        try:
            import psutil  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "TelemetryAgent: psutil not installed. "
                "Returning empty live snapshot list."
            )
            return snapshots

        io_start = psutil.disk_io_counters()
        while time.monotonic() < deadline:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            # Attempt to get richer data from ProcessMonitor
            fps_val = 60.0  # no real FPS source on desktop
            gpu_val: Optional[float] = None
            if process_monitor is not None:
                try:
                    pm_data = process_monitor.snapshot()
                    fps_val = pm_data.get("fps", 60.0)
                    gpu_val = pm_data.get("gpu_percent")
                except Exception:  # noqa: BLE001
                    pass

            io_now = psutil.disk_io_counters()
            io_read = (io_now.read_bytes - io_start.read_bytes) / (1024 * 1024)
            io_write = (io_now.write_bytes - io_start.write_bytes) / (1024 * 1024)

            snapshots.append(
                TelemetrySnapshot(
                    cpu_percent=cpu,
                    ram_used_mb=mem.used / (1024 * 1024),
                    ram_percent=mem.percent,
                    fps=fps_val,
                    io_read_mb=io_read,
                    io_write_mb=io_write,
                    gpu_percent=gpu_val,
                )
            )
            time.sleep(min(interval, max(0, deadline - time.monotonic())))

        return snapshots

    # ------------------------------------------------------------------
    # Synthetic collection
    # ------------------------------------------------------------------

    def _collect_synthetic(self, duration: float) -> List[TelemetrySnapshot]:
        """Generate realistic telemetry curves for CI/demo purposes."""
        snapshots: List[TelemetrySnapshot] = []
        interval = 0.25
        steps = max(1, int(duration / interval))

        base_cpu = random.uniform(25.0, 45.0)
        base_ram = random.uniform(1500.0, 2800.0)
        base_fps = random.uniform(55.0, 120.0)
        io_cumulative = 0.0
        ram_drift = random.uniform(0.0, 3.0)  # MB per step (leak sim)

        for i in range(steps):
            t_frac = i / max(1, steps - 1)

            # CPU: smooth wave with occasional spike
            cpu = base_cpu + 15.0 * math.sin(2 * math.pi * t_frac * 3)
            if random.random() < 0.08:
                cpu += random.uniform(20.0, 50.0)
            cpu = max(0.0, min(100.0, cpu))

            # RAM: gradual drift upward (simulates leak)
            ram = base_ram + ram_drift * i + random.gauss(0, 30)
            ram = max(500.0, ram)

            # FPS: inversely correlated with CPU
            fps = base_fps - (cpu - base_cpu) * 0.5 + random.gauss(0, 3)
            fps = max(5.0, min(240.0, fps))

            # I/O: bursty
            io_delta = random.expovariate(1.0 / 2.0)
            io_cumulative += io_delta

            snapshots.append(
                TelemetrySnapshot(
                    cpu_percent=round(cpu, 1),
                    ram_used_mb=round(ram, 1),
                    ram_percent=round(ram / 16384 * 100, 1),
                    fps=round(fps, 1),
                    io_read_mb=round(io_cumulative * 0.6, 2),
                    io_write_mb=round(io_cumulative * 0.4, 2),
                )
            )

        return snapshots

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def _detect_anomalies(
        self, snapshots: List[TelemetrySnapshot]
    ) -> List[TelemetryAnomaly]:
        anomalies: List[TelemetryAnomaly] = []
        for snap in snapshots:
            if snap.cpu_percent > _CPU_ANOMALY_THRESHOLD:
                anomalies.append(
                    TelemetryAnomaly(
                        metric="cpu_percent",
                        value=snap.cpu_percent,
                        threshold=_CPU_ANOMALY_THRESHOLD,
                        message=f"CPU spike: {snap.cpu_percent:.1f}% exceeds {_CPU_ANOMALY_THRESHOLD}%",
                        timestamp=snap.timestamp,
                    )
                )
            if snap.ram_used_mb > _RAM_ANOMALY_THRESHOLD_MB:
                anomalies.append(
                    TelemetryAnomaly(
                        metric="ram_used_mb",
                        value=snap.ram_used_mb,
                        threshold=_RAM_ANOMALY_THRESHOLD_MB,
                        message=f"High RAM: {snap.ram_used_mb:.0f} MB exceeds {_RAM_ANOMALY_THRESHOLD_MB:.0f} MB",
                        timestamp=snap.timestamp,
                    )
                )
            if snap.fps < _FPS_ANOMALY_THRESHOLD:
                anomalies.append(
                    TelemetryAnomaly(
                        metric="fps",
                        value=snap.fps,
                        threshold=_FPS_ANOMALY_THRESHOLD,
                        message=f"Low FPS: {snap.fps:.1f} below {_FPS_ANOMALY_THRESHOLD}",
                        timestamp=snap.timestamp,
                    )
                )
        return anomalies

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _compute_summary(
        self, snapshots: List[TelemetrySnapshot]
    ) -> TelemetrySummary:
        if not snapshots:
            return TelemetrySummary()

        cpus = [s.cpu_percent for s in snapshots]
        rams = [s.ram_used_mb for s in snapshots]
        fpss = [s.fps for s in snapshots]
        total_io = sum(s.io_read_mb + s.io_write_mb for s in snapshots)

        return TelemetrySummary(
            avg_cpu=round(sum(cpus) / len(cpus), 2),
            max_cpu=round(max(cpus), 2),
            avg_ram=round(sum(rams) / len(rams), 2),
            max_ram=round(max(rams), 2),
            avg_fps=round(sum(fpss) / len(fpss), 2),
            min_fps=round(min(fpss), 2),
            total_io_mb=round(total_io, 2),
        )

    # ------------------------------------------------------------------
    # Gemini analysis
    # ------------------------------------------------------------------

    def _analyze_via_gemini(self, report: TelemetryReport) -> TelemetryAnalysis:
        """Use Gemini to produce an expert telemetry analysis."""
        t0 = time.perf_counter()
        summary = report.summary

        prompt = (
            "You are an expert game performance analyst. Analyse the following "
            "telemetry summary and anomaly data, then return ONLY valid JSON "
            "(no markdown fences, no commentary) with these fields:\n"
            '  "summary": string (2-4 sentence analysis),\n'
            '  "performance_grade": string (A, B, C, D, or F),\n'
            '  "bottlenecks": [string, ...],\n'
            '  "recommendations": [string, ...],\n'
            '  "memory_leak_probability": float between 0.0 and 1.0\n\n'
            f"Game: {report.game_name}\n"
            f"Duration: {report.duration_seconds}s | Mode: {report.collection_mode}\n"
            f"Avg CPU: {summary.avg_cpu}% | Max CPU: {summary.max_cpu}%\n"
            f"Avg RAM: {summary.avg_ram} MB | Max RAM: {summary.max_ram} MB\n"
            f"Avg FPS: {summary.avg_fps} | Min FPS: {summary.min_fps}\n"
            f"Total I/O: {summary.total_io_mb} MB\n"
            f"Anomalies detected: {len(report.anomalies)}\n"
        )
        if report.anomalies:
            anomaly_lines = "\n".join(
                f"  - {a.message}" for a in report.anomalies[:20]
            )
            prompt += f"Anomaly details (first 20):\n{anomaly_lines}\n"

        response = self._client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )
        raw_text: str = response.text.strip()

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        import json

        data = json.loads(raw_text)

        analysis = TelemetryAnalysis(
            summary=data.get("summary", "Analysis unavailable."),
            performance_grade=data.get("performance_grade", "C"),
            bottlenecks=data.get("bottlenecks", []),
            recommendations=data.get("recommendations", []),
            memory_leak_probability=max(
                0.0, min(1.0, float(data.get("memory_leak_probability", 0.0)))
            ),
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "gemini_analysis",
            input_data=report.game_name,
            output_data=f"Grade={analysis.performance_grade}",
            duration_ms=elapsed_ms,
        )
        return analysis

    # ------------------------------------------------------------------
    # Heuristic analysis (fallback)
    # ------------------------------------------------------------------

    def _analyze_heuristic(self, report: TelemetryReport) -> TelemetryAnalysis:
        """Rule-based performance analysis when Gemini is unavailable."""
        s = report.summary
        bottlenecks: List[str] = []
        recommendations: List[str] = []

        # Score starts at 100, deductions determine grade
        score = 100.0

        # CPU assessment
        if s.max_cpu > 95:
            bottlenecks.append("Critical CPU saturation detected.")
            recommendations.append("Profile and optimise hottest code paths; consider job offloading.")
            score -= 25
        elif s.avg_cpu > 75:
            bottlenecks.append("Sustained high CPU usage.")
            recommendations.append("Review per-frame workload budget and reduce tick-rate for heavy systems.")
            score -= 15

        # RAM assessment
        if s.max_ram > 4000:
            bottlenecks.append("Excessive memory usage (>4 GB).")
            recommendations.append("Audit asset pools and implement streaming budgets.")
            score -= 20
        elif s.max_ram > 3000:
            bottlenecks.append("Elevated memory usage.")
            recommendations.append("Check for unreleased texture/mesh references.")
            score -= 10

        # FPS assessment
        if s.min_fps < 15:
            bottlenecks.append("Severe frame-rate drops below 15 FPS.")
            recommendations.append("Identify and address draw-call or GPU-bound spikes.")
            score -= 25
        elif s.min_fps < 30:
            bottlenecks.append("Frame-rate drops below 30 FPS target.")
            recommendations.append("Review particle systems and shadow cascade settings.")
            score -= 15

        # I/O assessment
        if s.total_io_mb > 500:
            bottlenecks.append("High cumulative I/O throughput.")
            recommendations.append("Implement asset pre-loading and I/O request coalescing.")
            score -= 10

        # Anomaly density
        anomaly_rate = len(report.anomalies) / max(1, len(report.snapshots))
        if anomaly_rate > 0.5:
            score -= 10

        # Memory-leak heuristic: check if RAM rose monotonically
        ram_values = [snap.ram_used_mb for snap in report.snapshots]
        leak_prob = 0.0
        if len(ram_values) >= 4:
            diffs = [ram_values[i + 1] - ram_values[i] for i in range(len(ram_values) - 1)]
            positive_frac = sum(1 for d in diffs if d > 0) / len(diffs)
            leak_prob = round(min(1.0, max(0.0, positive_frac - 0.3)), 2)
            if leak_prob > 0.5:
                bottlenecks.append("Potential memory leak: RAM grew monotonically.")
                recommendations.append("Run extended soak test and compare heap snapshots.")

        # Grade mapping
        grade_map = [(90, "A"), (75, "B"), (55, "C"), (35, "D")]
        grade = "F"
        for threshold, letter in grade_map:
            if score >= threshold:
                grade = letter
                break

        summary_text = (
            f"Heuristic analysis of '{report.game_name}' telemetry over "
            f"{report.duration_seconds}s. Performance score: {score:.0f}/100 "
            f"(grade {grade}). {len(bottlenecks)} bottleneck(s) identified."
        )

        return TelemetryAnalysis(
            summary=summary_text,
            performance_grade=grade,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            memory_leak_probability=leak_prob,
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
