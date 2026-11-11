"""Live process and system resource monitor using psutil.

Captures real system metrics (CPU, RAM, disk I/O, network) and provides
anomaly detection and synthetic load-curve generation for game-testing
scenarios.
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

import psutil
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class SystemSnapshot(BaseModel):
    """Point-in-time capture of whole-system resource utilisation."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the snapshot was taken.",
    )
    cpu_percent_per_core: List[float] = Field(
        default_factory=list,
        description="CPU usage percentage for each logical core.",
    )
    cpu_percent_avg: float = Field(
        0.0,
        description="Average CPU usage across all cores.",
    )
    ram_used_mb: float = Field(
        0.0,
        description="RAM currently in use (MiB).",
    )
    ram_total_mb: float = Field(
        0.0,
        description="Total physical RAM (MiB).",
    )
    ram_percent: float = Field(
        0.0,
        description="RAM usage as a percentage of total.",
    )
    disk_read_mb: float = Field(
        0.0,
        description="Cumulative disk read since boot (MiB).",
    )
    disk_write_mb: float = Field(
        0.0,
        description="Cumulative disk write since boot (MiB).",
    )
    net_sent_mb: float = Field(
        0.0,
        description="Cumulative bytes sent over the network (MiB).",
    )
    net_recv_mb: float = Field(
        0.0,
        description="Cumulative bytes received over the network (MiB).",
    )
    active_processes: int = Field(
        0,
        description="Number of active OS processes.",
    )
    active_threads: int = Field(
        0,
        description="Total thread count across all processes.",
    )
    fps_simulated: float = Field(
        0.0,
        description="Simulated frames-per-second (used in synthetic curves).",
    )


class ProcessMetrics(BaseModel):
    """Resource metrics for a single OS process."""

    pid: int = Field(..., description="Process ID.")
    name: str = Field("", description="Process name.")
    cpu_percent: float = Field(0.0, description="CPU usage percentage.")
    memory_percent: float = Field(0.0, description="Memory usage percentage.")
    num_threads: int = Field(0, description="Number of threads.")
    status: str = Field("unknown", description="Process status string.")


