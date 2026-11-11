"""
Stress Agent — AI-powered dynamic stress test scenario generation.

Uses Google Gemini to generate game-specific stress test scenarios
with quantitative workload parameters. Falls back to a comprehensive
set of pre-defined generic scenarios when the API is unavailable.
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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TraceStep(BaseModel):
    """A single recorded step within an agent's execution trace."""

    step_name: str
    input_data: str
    output_data: str
    duration_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    status: str = "completed"

    def model_post_init(self, __context: Any) -> None:
        if self.duration_seconds == 0.0 and self.duration_ms > 0:
            self.duration_seconds = round(self.duration_ms / 1000.0, 4)
        if self.start_time is None:
            self.start_time = self.timestamp
        if self.end_time is None and self.start_time:
            from datetime import timedelta
            self.end_time = self.start_time + timedelta(seconds=max(0.005, self.duration_seconds))


class AgentTrace(BaseModel):
    """Full execution trace for an agent run."""

    agent_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time_seconds: float = 0.0
    steps: List[TraceStep] = Field(default_factory=list)
    status: str = "pending"

    def model_post_init(self, __context: Any) -> None:
        if self.start_time is None:
            self.start_time = self.started_at
        if self.end_time is None and self.completed_at:
            self.end_time = self.completed_at
        if self.execution_time_seconds == 0.0 and self.start_time and self.end_time:
            self.execution_time_seconds = round((self.end_time - self.start_time).total_seconds(), 3)


class StressScenario(BaseModel):
    """A single stress-test scenario generated for a game."""

    id: str = Field(default_factory=lambda: f"stress-{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    category: str = Field(
        description="One of: performance, stability, memory, network, rendering, physics"
    )
    intensity: int = Field(ge=1, le=10)
    expected_metrics: Dict[str, Any] = Field(default_factory=dict)


class WorkloadParams(BaseModel):
    """Quantitative workload parameters derived from a scenario."""

    scenario_id: str
    cpu_target_percent: float = Field(ge=0.0, le=100.0)
    memory_target_mb: float = Field(ge=0.0)
    io_operations_per_sec: int = Field(ge=0)
    concurrent_threads: int = Field(ge=1)
    duration_seconds: float = Field(ge=0.1)


# ---------------------------------------------------------------------------
# Fallback scenarios
# ---------------------------------------------------------------------------

_FALLBACK_SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "CPU Spike – Heavy AI Pathfinding",
        "description": (
            "Simulate 200+ NPC agents running A* pathfinding simultaneously "
            "to stress CPU-bound game systems."
        ),
        "category": "performance",
        "intensity": 8,
        "expected_metrics": {
            "cpu_percent_target": 90,
            "thread_count": 16,
            "duration_s": 60,
        },
    },
    {
        "name": "Memory Pressure – Asset Streaming",
        "description": (
            "Rapidly load and unload high-resolution textures and mesh data "
            "to detect memory leaks and fragmentation."
        ),
        "category": "memory",
        "intensity": 7,
        "expected_metrics": {
            "ram_target_mb": 4096,
            "allocation_rate_mb_s": 200,
            "duration_s": 120,
        },
    },
    {
        "name": "Rendering Storm – Particle Overload",
        "description": (
            "Spawn 50,000 simultaneous particles with dynamic lighting "
            "to push GPU fill-rate and draw-call limits."
        ),
        "category": "rendering",
        "intensity": 9,
        "expected_metrics": {
            "draw_calls": 50000,
            "target_fps_drop_percent": 60,
            "duration_s": 45,
        },
    },
    {
        "name": "Network Jitter – Multiplayer Desync",
        "description": (
            "Inject variable latency (50–500 ms) and 5% packet loss "
            "into simulated multiplayer traffic to test netcode resilience."
        ),
        "category": "network",
        "intensity": 6,
        "expected_metrics": {
            "latency_range_ms": [50, 500],
            "packet_loss_percent": 5,
            "concurrent_connections": 64,
            "duration_s": 90,
        },
    },
    {
        "name": "Physics Avalanche – Ragdoll Chain Reaction",
        "description": (
            "Stack 500 physics-enabled rigid bodies and trigger a cascade "
            "to test solver stability and frame-time spikes."
        ),
        "category": "physics",
        "intensity": 8,
        "expected_metrics": {
            "rigid_body_count": 500,
            "solver_iterations": 16,
            "expected_spike_ms": 33,
            "duration_s": 30,
        },
    },
    {
        "name": "Stability Soak – Extended Idle Session",
        "description": (
            "Leave the game running at the main menu for 4 hours while "
            "monitoring handle count, memory, and CPU drift."
        ),
        "category": "stability",
        "intensity": 4,
        "expected_metrics": {
            "soak_duration_s": 14400,
            "handle_leak_threshold": 100,
            "memory_drift_mb": 50,
        },
    },
]


# ---------------------------------------------------------------------------
# StressAgent
# ---------------------------------------------------------------------------

