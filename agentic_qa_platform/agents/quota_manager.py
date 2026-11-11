"""API Quota & Dual-Tier Key Manager for Agentic QA Platform.

Monitors platform default Gemini API key utilization and enforces the 50%
quota guardrail:
- Tracks total API calls / prompt invocations against a daily platform budget.
- Once 50% usage is reached, execution with the platform key is paused and
  the user is prompted with two options:
    1. Enter their own personal Google Gemini API key to unlock unlimited testing.
    2. Continue in offline rule-based heuristic mode.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_QUOTA_FILE = _REPO_ROOT / ".agent_quota.json"

DEFAULT_BUDGET_CALLS = 40
QUOTA_THRESHOLD_PERCENT = 50.0  # 50% limit threshold


class QuotaManager:
    """Manages API usage tracking and 50% threshold enforcement."""

    def __init__(self, budget_calls: int = DEFAULT_BUDGET_CALLS) -> None:
        self.budget_calls = budget_calls
        self._load_state()

    def _load_state(self) -> None:
        """Load state from local file or initialize default."""
        self.calls_made: int = 0
        self.last_reset: str = datetime.now(timezone.utc).date().isoformat()

        if _QUOTA_FILE.is_file():
            try:
                with open(_QUOTA_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    today = datetime.now(timezone.utc).date().isoformat()
                    if data.get("date") == today:
                        self.calls_made = int(data.get("calls_made", 0))
                        self.last_reset = data.get("date", today)
                    else:
                        # Reset for new day
                        self.calls_made = 0
                        self.last_reset = today
                        self._save_state()
            except Exception:
                self.calls_made = 0
                self._save_state()

    def _save_state(self) -> None:
        """Persist state to disk safely."""
        try:
            data = {
                "date": self.last_reset,
                "calls_made": self.calls_made,
                "budget_calls": self.budget_calls,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(_QUOTA_FILE, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    def record_usage(self, calls: int = 1) -> None:
        """Increment usage count and persist."""
        self._load_state()
        self.calls_made += calls
        self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Return current quota metrics and status."""
        self._load_state()
        percent_used = (self.calls_made / float(self.budget_calls)) * 100.0
        is_threshold_hit = percent_used >= QUOTA_THRESHOLD_PERCENT
        calls_remaining_before_threshold = max(
            0, int((self.budget_calls * (QUOTA_THRESHOLD_PERCENT / 100.0)) - self.calls_made)
        )

        return {
            "calls_made": self.calls_made,
            "budget_calls": self.budget_calls,
            "percent_used": round(min(100.0, percent_used), 1),
            "threshold_percent": QUOTA_THRESHOLD_PERCENT,
            "is_threshold_hit": is_threshold_hit,
            "calls_remaining_before_threshold": calls_remaining_before_threshold,
            "last_reset": self.last_reset,
        }

    def check_execution_permission(
        self,
        active_key: str,
        platform_default_key: str,
    ) -> Tuple[bool, str, str]:
        """Determine if testing can proceed with the current key configuration.

        Returns
        -------
        Tuple[bool, str, str]
            (allowed, mode, reason)
            - mode in ("custom_key", "platform_key", "heuristic_mode", "blocked")
        """
        status = self.get_status()

        # If user has entered their own custom key (different from platform default)
        if active_key and active_key != platform_default_key:
            return True, "custom_key", "Using personal user Gemini key with unlimited quota."

        # If user explicitly chose heuristic mode (no key)
        if not active_key:
            return True, "heuristic_mode", "Running in offline rule-based heuristic mode."

        # Active key is the platform default key
        if status["is_threshold_hit"]:
            return (
                False,
                "blocked",
                f"Platform Gemini key usage has reached {status['percent_used']:.0f}% (Threshold: 50%). "
                "Please enter your own Google Gemini API key or continue in heuristic mode.",
            )

        return (
            True,
            "platform_key",
            f"Using platform key ({status['percent_used']:.0f}% used of 50% limit).",
        )

    def reset_usage(self) -> None:
        """Admin reset for quota counter."""
        self.calls_made = 0
        self._save_state()
