"""Multi-Agent Orchestration Engine for the Agentic QA Platform.

Exports:
  - Orchestrator: Central state graph and coordinator
  - StressAgent: Dynamic load and edge-case generator
  - TelemetryAgent: Process and system metric collector
  - RCAAgent: Deep stack-trace and log root-cause analysis
  - PatchAgent: Autonomous git-diff patch generator
"""

from agentic_qa_platform.agents.orchestrator import (
    AnalysisResult,
    Orchestrator,
)
from agentic_qa_platform.agents.stress_agent import (
    AgentTrace,
    StressAgent,
    StressScenario,
    TraceStep,
    WorkloadParams,
)
from agentic_qa_platform.agents.telemetry_agent import (
    TelemetryAgent,
    TelemetryAnalysis,
    TelemetryAnomaly,
    TelemetryReport,
    TelemetrySnapshot,
    TelemetrySummary,
)
from agentic_qa_platform.agents.rca_agent import (
    BugReport,
    RCAAgent,
    RCAResult,
)
from agentic_qa_platform.agents.patch_agent import (
    GitPatch,
    PatchAgent,
)

from agentic_qa_platform.agents.quota_manager import (
    QuotaManager,
    DEFAULT_BUDGET_CALLS,
    QUOTA_THRESHOLD_PERCENT,
)

__all__ = [
    "Orchestrator",
    "AnalysisResult",
    "QuotaManager",
    "DEFAULT_BUDGET_CALLS",
    "QUOTA_THRESHOLD_PERCENT",
    "StressAgent",
    "StressScenario",
    "WorkloadParams",
    "AgentTrace",
    "TraceStep",
    "TelemetryAgent",
    "TelemetrySnapshot",
    "TelemetryAnomaly",
    "TelemetrySummary",
    "TelemetryReport",
    "TelemetryAnalysis",
    "RCAAgent",
    "BugReport",
    "RCAResult",
    "PatchAgent",
    "GitPatch",
]
