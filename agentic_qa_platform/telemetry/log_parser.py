"""Structured parser for crash logs, stack traces, and game-engine log entries.

Provides extraction of exception types, file / line info, severity
classification, sample game-log generation (Unreal / Unity style), and
recurring-pattern detection.
"""

from __future__ import annotations

import hashlib
import random
import re
import string
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class StackFrame(BaseModel):
    """A single frame in a parsed stack trace."""

    file_path: str = Field("", description="Source file path.")
    line_number: int = Field(0, description="Line number in the source file.")
    function_name: str = Field("", description="Function or method name.")
    code_snippet: Optional[str] = Field(
        None,
        description="Inline code snippet, if available.",
    )


class CrashReport(BaseModel):
    """Structured representation of a parsed crash log."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the crash occurred.",
    )
    exception_type: str = Field("", description="Exception class name.")
    message: str = Field("", description="Error message text.")
    stack_frames: List[StackFrame] = Field(
        default_factory=list,
        description="Ordered stack frames (innermost last).",
    )
    severity: str = Field("ERROR", description="Severity classification.")
    affected_module: str = Field(
        "",
        description="Top-level module or subsystem that crashed.",
    )


class LogLevel(str, Enum):
    """Standard log severity levels."""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogEntry(BaseModel):
    """A single structured log line."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Log entry timestamp.",
    )
    level: LogLevel = Field(LogLevel.INFO, description="Log severity level.")
    source: str = Field("", description="Subsystem or module that emitted the log.")
    message: str = Field("", description="Log message body.")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata.",
    )


