"""
Agentic QA Platform — Autonomous Multi-Agent Telemetry & QA Engine for Game Testing.

This platform provides:
- Multi-agent orchestration for automated game testing
- Live system telemetry capture via psutil
- AI-powered Root Cause Analysis (RCA)
- Autonomous Git patch generation
- CI/CD integration (JUnit XML, SARIF, Risk Scoring)
- Modern Streamlit-based developer portal

Architecture:
    agents/       — Multi-agent orchestration engine (Stress, Telemetry, RCA, Patch)
    telemetry/    — Live process monitoring and log parsing
    cicd/         — CI/CD export and risk scoring modules
    ui/           — Streamlit UI components and trace viewer
"""

__version__ = "2.0.0"
__author__ = "Agentic QA Team"
