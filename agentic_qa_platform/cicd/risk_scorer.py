"""Release risk scorer for the Agentic QA Platform.

Computes a deterministic 0-100 Release Risk Score from test-run metrics,
provides per-category breakdowns, and generates actionable recommendations
for CI/CD release gates.

Example usage::

    from agentic_qa_platform.cicd.risk_scorer import RiskScorer, RiskMetrics

    scorer = RiskScorer()
    metrics = RiskMetrics(
        critical_bugs=1,
        major_bugs=3,
        minor_bugs=10,
        avg_cpu_percent=72.0,
        max_cpu_percent=95.0,
        avg_ram_percent=68.0,
        ram_leak_detected=False,
        avg_fps=55.0,
        min_fps=28.0,
        crash_count=0,
    )
    assessment = scorer.calculate_risk_score(metrics)
    breakdown = scorer.get_risk_breakdown(assessment)
    recommendations = scorer.generate_recommendations(assessment)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RISK_LEVEL_CRITICAL = "CRITICAL"
_RISK_LEVEL_HIGH = "HIGH"
_RISK_LEVEL_MEDIUM = "MEDIUM"
_RISK_LEVEL_LOW = "LOW"

# Deduction weights
_CRITICAL_BUG_PENALTY = 15
_MAJOR_BUG_PENALTY = 8
_MINOR_BUG_PENALTY = 2
_CRASH_PENALTY = 10
_HIGH_CPU_PENALTY = 10
_HIGH_RAM_PENALTY = 10
_RAM_LEAK_PENALTY = 20
_LOW_MIN_FPS_PENALTY = 15
_LOW_AVG_FPS_PENALTY = 10

# Thresholds
_CPU_THRESHOLD = 80.0
_RAM_THRESHOLD = 85.0
_MIN_FPS_THRESHOLD = 30.0
_AVG_FPS_THRESHOLD = 60.0


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RiskMetrics(BaseModel):
    """Raw test-run metrics used to compute a release risk score.

    Attributes:
        critical_bugs: Count of critical-severity bugs.
        major_bugs: Count of major-severity bugs.
        minor_bugs: Count of minor-severity bugs.
        avg_cpu_percent: Average CPU utilisation (0-100).
        max_cpu_percent: Peak CPU utilisation (0-100).
        avg_ram_percent: Average RAM utilisation (0-100).
        ram_leak_detected: Whether a memory leak was detected.
        avg_fps: Average frames per second during the test run.
        min_fps: Minimum observed FPS.
        crash_count: Number of application crashes during testing.
        test_coverage_percent: Percentage of test coverage achieved.
    """

    critical_bugs: int = Field(..., ge=0, description="Count of critical bugs")
    major_bugs: int = Field(..., ge=0, description="Count of major bugs")
    minor_bugs: int = Field(..., ge=0, description="Count of minor bugs")
    avg_cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Average CPU %")
    max_cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Peak CPU %")
    avg_ram_percent: float = Field(..., ge=0.0, le=100.0, description="Average RAM %")
    ram_leak_detected: bool = Field(..., description="Memory leak flag")
    avg_fps: float = Field(..., ge=0.0, description="Average FPS")
    min_fps: float = Field(..., ge=0.0, description="Minimum FPS")
    crash_count: int = Field(..., ge=0, description="Crash count")
    test_coverage_percent: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Test coverage %"
    )


class RiskAssessment(BaseModel):
    """Computed risk assessment for a release candidate.

    Attributes:
        overall_score: Aggregate risk score (0 = worst, 100 = best).
        risk_level: Human-readable label: LOW / MEDIUM / HIGH / CRITICAL.
        category_scores: Per-category score breakdown.
        timestamp: UTC timestamp when the assessment was computed.
        recommendations: Actionable recommendation strings.
    """

    overall_score: float = Field(..., ge=0.0, le=100.0, description="0-100 score")
    risk_level: str = Field(..., description="LOW / MEDIUM / HIGH / CRITICAL")
    category_scores: Dict[str, Any] = Field(
        default_factory=dict, description="Per-category scores"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Assessment timestamp (UTC)",
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class RiskScorer:
    """Deterministic release-risk scoring engine.

    The algorithm starts at 100 (perfect) and deducts points for each
    observed risk factor. The final score is clamped to [0, 100].

    Risk levels:
        * **0-30** → CRITICAL
        * **31-50** → HIGH
        * **51-75** → MEDIUM
        * **76-100** → LOW
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_risk_score(self, metrics: RiskMetrics) -> RiskAssessment:
        """Compute the overall release risk score from raw metrics.

        Args:
            metrics: A populated :class:`RiskMetrics` instance.

        Returns:
            A :class:`RiskAssessment` with scores, level, and recommendations.
        """
        # --- per-category deductions ---
        bug_deduction = (
            metrics.critical_bugs * _CRITICAL_BUG_PENALTY
            + metrics.major_bugs * _MAJOR_BUG_PENALTY
            + metrics.minor_bugs * _MINOR_BUG_PENALTY
        )
        stability_deduction = metrics.crash_count * _CRASH_PENALTY
        performance_deduction = 0.0

        if metrics.avg_cpu_percent > _CPU_THRESHOLD:
            performance_deduction += _HIGH_CPU_PENALTY
        if metrics.avg_ram_percent > _RAM_THRESHOLD:
            performance_deduction += _HIGH_RAM_PENALTY

        memory_deduction = _RAM_LEAK_PENALTY if metrics.ram_leak_detected else 0

        fps_deduction = 0.0
        if metrics.min_fps < _MIN_FPS_THRESHOLD:
            fps_deduction += _LOW_MIN_FPS_PENALTY
        if metrics.avg_fps < _AVG_FPS_THRESHOLD:
            fps_deduction += _LOW_AVG_FPS_PENALTY

        total_deduction = (
            bug_deduction
            + stability_deduction
            + performance_deduction
            + memory_deduction
            + fps_deduction
        )

        overall = max(0.0, min(100.0, 100.0 - total_deduction))
        risk_level = self._score_to_level(overall)

        category_scores: Dict[str, Any] = {
            "bugs": {
                "deduction": bug_deduction,
                "critical_bugs": metrics.critical_bugs,
                "major_bugs": metrics.major_bugs,
                "minor_bugs": metrics.minor_bugs,
            },
            "stability": {
                "deduction": stability_deduction,
                "crash_count": metrics.crash_count,
            },
            "performance": {
                "deduction": performance_deduction,
                "avg_cpu_percent": metrics.avg_cpu_percent,
                "max_cpu_percent": metrics.max_cpu_percent,
                "avg_ram_percent": metrics.avg_ram_percent,
            },
            "memory": {
                "deduction": memory_deduction,
                "ram_leak_detected": metrics.ram_leak_detected,
            },
            "fps": {
                "deduction": fps_deduction,
                "avg_fps": metrics.avg_fps,
                "min_fps": metrics.min_fps,
            },
        }

        assessment = RiskAssessment(
            overall_score=round(overall, 2),
            risk_level=risk_level,
            category_scores=category_scores,
        )

        assessment.recommendations = self.generate_recommendations(assessment)
        return assessment

    def get_risk_breakdown(self, assessment: RiskAssessment) -> Dict[str, Any]:
        """Return a detailed per-category breakdown of the risk assessment.

        Args:
            assessment: A previously computed :class:`RiskAssessment`.

        Returns:
            A dictionary containing the overall score, risk level, per-
            category details, and total deduction.
        """
        total_deduction = sum(
            cat.get("deduction", 0)
            for cat in assessment.category_scores.values()
            if isinstance(cat, dict)
        )

        return {
            "overall_score": assessment.overall_score,
            "risk_level": assessment.risk_level,
            "total_deduction": total_deduction,
            "categories": assessment.category_scores,
            "timestamp": assessment.timestamp.isoformat(),
            "recommendation_count": len(assessment.recommendations),
        }

    def generate_recommendations(self, assessment: RiskAssessment) -> List[str]:
        """Produce actionable recommendations based on the assessment.

        Args:
            assessment: A previously computed :class:`RiskAssessment`.

        Returns:
            Ordered list of human-readable recommendation strings, most
            urgent first.
        """
        recs: List[str] = []
        cats = assessment.category_scores

        # --- Bug recommendations ---
        bugs = cats.get("bugs", {})
        if bugs.get("critical_bugs", 0) > 0:
            recs.append(
                f"URGENT: Resolve {bugs['critical_bugs']} critical bug(s) before release. "
                "Critical bugs can cause data loss, crashes, or security vulnerabilities."
            )
        if bugs.get("major_bugs", 0) > 0:
            recs.append(
                f"Address {bugs['major_bugs']} major bug(s). "
                "Major bugs significantly impair core functionality."
            )
        if bugs.get("minor_bugs", 0) > 5:
            recs.append(
                f"Review {bugs['minor_bugs']} minor bug(s). "
                "A high minor bug count may indicate underlying code quality issues."
            )

        # --- Stability recommendations ---
        stability = cats.get("stability", {})
        if stability.get("crash_count", 0) > 0:
            recs.append(
                f"Investigate {stability['crash_count']} crash(es). "
                "Analyse crash dumps and stack traces to identify root causes."
            )

        # --- Performance recommendations ---
        perf = cats.get("performance", {})
        if perf.get("avg_cpu_percent", 0) > _CPU_THRESHOLD:
            recs.append(
                f"Average CPU usage is {perf['avg_cpu_percent']:.1f}% (threshold: {_CPU_THRESHOLD}%). "
                "Profile hot paths and consider optimising compute-heavy routines."
            )
        if perf.get("avg_ram_percent", 0) > _RAM_THRESHOLD:
            recs.append(
                f"Average RAM usage is {perf['avg_ram_percent']:.1f}% (threshold: {_RAM_THRESHOLD}%). "
                "Review memory allocations and reduce asset cache sizes."
            )

        # --- Memory recommendations ---
        memory = cats.get("memory", {})
        if memory.get("ram_leak_detected", False):
            recs.append(
                "URGENT: Memory leak detected. "
                "Run a memory profiler to locate and fix allocation leaks before release."
            )

        # --- FPS recommendations ---
        fps = cats.get("fps", {})
        if fps.get("min_fps", 999) < _MIN_FPS_THRESHOLD:
            recs.append(
                f"Minimum FPS dropped to {fps['min_fps']:.1f} (threshold: {_MIN_FPS_THRESHOLD}). "
                "Identify and optimise the scenes or conditions causing frame-rate drops."
            )
        if fps.get("avg_fps", 999) < _AVG_FPS_THRESHOLD:
            recs.append(
                f"Average FPS is {fps['avg_fps']:.1f} (target: {_AVG_FPS_THRESHOLD}). "
                "Consider reducing draw calls, LOD distances, or shader complexity."
            )

        # --- Overall risk-level guidance ---
        if assessment.risk_level == _RISK_LEVEL_CRITICAL:
            recs.insert(
                0,
                "RELEASE BLOCKED: Overall risk is CRITICAL. Do not ship until "
                "critical issues are resolved and the score exceeds 30.",
            )
        elif assessment.risk_level == _RISK_LEVEL_HIGH:
            recs.insert(
                0,
                "RELEASE AT RISK: Overall risk is HIGH. Strongly consider "
                "delaying the release until major issues are addressed.",
            )

        return recs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_level(score: float) -> str:
        """Map a numeric score to a risk-level label."""
        if score <= 30:
            return _RISK_LEVEL_CRITICAL
        if score <= 50:
            return _RISK_LEVEL_HIGH
        if score <= 75:
            return _RISK_LEVEL_MEDIUM
        return _RISK_LEVEL_LOW