class LogPattern(BaseModel):
    """A recurring pattern detected across log entries."""

    pattern_description: str = Field(
        "",
        description="Human-readable summary of the pattern.",
    )
    occurrences: int = Field(0, description="Number of times the pattern appeared.")
    severity: str = Field("INFO", description="Highest severity in the cluster.")
    first_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Earliest occurrence.",
    )
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Latest occurrence.",
    )
    affected_files: List[str] = Field(
        default_factory=list,
        description="Source files referenced by entries in this pattern.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Regex for Python-style traceback frame lines.
_PY_FRAME_RE = re.compile(
    r'^\s*File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)'
    r"(?:,\s+in\s+(?P<func>\S+))?",
)

# Regex for C++ / Unreal-style frame lines like:
#   UnrealEngine!FRenderModule::Tick() [RenderModule.cpp:412]
_CPP_FRAME_RE = re.compile(
    r"^(?P<module>\S+?)!"
    r"(?P<func>[^\[]+?)\s*"
    r"\[(?P<file>[^\]:]+):(?P<line>\d+)\]",
)

# Common Python exception line:  ``SomeError: message``
_EXCEPTION_RE = re.compile(r"^(?P<exc>[A-Za-z_][\w.]*):\s*(?P<msg>.+)$")


def _severity_rank(level: str) -> int:
    """Return an integer rank for severity comparison."""
    return {"INFO": 0, "WARN": 1, "ERROR": 2, "FATAL": 3}.get(level.upper(), -1)


def _extract_module_from_path(path: str) -> str:
    """Best-effort module name from a file path."""
    # Strip directory and extension, take the stem.
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return stem


# ---------------------------------------------------------------------------
# LogParser
# ---------------------------------------------------------------------------

class LogParser:
    """Parses crash logs, stack traces, and generates sample game-engine logs.

    Example::

        parser = LogParser()
        report = parser.parse_crash_log(raw_log_text)
        print(report.exception_type, report.severity)
    """

    # ---- crash-log parsing ----------------------------------------------- #

    @staticmethod
    def parse_crash_log(log_text: str) -> CrashReport:
        """Parse a raw crash log into a structured ``CrashReport``.

        Supports Python tracebacks and C++ / Unreal-style crash dumps.
        Severity is inferred from keywords in the log text.

        Args:
            log_text: Raw multi-line crash log string.

        Returns:
            A populated ``CrashReport``.
        """
        lines = log_text.strip().splitlines()

        exception_type = ""
        message = ""
        frames: List[StackFrame] = []
        affected_module = ""

        # -- Attempt to find a timestamp in the first few lines ------------ #
        ts = datetime.now(timezone.utc)
        ts_patterns = [
            # ISO-8601 variants.
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
            # Common log format.
            r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}",
        ]
        for line in lines[:5]:
            for pat in ts_patterns:
                m = re.search(pat, line)
                if m:
                    try:
                        ts = datetime.fromisoformat(
                            m.group(0).replace(" ", "T")
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                    break

        # -- Parse frames -------------------------------------------------- #
        code_snippet_next = False
        for idx, line in enumerate(lines):
            # Python frame.
            pm = _PY_FRAME_RE.match(line)
            if pm:
                snippet: Optional[str] = None
                # The line immediately after a Python frame is the code.
                if idx + 1 < len(lines):
                    candidate = lines[idx + 1].strip()
                    if candidate and not _PY_FRAME_RE.match(lines[idx + 1]):
                        snippet = candidate
                frames.append(
                    StackFrame(
                        file_path=pm.group("file"),
                        line_number=int(pm.group("line")),
                        function_name=pm.group("func") or "",
                        code_snippet=snippet,
                    )
                )
                continue

            # C++ / Unreal frame.
            cm = _CPP_FRAME_RE.match(line.strip())
            if cm:
                frames.append(
                    StackFrame(
                        file_path=cm.group("file"),
                        line_number=int(cm.group("line")),
                        function_name=cm.group("func").strip(),
                        code_snippet=None,
                    )
                )
                continue

            # Exception line (usually last meaningful line in Python tb).
            em = _EXCEPTION_RE.match(line.strip())
            if em:
                exception_type = em.group("exc")
                message = em.group("msg")

        # Fallback: if no exception regex matched, use the last non-empty line.
        if not exception_type:
            for line in reversed(lines):
                stripped = line.strip()
                if stripped:
                    exception_type = "UnknownError"
                    message = stripped
                    break

        # Determine affected module from the deepest frame.
        if frames:
            affected_module = _extract_module_from_path(frames[-1].file_path)

        # Severity heuristics.
        lower_text = log_text.lower()
        if any(kw in lower_text for kw in ("fatal", "abort", "segfault", "sigsegv", "access violation")):
            severity = "FATAL"
        elif any(kw in lower_text for kw in ("error", "exception", "crash", "unhandled")):
            severity = "ERROR"
        elif any(kw in lower_text for kw in ("warning", "warn", "deprecated")):
            severity = "WARN"
        else:
            severity = "INFO"

        return CrashReport(
            timestamp=ts,
            exception_type=exception_type,
            message=message,
            stack_frames=frames,
            severity=severity,
            affected_module=affected_module,
        )

    # ---- stack-trace parsing --------------------------------------------- #

    @staticmethod
    def parse_stack_trace(trace_text: str) -> List[StackFrame]:
        """Parse a raw stack trace string into a list of ``StackFrame``.

        Handles Python tracebacks and C++ / Unreal-style crash frames.

        Args:
            trace_text: Multi-line stack trace.

        Returns:
            Ordered list of ``StackFrame`` instances (outermost first).
        """
        frames: List[StackFrame] = []
        lines = trace_text.strip().splitlines()

        for idx, line in enumerate(lines):
            pm = _PY_FRAME_RE.match(line)
            if pm:
                snippet: Optional[str] = None
                if idx + 1 < len(lines):
                    candidate = lines[idx + 1].strip()
                    if candidate and not _PY_FRAME_RE.match(lines[idx + 1]):
                        snippet = candidate
                frames.append(
                    StackFrame(
                        file_path=pm.group("file"),
                        line_number=int(pm.group("line")),
                        function_name=pm.group("func") or "",
                        code_snippet=snippet,
                    )
                )
                continue

            cm = _CPP_FRAME_RE.match(line.strip())
            if cm:
                frames.append(
                    StackFrame(
                        file_path=cm.group("file"),
                        line_number=int(cm.group("line")),
                        function_name=cm.group("func").strip(),
                        code_snippet=None,
                    )
                )

        return frames

    # ---- sample game log generation -------------------------------------- #

    @staticmethod
    def generate_sample_game_logs(
        game_name: str,
        num_entries: int = 20,
    ) -> List[LogEntry]:
        """Generate realistic sample game-engine log entries.

        Produces a mix of rendering errors, physics glitches, network
        timeouts, shader compilation failures, memory-allocation failures,
        and normal operational messages using Unreal / Unity style
        terminology.

        Args:
            game_name: Name of the game (used in log context).
            num_entries: Number of log entries to generate.

        Returns:
            Time-ordered list of ``LogEntry`` instances.
        """
        if num_entries <= 0:
            return []

        entries: List[LogEntry] = []
        base_time = datetime.now(timezone.utc) - timedelta(minutes=num_entries)

        # -- Template pools ------------------------------------------------ #
        _subsystems = [
            "RenderThread",
            "PhysXSimulation",
            "NetworkManager",
            "ShaderCompiler",
            "MemoryAllocator",
            "AudioEngine",
            "AssetLoader",
            "AnimationGraph",
            "GarbageCollector",
            "InputManager",
            "ParticleSystem",
            "NavMeshBuilder",
            "LightingSystem",
            "StreamingManager",
            "SaveGameManager",
        ]

        _shader_names = [
            "M_Character_Hair_Translucent",
            "M_Environment_Foliage_Wind",
            "PP_GlobalFog_Volumetric",
            "M_VFX_Explosion_Distortion",
            "M_Water_Ocean_Tessellated",
            "M_Weapon_PBR_Emissive",
            "M_Decal_BloodSplatter_Deferred",
            "M_UI_HUD_Holographic",
            "CS_ParticleGPU_Collision",
            "M_Terrain_Landscape_4Layer",
        ]

        _render_files = [
            "Engine/Source/Runtime/Renderer/Private/DeferredShadingRenderer.cpp",
            "Engine/Source/Runtime/Renderer/Private/SceneRendering.cpp",
            "Engine/Source/Runtime/RHI/Private/D3D12RHI/D3D12CommandList.cpp",
            "Engine/Source/Runtime/RHI/Private/VulkanRHI/VulkanPipeline.cpp",
            "Engine/Shaders/Private/PostProcessing/TemporalAA.usf",
        ]

        _physics_files = [
            "Engine/Source/Runtime/PhysicsCore/Private/PhysXScene.cpp",
            "Engine/Source/Runtime/PhysicsCore/Private/BodyInstance.cpp",
            "Plugins/Chaos/Source/ChaosCore/Private/Simulation/ChaosSolver.cpp",
            "Source/Runtime/Physics/Private/CollisionDispatch.cpp",
        ]

        _network_files = [
            "Engine/Source/Runtime/Online/HTTP/Private/HttpThread.cpp",
            "Engine/Source/Runtime/Sockets/Private/BSDSockets/SocketSubsystemBSD.cpp",
            "Engine/Source/Runtime/Net/Private/NetDriver.cpp",
            "Source/Runtime/Online/Private/SessionManager.cpp",
        ]

        _memory_files = [
            "Engine/Source/Runtime/Core/Private/HAL/MallocBinned2.cpp",
            "Engine/Source/Runtime/Core/Private/HAL/MemoryAllocatorPool.cpp",
            "Engine/Source/Runtime/Core/Private/GenericPlatform/GenericPlatformMemory.cpp",
        ]

        _asset_files = [
            f"Content/{game_name}/Maps/MainWorld_P.umap",
            f"Content/{game_name}/Characters/Hero/SK_Hero_Mesh.uasset",
            f"Content/{game_name}/VFX/Particles/PS_MuzzleFlash.uasset",
            f"Content/{game_name}/Audio/Cues/SFX_Footstep_Concrete.uasset",
        ]

        # Weighted template pool: (level, source, message_template, metadata_fn, file_pool)
        _templates: List[tuple] = [
            # -- INFO (operational) ---------------------------------------- #
            (
                LogLevel.INFO,
                "AssetLoader",
                f"Successfully loaded streaming level: /Game/{game_name}/Maps/{{map_name}}",
                lambda: {"map_name": random.choice(["MainWorld_P", "Dungeon_01", "Arena_PvP", "Tutorial_Island"]),
                         "load_time_ms": round(random.uniform(120, 2800), 1)},
                _asset_files,
            ),
            (
                LogLevel.INFO,
                "ShaderCompiler",
                "Compiled shader permutation {shader} ({variant} variant) in {time_ms:.0f} ms",
                lambda: {"shader": random.choice(_shader_names),
                         "variant": random.choice(["SM5", "SM6", "Vulkan", "Metal"]),
                         "time_ms": random.uniform(45, 900)},
                _render_files,
            ),
            (
                LogLevel.INFO,
                "GarbageCollector",
                "GC completed: {freed} objects freed, {remaining} reachable ({duration_ms:.1f} ms)",
                lambda: {"freed": random.randint(200, 12000),
                         "remaining": random.randint(50000, 300000),
                         "duration_ms": random.uniform(2.0, 35.0)},
                _memory_files,
            ),

            # -- WARN ------------------------------------------------------ #
            (
                LogLevel.WARN,
                "RenderThread",
                "Frame time spike detected: {frame_ms:.1f} ms (target {target_ms:.1f} ms). "
                "Possible GPU stall in deferred lighting pass.",
                lambda: {"frame_ms": random.uniform(33.0, 120.0),
                         "target_ms": 16.67,
                         "gpu_vendor": random.choice(["NVIDIA", "AMD", "Intel"])},
                _render_files,
            ),
            (
                LogLevel.WARN,
                "PhysXSimulation",
                "Physics substep exceeded budget: {substep_ms:.2f} ms "
                "(budget {budget_ms:.1f} ms). {bodies} active rigid bodies.",
                lambda: {"substep_ms": random.uniform(12.0, 45.0),
                         "budget_ms": 8.0,
                         "bodies": random.randint(150, 2000)},
                _physics_files,
            ),
            (
                LogLevel.WARN,
                "NetworkManager",
                "Packet loss detected on channel {channel}: {loss_pct:.1f}% "
                "(RTT {rtt_ms} ms, jitter {jitter_ms} ms)",
                lambda: {"channel": random.choice(["Reliable", "Unreliable", "Voice"]),
                         "loss_pct": random.uniform(1.0, 15.0),
                         "rtt_ms": random.randint(80, 350),
                         "jitter_ms": random.randint(5, 60)},
                _network_files,
            ),
            (
                LogLevel.WARN,
                "AnimationGraph",
                "Animation blend tree node '{node}' produced NaN output on bone "
                "'{bone}'. Clamping to identity.",
                lambda: {"node": random.choice(["Locomotion_BlendSpace", "AimOffset_Upper",
                                                  "IK_FootPlacement", "RagdollBlend"]),
                         "bone": random.choice(["spine_03", "hand_r", "foot_l", "head",
                                                 "clavicle_l", "thigh_r"])},
                [f"Content/{game_name}/Characters/Hero/ABP_Hero.uasset"],
            ),

            # -- ERROR ----------------------------------------------------- #
            (
                LogLevel.ERROR,
                "ShaderCompiler",
                "Failed to compile shader '{shader}': "
                "error X3004: undeclared identifier '{ident}' at line {line}",
                lambda: {"shader": random.choice(_shader_names),
                         "ident": random.choice(["WorldPosition", "NormalWS",
                                                   "BaseColor", "SceneDepth", "CustomUV0"]),
                         "line": random.randint(30, 500)},
                _render_files,
            ),
            (
                LogLevel.ERROR,
                "RenderThread",
                "D3D12 ERROR: ID3D12Device::CreateGraphicsPipelineState failed "
                "(hr=0x{hr:08X}). PSO cache miss for material '{mat}'.",
                lambda: {"hr": random.randint(0x80004001, 0x80070057),
                         "mat": random.choice(_shader_names)},
                _render_files,
            ),
            (
                LogLevel.ERROR,
                "PhysXSimulation",
                "Penetration depth exceeded maximum ({depth:.3f} m) for pair "
                "({actor_a}, {actor_b}). Teleporting to depenetrated position.",
                lambda: {"depth": random.uniform(0.5, 5.0),
                         "actor_a": f"BP_{game_name}_Character_C_{random.randint(0, 999)}",
                         "actor_b": f"SM_Wall_Segment_{random.randint(0, 200)}",
                         },
                _physics_files,
            ),
            (
                LogLevel.ERROR,
                "NetworkManager",
                "RPC '{rpc}' timed out after {timeout_ms} ms. "
                "Server endpoint {ip}:{port} unreachable.",
                lambda: {"rpc": random.choice(["ServerMove", "ClientAck",
                                                 "SpawnActor_Replicated",
                                                 "InventorySync", "DamageEvent"]),
                         "timeout_ms": random.randint(5000, 30000),
                         "ip": f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
                         "port": random.choice([7777, 7778, 27015, 443])},
                _network_files,
            ),
            (
                LogLevel.ERROR,
                "MemoryAllocator",
                "Allocation of {size_mb:.1f} MiB failed in pool '{pool}'. "
                "Total allocated: {total_gb:.2f} GiB / {limit_gb:.1f} GiB.",
                lambda: {"size_mb": random.uniform(32, 512),
                         "pool": random.choice(["TexturePool", "MeshPool",
                                                  "AudioPool", "ScriptPool"]),
                         "total_gb": random.uniform(6.0, 15.5),
                         "limit_gb": 16.0},
                _memory_files,
            ),
            (
                LogLevel.ERROR,
                "AudioEngine",
                "FMOD Error ({code}): Failed to create sound instance for "
                "'{event}'. Max voices exceeded ({voices}/{max_voices}).",
                lambda: {"code": random.choice(["FMOD_ERR_CHANNEL_ALLOC",
                                                  "FMOD_ERR_DSP_NOTFOUND",
                                                  "FMOD_ERR_FILE_NOTFOUND"]),
                         "event": random.choice(["Explosion_Large", "Footstep_Run",
                                                   "UI_Click", "Ambient_Wind_Loop"]),
                         "voices": random.randint(64, 128),
                         "max_voices": 64},
                _asset_files,
            ),

            # -- FATAL ----------------------------------------------------- #
            (
                LogLevel.FATAL,
                "RenderThread",
                "GPU device lost (DXGI_ERROR_DEVICE_REMOVED, reason 0x{reason:08X}). "
                "Unable to recover. Initiating crash report.",
                lambda: {"reason": random.choice([0x887A0006, 0x887A0005, 0x887A0001]),
                         "gpu": random.choice(["NVIDIA RTX 4090", "AMD RX 7900 XTX",
                                                 "Intel Arc A770"])},
                _render_files,
            ),
            (
                LogLevel.FATAL,
                "MemoryAllocator",
                "Out of memory: failed to allocate {size_mb} MiB for "
                "'{resource}'. Heap fragmentation at {frag_pct:.1f}%.",
                lambda: {"size_mb": random.randint(256, 2048),
                         "resource": random.choice([
                             "WorldPartition_StreamingGrid",
                             "Nanite_ClusterPagePool",
                             "VirtualTexture_PhysicalPool",
                             "Niagara_GPUParticleBuffer",
                         ]),
                         "frag_pct": random.uniform(60.0, 95.0)},
                _memory_files,
            ),
            (
                LogLevel.FATAL,
                "PhysXSimulation",
                "SIGSEGV: Access violation reading address 0x{addr:016X} in "
                "PhysX broadphase. Chaos solver state corrupted.",
                lambda: {"addr": random.randint(0, 0xFFFFFFFFFFFFFFFF)},
                _physics_files,
            ),
        ]

        # Weighted distribution: mostly INFO/WARN, fewer ERROR/FATAL.
        level_weights = {
            LogLevel.INFO: 0.35,
            LogLevel.WARN: 0.30,
            LogLevel.ERROR: 0.25,
            LogLevel.FATAL: 0.10,
        }

        # Group templates by level for weighted selection.
        by_level: Dict[LogLevel, List[tuple]] = defaultdict(list)
        for tpl in _templates:
            by_level[tpl[0]].append(tpl)

        for i in range(num_entries):
            # Pick level first (weighted), then a random template of that level.
            level = random.choices(
                list(level_weights.keys()),
                weights=list(level_weights.values()),
                k=1,
            )[0]

            templates_for_level = by_level.get(level)
            if not templates_for_level:
                # Fallback to any template.
                tpl_row = random.choice(_templates)
            else:
                tpl_row = random.choice(templates_for_level)

            tpl_level, tpl_source, tpl_msg, meta_fn, file_pool = tpl_row
            meta = meta_fn()

            # Render the message template with metadata values.
            try:
                rendered_msg = tpl_msg.format(**meta)
            except (KeyError, IndexError):
                rendered_msg = tpl_msg

            # Add source file to metadata.
            source_file = random.choice(file_pool) if file_pool else ""
            meta["source_file"] = source_file
            meta["game"] = game_name

            entry = LogEntry(
                timestamp=base_time + timedelta(seconds=i * random.uniform(0.5, 8.0)),
                level=tpl_level,
                source=tpl_source,
                message=rendered_msg,
                metadata=meta,
            )
            entries.append(entry)

        # Sort by timestamp for realism.
        entries.sort(key=lambda e: e.timestamp)
        return entries

    # ---- pattern detection ----------------------------------------------- #

    @staticmethod
    def detect_patterns(entries: List[LogEntry]) -> List[LogPattern]:
        """Find recurring error patterns across log entries.

        Groups entries by a normalised signature (source + message skeleton)
        and returns clusters with ≥ 2 occurrences, ordered by frequency.

        Args:
            entries: List of log entries to analyse.

        Returns:
            List of ``LogPattern`` instances, most frequent first.
        """
        if not entries:
            return []

        def _normalise(msg: str) -> str:
            """Strip numbers / hashes to create a message skeleton."""
            skeleton = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", msg)
            skeleton = re.sub(r"\b\d+(\.\d+)?\b", "<NUM>", skeleton)
            skeleton = re.sub(r"'[^']*'", "'<STR>'", skeleton)
            return skeleton

        # Bucket entries by (source, skeleton).
        buckets: Dict[str, List[LogEntry]] = defaultdict(list)
        for entry in entries:
            key = f"{entry.source}::{_normalise(entry.message)}"
            buckets[key].append(entry)

        patterns: List[LogPattern] = []
        for key, group in buckets.items():
            if len(group) < 2:
                continue

            # Determine highest severity.
            max_sev = max(group, key=lambda e: _severity_rank(e.level.value))

            # Collect affected files.
            affected: List[str] = []
            seen_files: set = set()
            for e in group:
                sf = e.metadata.get("source_file", "")
                if sf and sf not in seen_files:
                    affected.append(sf)
                    seen_files.add(sf)

            source_part = key.split("::", 1)[0]
            skeleton_part = key.split("::", 1)[1] if "::" in key else key

            # Truncate the skeleton for readability.
            desc = (
                f"[{source_part}] Recurring pattern ({len(group)}x): "
                f"{skeleton_part[:120]}{'…' if len(skeleton_part) > 120 else ''}"
            )

            patterns.append(
                LogPattern(
                    pattern_description=desc,
                    occurrences=len(group),
                    severity=max_sev.level.value,
                    first_seen=min(e.timestamp for e in group),
                    last_seen=max(e.timestamp for e in group),
                    affected_files=affected,
                )
            )

        # Sort by occurrence count descending.
        patterns.sort(key=lambda p: p.occurrences, reverse=True)
        return patterns