class Severity(str, Enum):
    """Severity levels for resource anomalies."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class ResourceAnomaly(BaseModel):
    """An anomalous resource observation detected from snapshots."""

    timestamp: datetime = Field(
        ...,
        description="When the anomaly was observed.",
    )
    metric_name: str = Field(
        ...,
        description="Name of the metric that triggered the anomaly.",
    )
    value: float = Field(
        ...,
        description="Observed value of the metric.",
    )
    threshold: float = Field(
        ...,
        description="Threshold that was exceeded.",
    )
    severity: Severity = Field(
        ...,
        description="Severity classification.",
    )
    description: str = Field(
        "",
        description="Human-readable explanation.",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BYTES_PER_MIB: float = 1024.0 * 1024.0


# ---------------------------------------------------------------------------
# ProcessMonitor
# ---------------------------------------------------------------------------

class ProcessMonitor:
    """Captures real and synthetic system / process metrics.

    Example::

        monitor = ProcessMonitor()
        snap = monitor.get_system_snapshot()
        print(snap.cpu_percent_avg, snap.ram_percent)
    """

    # ---- live metrics ---------------------------------------------------- #

    @staticmethod
    def get_system_snapshot() -> SystemSnapshot:
        """Capture a single point-in-time snapshot of system resources.

        Returns:
            A ``SystemSnapshot`` populated with live psutil readings.
        """
        cpu_per_core: List[float] = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_avg: float = sum(cpu_per_core) / max(len(cpu_per_core), 1)

        mem = psutil.virtual_memory()
        disk = psutil.disk_io_counters()
        net = psutil.net_io_counters()

        total_threads = 0
        process_count = 0
        for proc in psutil.process_iter(attrs=["num_threads"]):
            try:
                total_threads += proc.info.get("num_threads", 0) or 0  # type: ignore[union-attr]
                process_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent_per_core=cpu_per_core,
            cpu_percent_avg=round(cpu_avg, 2),
            ram_used_mb=round(mem.used / _BYTES_PER_MIB, 2),
            ram_total_mb=round(mem.total / _BYTES_PER_MIB, 2),
            ram_percent=round(mem.percent, 2),
            disk_read_mb=round((disk.read_bytes if disk else 0) / _BYTES_PER_MIB, 2),
            disk_write_mb=round((disk.write_bytes if disk else 0) / _BYTES_PER_MIB, 2),
            net_sent_mb=round(net.bytes_sent / _BYTES_PER_MIB, 2),
            net_recv_mb=round(net.bytes_recv / _BYTES_PER_MIB, 2),
            active_processes=process_count,
            active_threads=total_threads,
            fps_simulated=0.0,
        )

    @staticmethod
    def get_process_metrics(pid: int) -> ProcessMetrics:
        """Capture resource metrics for a specific process.

        Args:
            pid: OS process identifier.

        Returns:
            A ``ProcessMetrics`` instance.

        Raises:
            psutil.NoSuchProcess: If the PID does not exist.
            psutil.AccessDenied: If access to the process is restricted.
        """
        proc = psutil.Process(pid)
        with proc.oneshot():
            # Call cpu_percent once to prime, then again for a reading.
            proc.cpu_percent(interval=None)
            time.sleep(0.1)
            cpu_pct = proc.cpu_percent(interval=None)

            mem_pct = proc.memory_percent()
            threads = proc.num_threads()
            status = proc.status()
            name = proc.name()

        return ProcessMetrics(
            pid=pid,
            name=name,
            cpu_percent=round(cpu_pct, 2),
            memory_percent=round(mem_pct, 2),
            num_threads=threads,
            status=status,
        )

    # ---- time-series capture --------------------------------------------- #

    def monitor_for_duration(
        self,
        duration_seconds: float,
        interval: float = 0.5,
    ) -> List[SystemSnapshot]:
        """Capture system snapshots at fixed intervals.

        Args:
            duration_seconds: Total wall-clock time to monitor.
            interval: Seconds between consecutive snapshots.

        Returns:
            Ordered list of ``SystemSnapshot`` instances.
        """
        if duration_seconds <= 0:
            return []

        snapshots: List[SystemSnapshot] = []
        end_time = time.monotonic() + duration_seconds
        while time.monotonic() < end_time:
            snapshots.append(self.get_system_snapshot())
            remaining = end_time - time.monotonic()
            if remaining > 0:
                time.sleep(min(interval, remaining))
        return snapshots

    # ---- anomaly detection ----------------------------------------------- #

    @staticmethod
    def detect_anomalies(
        snapshots: List[SystemSnapshot],
    ) -> List[ResourceAnomaly]:
        """Detect resource anomalies in a sequence of snapshots.

        Detection rules:
        * **CPU spike** – any snapshot with ``cpu_percent_avg`` > 90 %.
        * **Memory leak** – five or more consecutive increases in
          ``ram_used_mb`` (monotonic climb).
        * **Disk I/O bottleneck** – disk write rate exceeds 500 MiB between
          consecutive snapshots.

        Args:
            snapshots: Time-ordered list of system snapshots.

        Returns:
            List of ``ResourceAnomaly`` instances.
        """
        anomalies: List[ResourceAnomaly] = []
        if not snapshots:
            return anomalies

        # -- CPU spikes ---------------------------------------------------- #
        cpu_spike_threshold = 90.0
        for snap in snapshots:
            if snap.cpu_percent_avg > cpu_spike_threshold:
                anomalies.append(
                    ResourceAnomaly(
                        timestamp=snap.timestamp,
                        metric_name="cpu_percent_avg",
                        value=snap.cpu_percent_avg,
                        threshold=cpu_spike_threshold,
                        severity=Severity.CRITICAL if snap.cpu_percent_avg > 95.0 else Severity.MAJOR,
                        description=(
                            f"CPU spike detected: {snap.cpu_percent_avg:.1f}% "
                            f"(threshold {cpu_spike_threshold}%)."
                        ),
                    )
                )

        # -- Memory leak (monotonic increase) ------------------------------ #
        monotonic_window = 5
        consecutive_increases = 0
        for i in range(1, len(snapshots)):
            if snapshots[i].ram_used_mb > snapshots[i - 1].ram_used_mb:
                consecutive_increases += 1
                if consecutive_increases >= monotonic_window:
                    anomalies.append(
                        ResourceAnomaly(
                            timestamp=snapshots[i].timestamp,
                            metric_name="ram_used_mb",
                            value=snapshots[i].ram_used_mb,
                            threshold=snapshots[i - monotonic_window].ram_used_mb,
                            severity=Severity.MAJOR,
                            description=(
                                f"Possible memory leak: RAM rose monotonically for "
                                f"{consecutive_increases} consecutive samples "
                                f"({snapshots[i - monotonic_window].ram_used_mb:.1f} → "
                                f"{snapshots[i].ram_used_mb:.1f} MiB)."
                            ),
                        )
                    )
            else:
                consecutive_increases = 0

        # -- Disk I/O bottleneck ------------------------------------------- #
        disk_write_threshold_mb = 500.0
        for i in range(1, len(snapshots)):
            delta = snapshots[i].disk_write_mb - snapshots[i - 1].disk_write_mb
            if delta > disk_write_threshold_mb:
                anomalies.append(
                    ResourceAnomaly(
                        timestamp=snapshots[i].timestamp,
                        metric_name="disk_write_mb_delta",
                        value=delta,
                        threshold=disk_write_threshold_mb,
                        severity=Severity.MINOR,
                        description=(
                            f"Disk I/O bottleneck: {delta:.1f} MiB written between "
                            f"consecutive snapshots (threshold {disk_write_threshold_mb} MiB)."
                        ),
                    )
                )

        return anomalies

    # ---- synthetic load curves ------------------------------------------- #

    @staticmethod
    def generate_synthetic_load_curve(
        duration_seconds: float,
        profile: str = "gaming",
    ) -> List[SystemSnapshot]:
        """Generate realistic synthetic system-metric time series.

        Supported profiles:

        * ``"gaming"`` – FPS 30-144 with occasional frame drops, CPU 40-85 %,
          RAM gradually climbing.
        * ``"stress_test"`` – sustained high CPU / RAM / disk utilisation.
        * ``"idle"`` – near-zero activity with minor fluctuations.
        * ``"memory_leak"`` – RAM grows linearly while other metrics stay
          moderate.

        No external dependencies (uses ``random`` and ``math`` only).

        Args:
            duration_seconds: Simulated duration in seconds.
            profile: One of ``"gaming"``, ``"stress_test"``, ``"idle"``,
                ``"memory_leak"``.

        Returns:
            Time-ordered list of ``SystemSnapshot`` instances.

        Raises:
            ValueError: If *profile* is not recognised.
        """
        valid_profiles = {"gaming", "stress_test", "idle", "memory_leak"}
        if profile not in valid_profiles:
            raise ValueError(
                f"Unknown profile {profile!r}. Choose from {sorted(valid_profiles)}."
            )

        if duration_seconds <= 0:
            return []

        interval = 0.5
        num_samples = max(1, int(duration_seconds / interval))
        core_count = psutil.cpu_count(logical=True) or 4
        total_ram_mb = round(psutil.virtual_memory().total / _BYTES_PER_MIB, 2)

        snapshots: List[SystemSnapshot] = []
        base_time = datetime.now(timezone.utc)

        # Helpers for bounded Gaussian noise.
        def _gauss(mu: float, sigma: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, random.gauss(mu, sigma)))

        # Per-profile parameter generators.
        def _gaming(idx: int) -> dict:  # type: ignore[type-arg]
            t = idx / max(num_samples - 1, 1)
            # FPS: base 90, occasional dip events.
            fps_base = 90.0
            fps_jitter = _gauss(0, 8, -20, 20)
            # Simulate occasional severe frame drops (~5 % chance).
            if random.random() < 0.05:
                fps_jitter -= random.uniform(30, 55)
            fps = max(10.0, min(144.0, fps_base + fps_jitter))

            cpu_avg = _gauss(62.0, 10.0, 40.0, 85.0)
            # Higher CPU when FPS drops (GPU-bound stutter → CPU retry).
            if fps < 45:
                cpu_avg = _gauss(80.0, 5.0, 70.0, 95.0)

            # RAM climbs gently over session.
            ram_base = total_ram_mb * 0.45
            ram_used = ram_base + (total_ram_mb * 0.15 * t) + _gauss(0, 50, -100, 100)
            ram_used = max(0, min(total_ram_mb, ram_used))

            disk_r = 200 + t * 800 + _gauss(0, 30, -60, 60)
            disk_w = 50 + t * 300 + _gauss(0, 20, -40, 40)

            return dict(
                cpu_avg=round(cpu_avg, 2),
                ram_used=round(ram_used, 2),
                fps=round(fps, 2),
                disk_r=round(max(0, disk_r), 2),
                disk_w=round(max(0, disk_w), 2),
            )

        def _stress_test(idx: int) -> dict:  # type: ignore[type-arg]
            t = idx / max(num_samples - 1, 1)
            cpu_avg = _gauss(92.0, 4.0, 80.0, 100.0)
            ram_used = total_ram_mb * (0.75 + 0.2 * t) + _gauss(0, 30, -60, 60)
            ram_used = max(0, min(total_ram_mb, ram_used))
            fps = _gauss(25.0, 8.0, 8.0, 60.0)
            disk_r = 1000 + t * 2000 + _gauss(0, 80, -150, 150)
            disk_w = 800 + t * 1500 + _gauss(0, 60, -120, 120)
            return dict(
                cpu_avg=round(cpu_avg, 2),
                ram_used=round(ram_used, 2),
                fps=round(fps, 2),
                disk_r=round(max(0, disk_r), 2),
                disk_w=round(max(0, disk_w), 2),
            )

        def _idle(idx: int) -> dict:  # type: ignore[type-arg]
            cpu_avg = _gauss(3.0, 1.5, 0.0, 12.0)
            ram_used = total_ram_mb * 0.20 + _gauss(0, 20, -40, 40)
            ram_used = max(0, min(total_ram_mb, ram_used))
            fps = 0.0  # No game running.
            disk_r = _gauss(5, 3, 0, 20)
            disk_w = _gauss(2, 1.5, 0, 10)
            return dict(
                cpu_avg=round(cpu_avg, 2),
                ram_used=round(ram_used, 2),
                fps=round(fps, 2),
                disk_r=round(max(0, disk_r), 2),
                disk_w=round(max(0, disk_w), 2),
            )

        def _memory_leak(idx: int) -> dict:  # type: ignore[type-arg]
            t = idx / max(num_samples - 1, 1)
            cpu_avg = _gauss(50.0, 6.0, 30.0, 70.0)
            # Linear RAM climb – the hallmark of a leak.
            ram_used = total_ram_mb * (0.30 + 0.60 * t) + _gauss(0, 10, -15, 15)
            ram_used = max(0, min(total_ram_mb, ram_used))
            fps_base = 80.0 - 40.0 * t  # Degrades as RAM fills.
            fps = max(5.0, fps_base + _gauss(0, 4, -10, 10))
            disk_r = 100 + _gauss(0, 15, -30, 30)
            disk_w = 80 + t * 600 + _gauss(0, 20, -40, 40)  # Paging grows.
            return dict(
                cpu_avg=round(cpu_avg, 2),
                ram_used=round(ram_used, 2),
                fps=round(fps, 2),
                disk_r=round(max(0, disk_r), 2),
                disk_w=round(max(0, disk_w), 2),
            )

        profile_fn = {
            "gaming": _gaming,
            "stress_test": _stress_test,
            "idle": _idle,
            "memory_leak": _memory_leak,
        }[profile]

        cumulative_net_sent = 0.0
        cumulative_net_recv = 0.0

        for i in range(num_samples):
            params = profile_fn(i)
            cpu_avg: float = params["cpu_avg"]

            # Distribute CPU across cores with per-core jitter.
            per_core: List[float] = []
            for _ in range(core_count):
                core_val = _gauss(cpu_avg, cpu_avg * 0.15, 0.0, 100.0)
                per_core.append(round(core_val, 2))

            # Network traffic: gentle accumulation.
            cumulative_net_sent += max(0, _gauss(0.3, 0.15, 0.0, 2.0))
            cumulative_net_recv += max(0, _gauss(0.8, 0.3, 0.0, 5.0))

            ram_used_val: float = params["ram_used"]
            ram_pct = round(ram_used_val / total_ram_mb * 100, 2) if total_ram_mb else 0.0

            snap = SystemSnapshot(
                timestamp=base_time.__class__(
                    base_time.year,
                    base_time.month,
                    base_time.day,
                    base_time.hour,
                    base_time.minute,
                    base_time.second,
                    base_time.microsecond + int(i * interval * 1_000_000) % 1_000_000,
                    tzinfo=timezone.utc,
                ),
                cpu_percent_per_core=per_core,
                cpu_percent_avg=cpu_avg,
                ram_used_mb=ram_used_val,
                ram_total_mb=total_ram_mb,
                ram_percent=ram_pct,
                disk_read_mb=params["disk_r"],
                disk_write_mb=params["disk_w"],
                net_sent_mb=round(cumulative_net_sent, 2),
                net_recv_mb=round(cumulative_net_recv, 2),
                active_processes=int(_gauss(250, 30, 100, 500)),
                active_threads=int(_gauss(1800, 200, 800, 4000)),
                fps_simulated=params["fps"],
            )
            # Fix timestamp to actually increment properly.
            snap.timestamp = base_time.__class__.fromtimestamp(
                base_time.timestamp() + i * interval,
                tz=timezone.utc,
            )
            snapshots.append(snap)

        return snapshots
