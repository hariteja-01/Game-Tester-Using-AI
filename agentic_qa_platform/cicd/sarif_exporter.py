"""SARIF v2.1.0 report exporter for the Agentic QA Platform.

Generates Static Analysis Results Interchange Format (SARIF) reports that can
be consumed by GitHub Advanced Security, Azure DevOps, SonarQube, and other
SARIF-compatible dashboards.

Example usage::

    from agentic_qa_platform.cicd.sarif_exporter import SARIFExporter, SARIFFinding

    exporter = SARIFExporter()
    findings = [
        SARIFFinding(
            rule_id="QA001",
            message="Texture flickering detected on player model",
            level="error",
            file_path="src/rendering/player_renderer.py",
            start_line=142,
            end_line=145,
            description="Rendering artefact causing visual glitch.",
        ),
    ]
    sarif = exporter.create_sarif_report("AgenticQA", findings)
    exporter.export_to_file(sarif, "results/sarif_report.json")
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
_SARIF_VERSION = "2.1.0"
_TOOL_VERSION = "1.0.0"
_TOOL_SEMANTIC_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SARIFLevel(str, Enum):
    """Allowed SARIF result levels (severity)."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class SARIFFinding(BaseModel):
    """A single static-analysis finding to be encoded in SARIF.

    Attributes:
        rule_id: Stable identifier for the rule that produced this finding.
        message: Human-readable description of the finding.
        level: SARIF severity level (``error``, ``warning``, or ``note``).
        file_path: Relative or absolute path to the artefact.
        start_line: 1-based start line number.
        end_line: 1-based end line number (inclusive).
        description: Extended explanation of the rule / finding.
        help_uri: URL to documentation about this rule.
    """

    rule_id: str = Field(..., min_length=1, description="Unique rule identifier")
    message: str = Field(..., min_length=1, description="Finding description")
    level: SARIFLevel = Field(..., description="Severity level")
    file_path: str = Field(..., min_length=1, description="Artefact file path")
    start_line: int = Field(..., ge=1, description="Start line (1-based)")
    end_line: int = Field(..., ge=1, description="End line (1-based, inclusive)")
    description: str = Field(default="", description="Extended description")
    help_uri: Optional[str] = Field(default=None, description="Help URL")


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class SARIFExporter:
    """Builds and writes SARIF v2.1.0 JSON reports.

    The exporter is stateless; every public method is self-contained and can
    be called independently.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_sarif_report(
        self,
        tool_name: str,
        findings: List[SARIFFinding],
        *,
        tool_version: str = _TOOL_VERSION,
        semantic_version: str = _TOOL_SEMANTIC_VERSION,
    ) -> Dict[str, Any]:
        """Create a complete SARIF v2.1.0 JSON-compatible dict.

        Args:
            tool_name: Display name of the analysis tool.
            findings: List of :class:`SARIFFinding` objects.
            tool_version: Semver string for the tool.
            semantic_version: Semantic version for SARIF ``semanticVersion``.

        Returns:
            A dictionary conforming to the SARIF v2.1.0 schema, ready for
            serialisation to JSON.

        Raises:
            ValueError: If *tool_name* is empty.
        """
        if not tool_name:
            raise ValueError("tool_name must not be empty.")

        # Collect unique rules from findings
        rules_map: Dict[str, Dict[str, Any]] = {}
        for finding in findings:
            if finding.rule_id not in rules_map:
                rule_entry: Dict[str, Any] = {
                    "id": finding.rule_id,
                    "shortDescription": {"text": finding.rule_id},
                    "fullDescription": {"text": finding.description or finding.message},
                }
                if finding.help_uri:
                    rule_entry["helpUri"] = finding.help_uri
                rules_map[finding.rule_id] = rule_entry

        results: List[Dict[str, Any]] = [
            self._finding_to_result(f) for f in findings
        ]

        sarif: Dict[str, Any] = {
            "$schema": _SARIF_SCHEMA,
            "version": _SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": tool_name,
                            "version": tool_version,
                            "semanticVersion": semantic_version,
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": results,
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "startTimeUtc": datetime.now(timezone.utc).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        }
                    ],
                }
            ],
        }

        return sarif

    def export_to_file(self, sarif_data: Dict[str, Any], filepath: str) -> str:
        """Serialise a SARIF dict to a JSON file.

        Parent directories are created automatically if they do not exist.

        Args:
            sarif_data: SARIF dictionary (from :meth:`create_sarif_report`).
            filepath: Destination file path.

        Returns:
            The absolute path of the written file.

        Raises:
            OSError: If the file cannot be written.
        """
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, "w", encoding="utf-8") as fh:
            json.dump(sarif_data, fh, indent=2, ensure_ascii=False)

        return abs_path

    def from_rca_results(
        self,
        rca_results: list,
        *,
        tool_name: str = "AgenticQA-RCA",
    ) -> Dict[str, Any]:
        """Convert root-cause analysis results into a SARIF report.

        Each RCA result dict is expected to have the following keys (all
        optional except ``root_cause``):

        * ``root_cause`` – short summary of the root cause.
        * ``severity`` – ``"critical"``, ``"major"``, ``"minor"``
          (mapped to SARIF levels).
        * ``file_path`` – source file associated with the issue.
        * ``line_number`` – approximate line in the source file.
        * ``recommendation`` – suggested remediation.
        * ``rule_id`` – stable rule identifier.
        * ``category`` – issue category (used as fallback rule_id).

        Args:
            rca_results: List of RCA result dicts.
            tool_name: Tool name for the SARIF report header.

        Returns:
            A SARIF v2.1.0 dict.

        Raises:
            ValueError: If *rca_results* is empty.
        """
        if not rca_results:
            raise ValueError("At least one RCA result is required.")

        findings: List[SARIFFinding] = []
        for idx, rca in enumerate(rca_results):
            root_cause: str = rca.get("root_cause", f"RCA finding {idx + 1}")
            severity: str = rca.get("severity", "minor").lower()
            file_path: str = rca.get("file_path", "unknown")
            line_number: int = rca.get("line_number", 1)
            recommendation: str = rca.get("recommendation", "")
            rule_id: str = rca.get("rule_id", "") or rca.get("category", f"RCA-{idx + 1:04d}")

            level = self._severity_to_level(severity)

            description_parts = [root_cause]
            if recommendation:
                description_parts.append(f"Recommendation: {recommendation}")

            findings.append(
                SARIFFinding(
                    rule_id=rule_id,
                    message=root_cause,
                    level=level,
                    file_path=file_path,
                    start_line=max(1, line_number),
                    end_line=max(1, line_number),
                    description=" | ".join(description_parts),
                )
            )

        return self.create_sarif_report(tool_name, findings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _finding_to_result(finding: SARIFFinding) -> Dict[str, Any]:
        """Map a :class:`SARIFFinding` to a SARIF ``result`` object."""
        return {
            "ruleId": finding.rule_id,
            "level": finding.level.value,
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.file_path},
                        "region": {
                            "startLine": finding.start_line,
                            "endLine": finding.end_line,
                        },
                    }
                }
            ],
        }

    @staticmethod
    def _severity_to_level(severity: str) -> SARIFLevel:
        """Map common severity strings to SARIF levels."""
        mapping = {
            "critical": SARIFLevel.ERROR,
            "high": SARIFLevel.ERROR,
            "major": SARIFLevel.ERROR,
            "medium": SARIFLevel.WARNING,
            "moderate": SARIFLevel.WARNING,
            "minor": SARIFLevel.NOTE,
            "low": SARIFLevel.NOTE,
            "info": SARIFLevel.NOTE,
        }
        return mapping.get(severity.lower(), SARIFLevel.WARNING)
