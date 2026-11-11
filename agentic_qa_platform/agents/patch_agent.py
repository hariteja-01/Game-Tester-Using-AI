"""
Patch Agent — Autonomous code-patch generation for game bugs.

Uses Google Gemini to generate realistic C++/C# code fixes formatted as
unified diffs. Falls back to template-based patch generation when the
API is unavailable.
"""

from __future__ import annotations

import json
import logging
import textwrap
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agentic_qa_platform.agents.stress_agent import AgentTrace, TraceStep
from agentic_qa_platform.agents.rca_agent import RCAResult


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GitPatch(BaseModel):
    """A generated code patch expressed as a unified diff."""

    patch_id: str = Field(default_factory=lambda: f"PATCH-{uuid.uuid4().hex[:8].upper()}")
    bug_id: str
    file_path: str
    original_code: str
    patched_code: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    diff_text: str = ""


# ---------------------------------------------------------------------------
# Template patches (fallback)
# ---------------------------------------------------------------------------

_TEMPLATE_PATCHES: Dict[str, Dict[str, str]] = {
    "Engine/Core Loop": {
        "file": "Source/Runtime/Engine/GameLoop.cpp",
        "original": textwrap.dedent("""\
            void UGameLoop::Tick(float DeltaTime)
            {
                for (auto& Actor : ActiveActors)
                {
                    Actor->Tick(DeltaTime);
                }
            }
        """),
        "patched": textwrap.dedent("""\
            void UGameLoop::Tick(float DeltaTime)
            {
                // Batch actors into worker threads to reduce main-thread load
                ParallelFor(ActiveActors.Num(), [&](int32 Index)
                {
                    ActiveActors[Index]->Tick(DeltaTime);
                });
            }
        """),
    },
    "Memory Manager": {
        "file": "Source/Runtime/Memory/AssetPool.cpp",
        "original": textwrap.dedent("""\
            void FAssetPool::LoadAsset(const FString& Path)
            {
                UObject* Asset = StaticLoadObject(UObject::StaticClass(), nullptr, *Path);
                LoadedAssets.Add(Asset);
            }
        """),
        "patched": textwrap.dedent("""\
            void FAssetPool::LoadAsset(const FString& Path)
            {
                // Evict oldest assets when pool exceeds budget
                if (LoadedAssets.Num() >= MaxPoolSize)
                {
                    EvictLRU();
                }
                TWeakObjectPtr<UObject> Asset = StaticLoadObject(UObject::StaticClass(), nullptr, *Path);
                if (Asset.IsValid())
                {
                    LoadedAssets.Add(Asset);
                }
            }
        """),
    },
    "Rendering Pipeline": {
        "file": "Source/Runtime/Renderer/ParticleRenderer.cpp",
        "original": textwrap.dedent("""\
            void FParticleRenderer::DrawParticles()
            {
                for (auto& Particle : Particles)
                {
                    RHICmdList.DrawIndexedPrimitive(Particle.Mesh, 0, 0,
                        Particle.NumVertices, 0, Particle.NumTriangles, 1);
                }
            }
        """),
        "patched": textwrap.dedent("""\
            void FParticleRenderer::DrawParticles()
            {
                // Instanced rendering: batch particles to reduce draw calls
                if (Particles.Num() > 0)
                {
                    BuildInstanceBuffer(Particles, InstanceBuffer);
                    RHICmdList.DrawIndexedPrimitive(SharedParticleMesh, 0, 0,
                        SharedNumVertices, 0, SharedNumTriangles, Particles.Num());
                }
            }
        """),
    },
    "Runtime / Exception Handler": {
        "file": "Source/Runtime/Core/ExceptionHandler.cs",
        "original": textwrap.dedent("""\
            public void ProcessInput(PlayerInput input)
            {
                var controller = GetController(input.PlayerId);
                controller.HandleInput(input);
            }
        """),
        "patched": textwrap.dedent("""\
            public void ProcessInput(PlayerInput input)
            {
                var controller = GetController(input.PlayerId);
                if (controller == null)
                {
                    Logger.Warn($"No controller for player {input.PlayerId}; ignoring input.");
                    return;
                }
                try
                {
                    controller.HandleInput(input);
                }
                catch (Exception ex)
                {
                    Logger.Error($"Input processing failed: {ex.Message}", ex);
                    RecoverController(input.PlayerId);
                }
            }
        """),
    },
    "Netcode / Replication": {
        "file": "Source/Runtime/Net/ReplicationManager.cpp",
        "original": textwrap.dedent("""\
            void UReplicationManager::SendUpdate(FNetConnection* Conn, const FReplicatedState& State)
            {
                FBitWriter Writer(1024);
                State.Serialize(Writer);
                Conn->SendRawBunch(Writer);
            }
        """),
        "patched": textwrap.dedent("""\
            void UReplicationManager::SendUpdate(FNetConnection* Conn, const FReplicatedState& State)
            {
                if (!Conn || Conn->GetState() != EConnectionState::Open)
                {
                    UE_LOG(LogNet, Warning, TEXT("Skipping replication: connection invalid."));
                    return;
                }
                FBitWriter Writer(1024);
                State.Serialize(Writer);

                // Retry with exponential back-off on transient failures
                constexpr int32 MaxRetries = 3;
                for (int32 Attempt = 0; Attempt < MaxRetries; ++Attempt)
                {
                    if (Conn->SendRawBunch(Writer))
                    {
                        return;
                    }
                    FPlatformProcess::Sleep(0.01f * (1 << Attempt));
                }
                UE_LOG(LogNet, Error, TEXT("Replication send failed after %d retries."), MaxRetries);
            }
        """),
    },
}


