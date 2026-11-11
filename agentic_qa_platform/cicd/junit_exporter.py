"""JUnit XML test report exporter for the Agentic QA Platform.

Generates standard JUnit XML test execution reports compatible with Jenkins,
GitHub Actions, GitLab CI, Azure DevOps, and other CI/CD systems.

Example usage::

    from agentic_qa_platform.cicd.junit_exporter import JUnitExporter, TestResult

    exporter = JUnitExporter()
    tests = [
        TestResult(
            name="test_player_movement",
            classname="GameTests.PlayerTests",
            time_seconds=1.25,
            status="PASS",
        ),
        TestResult(
            name="test_collision_detection",
            classname="GameTests.PhysicsTests",
            time_seconds=0.83,
            status="FAIL",
            failure_message="Collision missed between player and wall",
            failure_type="AssertionError",
        ),
    ]
    xml_str = exporter.create_test_suite("GameTests", tests)
    exporter.export_to_file(xml_str, "results/junit_report.xml")
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestStatus(str, Enum):
    """Allowed statuses for a single test result."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"


class TestResult(BaseModel):
    """Represents the outcome of a single test case.

    Attributes:
        name: Short test-case name (e.g. ``test_player_spawn``).
        classname: Dot-separated class path (e.g. ``GameTests.SpawnTests``).
        time_seconds: Wall-clock execution time in seconds.
        status: One of PASS, FAIL, ERROR, or SKIP.
        failure_message: Human-readable failure description (for FAIL/ERROR).
        failure_type: Exception or error class name (for FAIL/ERROR).
        system_out: Captured stdout for this test case.
    """

    name: str = Field(..., min_length=1, description="Test case name")
    classname: str = Field(..., min_length=1, description="Dot-separated class path")
    time_seconds: float = Field(..., ge=0.0, description="Execution time in seconds")
    status: TestStatus = Field(..., description="Test outcome")
    failure_message: Optional[str] = Field(
        default=None, description="Failure description"
    )
    failure_type: Optional[str] = Field(
        default=None, description="Exception / error type name"
    )
    system_out: Optional[str] = Field(
        default=None, description="Captured stdout"
    )


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class JUnitExporter:
    """Builds and writes JUnit XML test-suite documents.

    All generated XML conforms to the JUnit XML schema consumed by major
    CI/CD platforms. The exporter is stateless; every public method is
    self-contained and can be called independently.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_test_suite(
        self,
        name: str,
        tests: List[TestResult],
        *,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Build a complete JUnit XML string for a test suite.

        Args:
            name: Human-readable suite name.
            tests: Ordered list of :class:`TestResult` objects.
            timestamp: Optional explicit timestamp; defaults to *now* (UTC).

        Returns:
            A well-formed XML string with ``<?xml …?>`` declaration.

        Raises:
            ValueError: If *name* is empty or *tests* is empty.
        """
        if not name:
            raise ValueError("Test suite name must not be empty.")
        if not tests:
            raise ValueError("At least one TestResult is required.")

        ts = timestamp or datetime.now(timezone.utc)

        failures = sum(1 for t in tests if t.status == TestStatus.FAIL)
        errors = sum(1 for t in tests if t.status == TestStatus.ERROR)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIP)
        total_time = sum(t.time_seconds for t in tests)

        suite = ET.Element("testsuite")
        suite.set("name", name)
        suite.set("tests", str(len(tests)))
        suite.set("failures", str(failures))
        suite.set("errors", str(errors))
        suite.set("skipped", str(skipped))
        suite.set("time", f"{total_time:.3f}")
        suite.set("timestamp", ts.strftime("%Y-%m-%dT%H:%M:%S"))

        for test in tests:
            self._add_testcase(suite, test)

        tree = ET.ElementTree(suite)
        ET.indent(tree, space="  ")

        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        return xml_declaration + ET.tostring(suite, encoding="unicode")

    def export_to_file(self, suite_xml: str, filepath: str) -> str:
        """Write a JUnit XML string to *filepath*.

        Parent directories are created automatically if they do not exist.

        Args:
            suite_xml: XML string produced by :meth:`create_test_suite`.
            filepath: Destination file path (absolute or relative).

        Returns:
            The absolute path of the written file.

        Raises:
            OSError: If the file cannot be written.
        """
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(suite_xml)

        return abs_path

    def from_bug_reports(self, bugs: list, game_name: str) -> str:
        """Convert a list of bug-report dicts into a JUnit XML string.

        Each bug becomes a *failed* test case. The ``game_name`` is used as
        the suite name and classname prefix.

        Expected dict keys per bug (all optional except ``title``):

        * ``title`` – short summary (used as test name).
        * ``severity`` – e.g. ``"critical"``, ``"major"``, ``"minor"``.
        * ``description`` – full bug description (maps to failure message).
        * ``category`` – bug category (appended to classname).
        * ``timestamp`` – ISO-format string; used for ordering only.

        Args:
            bugs: List of bug-report dictionaries.
            game_name: Name of the game under test.

        Returns:
            A JUnit XML string with one failed test per bug.

        Raises:
            ValueError: If *bugs* is empty or *game_name* is empty.
        """
        if not bugs:
            raise ValueError("At least one bug report is required.")
        if not game_name:
            raise ValueError("game_name must not be empty.")

        test_results: List[TestResult] = []
        for idx, bug in enumerate(bugs):
            title: str = bug.get("title", f"bug_{idx + 1}")
            severity: str = bug.get("severity", "unknown")
            description: str = bug.get("description", "No description provided.")
            category: str = bug.get("category", "General")

            sanitised_name = self._sanitise_name(title)
            classname = f"{game_name}.BugReports.{category}"

            failure_type = f"Bug/{severity.capitalize()}" if severity else "Bug"

            test_results.append(
                TestResult(
                    name=sanitised_name,
                    classname=classname,
                    time_seconds=0.0,
                    status=TestStatus.FAIL,
                    failure_message=description,
                    failure_type=failure_type,
                    system_out=f"Severity: {severity}\nTitle: {title}",
                )
            )

        return self.create_test_suite(f"{game_name} - Bug Reports", test_results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_testcase(self, parent: ET.Element, test: TestResult) -> None:
        """Append a ``<testcase>`` element to *parent*."""
        tc = ET.SubElement(parent, "testcase")
        tc.set("classname", test.classname)
        tc.set("name", test.name)
        tc.set("time", f"{test.time_seconds:.3f}")

        if test.status == TestStatus.FAIL:
            failure = ET.SubElement(tc, "failure")
            failure.set("message", test.failure_message or "Test failed")
            failure.set("type", test.failure_type or "AssertionError")
            if test.failure_message:
                failure.text = test.failure_message

        elif test.status == TestStatus.ERROR:
            error = ET.SubElement(tc, "error")
            error.set("message", test.failure_message or "Test error")
            error.set("type", test.failure_type or "RuntimeError")
            if test.failure_message:
                error.text = test.failure_message

        elif test.status == TestStatus.SKIP:
            skipped = ET.SubElement(tc, "skipped")
            if test.failure_message:
                skipped.set("message", test.failure_message)

        if test.system_out:
            sysout = ET.SubElement(tc, "system-out")
            sysout.text = test.system_out

    @staticmethod
    def _sanitise_name(raw: str) -> str:
        """Turn an arbitrary string into a safe XML-friendly test name."""
        sanitised = raw.replace(" ", "_").replace("/", "_").replace("\\", "_")
        # Strip characters that are invalid in XML names
        sanitised = "".join(
            ch for ch in sanitised if ch.isalnum() or ch in ("_", "-", ".")
        )
        return sanitised or "unnamed_test"