class StressAgent:
    """Generates dynamic stress test scenarios using Gemini AI.

    Parameters
    ----------
    api_key : str
        Google Gemini API key.  An empty string disables AI generation
        and uses built-in fallback scenarios instead.
    """

    MODEL = "gemini-flash-latest"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None
        self._trace = AgentTrace(
            agent_name="StressAgent",
            started_at=datetime.now(timezone.utc),
        )

        if self._api_key:
            try:
                from google import genai  # type: ignore[import-untyped]
                from google.genai import types  # type: ignore[import-untyped]

                self._client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=5.0))
                logger.info("StressAgent: Gemini client initialised.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("StressAgent: Gemini client init failed (%s). Using fallback.", exc)
                self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_test_scenarios(self, game_name: str) -> List[StressScenario]:
        """Generate 5-8 stress-test scenarios tailored to *game_name*.

        Uses Gemini AI when available; otherwise returns hardcoded
        fallback scenarios that cover all major stress categories.
        """
        t0 = time.perf_counter()
        scenarios: List[StressScenario] = []

        if self._client is not None:
            try:
                scenarios = self._generate_via_gemini(game_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "StressAgent: Gemini generation failed (%s). Falling back.", exc
                )
                self._record_step(
                    "gemini_generate_fallback_trigger",
                    input_data=game_name,
                    output_data=f"Error: {exc}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

        if not scenarios:
            scenarios = self._fallback_scenarios(game_name)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "generate_test_scenarios",
            input_data=game_name,
            output_data=f"{len(scenarios)} scenarios generated",
            duration_ms=elapsed_ms,
        )
        self._trace.status = "completed"
        self._trace.completed_at = datetime.now(timezone.utc)
        return scenarios

    def create_workload_params(self, scenario: StressScenario) -> WorkloadParams:
        """Derive quantitative workload parameters from a scenario."""
        t0 = time.perf_counter()

        intensity = scenario.intensity
        metrics = scenario.expected_metrics

        cpu_target = min(float(metrics.get("cpu_percent_target", intensity * 10)), 100.0)
        memory_target = float(metrics.get("ram_target_mb", intensity * 256))
        io_ops = int(metrics.get("io_operations_per_sec", intensity * 50))
        threads = int(metrics.get("thread_count", max(1, intensity * 2)))
        duration = float(metrics.get("duration_s", max(10, intensity * 10)))

        params = WorkloadParams(
            scenario_id=scenario.id,
            cpu_target_percent=cpu_target,
            memory_target_mb=memory_target,
            io_operations_per_sec=io_ops,
            concurrent_threads=threads,
            duration_seconds=duration,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "create_workload_params",
            input_data=scenario.name,
            output_data=params.model_dump_json(),
            duration_ms=elapsed_ms,
        )
        return params

    def get_trace(self) -> AgentTrace:
        """Return the execution trace for this agent run."""
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
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_via_gemini(self, game_name: str) -> List[StressScenario]:
        """Call Gemini to produce game-specific stress scenarios."""
        t0 = time.perf_counter()

        prompt = (
            f"You are an expert QA engineer for video games. Generate between 5 and 8 "
            f"stress test scenarios specifically tailored for the game '{game_name}'.\n\n"
            f"Return ONLY a JSON array where each element has these fields:\n"
            f'  "name": string,\n'
            f'  "description": string (2-3 sentences),\n'
            f'  "category": one of "performance", "stability", "memory", "network", '
            f'"rendering", "physics",\n'
            f'  "intensity": integer 1-10,\n'
            f'  "expected_metrics": object with relevant numeric targets\n\n'
            f"Make each scenario realistic and specific to the genre and mechanics of "
            f"'{game_name}'. Cover at least 4 different categories.\n"
            f"Return ONLY valid JSON — no markdown fences, no commentary."
        )

        response = self._client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )
        raw_text: str = response.text.strip()

        # Strip optional markdown code-fence wrappers
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        data = json.loads(raw_text)
        if not isinstance(data, list):
            raise ValueError("Gemini response is not a JSON array.")

        scenarios: List[StressScenario] = []
        for item in data:
            scenarios.append(
                StressScenario(
                    name=item.get("name", "Unnamed"),
                    description=item.get("description", ""),
                    category=item.get("category", "performance"),
                    intensity=max(1, min(10, int(item.get("intensity", 5)))),
                    expected_metrics=item.get("expected_metrics", {}),
                )
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "gemini_generate",
            input_data=game_name,
            output_data=f"Parsed {len(scenarios)} scenarios from Gemini",
            duration_ms=elapsed_ms,
        )
        return scenarios

    def _fallback_scenarios(self, game_name: str) -> List[StressScenario]:
        """Return pre-defined generic scenarios, tagged with the game name."""
        scenarios: List[StressScenario] = []
        for raw in _FALLBACK_SCENARIOS:
            scenarios.append(
                StressScenario(
                    name=raw["name"],
                    description=f"[{game_name}] {raw['description']}",
                    category=raw["category"],
                    intensity=raw["intensity"],
                    expected_metrics=raw["expected_metrics"],
                )
            )
        self._record_step(
            "fallback_scenarios",
            input_data=game_name,
            output_data=f"Loaded {len(scenarios)} fallback scenarios",
            duration_ms=0.0,
        )
        return scenarios

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