# ---------------------------------------------------------------------------
# PatchAgent
# ---------------------------------------------------------------------------

class PatchAgent:
    """Generates autonomous code patches for bugs identified by RCA.

    Parameters
    ----------
    api_key : str
        Google Gemini API key.  Pass ``""`` for template-based patches.
    """

    MODEL = "gemini-flash-latest"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None
        self._trace = AgentTrace(
            agent_name="PatchAgent",
            started_at=datetime.now(timezone.utc),
        )

        if self._api_key:
            try:
                from google import genai  # type: ignore[import-untyped]
                from google.genai import types  # type: ignore[import-untyped]

                self._client = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=5.0))
                logger.info("PatchAgent: Gemini client initialised.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("PatchAgent: Gemini client init failed (%s).", exc)
                self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_patches(self, rca_results: List[RCAResult]) -> List[GitPatch]:
        """Generate code-fix patches for each RCA result.

        Returns one ``GitPatch`` per bug, containing the original and
        patched code along with a unified-diff representation.
        """
        t0 = time.perf_counter()
        patches: List[GitPatch] = []

        for rca in rca_results:
            patch: Optional[GitPatch] = None
            if self._client is not None:
                try:
                    patch = self._generate_via_gemini(rca)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "PatchAgent: Gemini patch gen failed for %s (%s). Using template.",
                        rca.bug_id,
                        exc,
                    )
                    self._record_step(
                        "gemini_patch_fallback_trigger",
                        input_data=rca.bug_id,
                        output_data=f"Error: {exc}",
                        duration_ms=0.0,
                    )

            if patch is None:
                patch = self._generate_template_patch(rca)

            # Ensure diff text is populated
            if not patch.diff_text:
                patch.diff_text = self.format_as_unified_diff(patch)

            patches.append(patch)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "generate_patches",
            input_data=f"{len(rca_results)} RCA results",
            output_data=f"{len(patches)} patches generated",
            duration_ms=elapsed_ms,
        )
        self._trace.status = "completed"
        self._trace.completed_at = datetime.now(timezone.utc)
        return patches

    def format_as_unified_diff(self, patch: GitPatch) -> str:
        """Format a ``GitPatch`` as a git-compatible unified diff."""
        original_lines = patch.original_code.splitlines(keepends=True)
        patched_lines = patch.patched_code.splitlines(keepends=True)

        # Ensure lines end with newline for clean diffs
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] += "\n"
        if patched_lines and not patched_lines[-1].endswith("\n"):
            patched_lines[-1] += "\n"

        diff_parts: List[str] = [
            f"--- a/{patch.file_path}\n",
            f"+++ b/{patch.file_path}\n",
            f"@@ -1,{len(original_lines)} +1,{len(patched_lines)} @@\n",
        ]
        for line in original_lines:
            diff_parts.append(f"-{line}")
        for line in patched_lines:
            diff_parts.append(f"+{line}")

        return "".join(diff_parts)

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
    # Gemini patch generation
    # ------------------------------------------------------------------

    def _generate_via_gemini(self, rca: RCAResult) -> GitPatch:
        """Use Gemini to produce a realistic code patch."""
        t0 = time.perf_counter()

        prompt = (
            "You are a senior game engine developer. Generate a code fix for the "
            "following bug.\n\n"
            f"Bug ID: {rca.bug_id}\n"
            f"Title: {rca.title}\n"
            f"Root Cause: {rca.root_cause}\n"
            f"Affected Component: {rca.affected_component}\n"
            f"Suggested Fix: {rca.suggested_fix}\n\n"
            "Return ONLY valid JSON (no markdown fences, no commentary) with:\n"
            '  "file_path": string (realistic engine source path),\n'
            '  "original_code": string (the buggy code, C++ or C#, 5-15 lines),\n'
            '  "patched_code": string (the fixed code, same style),\n'
            '  "description": string (1-2 sentence explanation of the fix),\n'
            '  "confidence": float 0.0-1.0\n\n'
            "The code should look like real Unreal Engine C++ or Unity C# — use "
            "appropriate naming conventions, macros, and engine APIs."
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

        patch = GitPatch(
            bug_id=rca.bug_id,
            file_path=data.get("file_path", "Source/Unknown.cpp"),
            original_code=data.get("original_code", ""),
            patched_code=data.get("patched_code", ""),
            description=data.get("description", "AI-generated fix"),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_step(
            "gemini_patch",
            input_data=rca.bug_id,
            output_data=f"Generated patch for {patch.file_path}",
            duration_ms=elapsed_ms,
        )
        return patch

    # ------------------------------------------------------------------
    # Template-based fallback
    # ------------------------------------------------------------------

    def _generate_template_patch(self, rca: RCAResult) -> GitPatch:
        """Produce a patch from pre-defined templates based on component."""
        component = rca.affected_component
        template = _TEMPLATE_PATCHES.get(component)

        if template is None:
            # Pick a generic template
            template = _TEMPLATE_PATCHES.get("Runtime / Exception Handler", {
                "file": "Source/Runtime/Unknown/Module.cpp",
                "original": "// Original code placeholder\nvoid Func() { /* buggy */ }\n",
                "patched": "// Patched code\nvoid Func() { /* fixed */ }\n",
            })

        patch = GitPatch(
            bug_id=rca.bug_id,
            file_path=template["file"],
            original_code=template["original"],
            patched_code=template["patched"],
            description=f"Template fix for {component}: {rca.suggested_fix[:200]}",
            confidence=0.40,
        )

        self._record_step(
            "template_patch",
            input_data=rca.bug_id,
            output_data=f"Template patch for component '{component}'",
            duration_ms=0.0,
        )
        return patch

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
