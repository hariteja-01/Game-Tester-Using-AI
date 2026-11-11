# ⚡ Agentic-QA-Platform: Autonomous Multi-Agent Game Testing & Telemetry Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38+-FF4B4B.svg)](https://streamlit.io)
[![Google Gemini API](https://img.shields.io/badge/Google%20Gemini-SDK%20Integrated-4285F4.svg)](https://ai.google.dev/)
[![CI/CD Ready](https://img.shields.io/badge/CI%2FCD-JUnit%20%7C%20SARIF%20v2.1-success.svg)](https://github.com/hariteja-01/Game-Tester-Using-AI)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, production-ready **Autonomous Multi-Agent Telemetry & QA Platform** for video games and real-time graphics applications. Engineered to shift game quality assurance from static mock reports to an active **Multi-Agent Orchestration Engine** that captures live process metrics (`psutil`), executes autonomous Root Cause Analysis (RCA), generates automated Git unified diff code patches, and exports CI/CD integration artifacts (JUnit XML, SARIF v2.1.0, Release Risk Scores).

---

## 🌟 Key Features

- **Multi-Agent Orchestration**: Stateful pipeline coordinating 4 specialized AI agents:
  1. 🟢 `StressAgent`: Synthesizes dynamic runtime edge-cases and quantitative workload parameters.
  2. 🔵 `TelemetryAgent`: Ingests real process execution metrics via `psutil` (or high-fidelity Gaussian synthetic gaming curves).
  3. 🟡 `RCAAgent`: Deep stack-trace and log correlation for automated root cause attribution.
  4. 🟣 `PatchAgent`: Synthesizes production-ready C++/C# Git unified diff patches (`.patch` format) proposing direct codebase fixes.
- **Deterministic Release Risk Scoring**: 0–100 safety score evaluating memory leak slopes, thread contention, and defect severity counts to power automated CI/CD release gates.
- **Enterprise CI/CD Artifacts**:
  - **JUnit XML Exporter**: Compatible with GitHub Actions, Jenkins, and GitLab CI.
  - **SARIF v2.1.0 Exporter**: Direct integration with GitHub Code Scanning & security dashboards.
  - **Pre-commit Git Hooks**: Automated local gatekeeping before pull requests.
- **Modern Dark Engineering Dashboard**: Sleek, glass-morphism developer portal featuring Plotly telemetry charts, interactive Gantt reasoning timelines, side-by-side log inspectors, and syntax-highlighted diff viewers.
- **Zero-Trust Security**: No hardcoded API keys. Dynamic retrieval via `os.getenv("GEMINI_API_KEY")` and Streamlit `st.secrets` with complete `.gitignore` enforcement.

---

## 🏗️ Architecture & Directory Structure

```
agentic_qa_platform/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py        # Central state graph controller & execution pipeline
│   ├── stress_agent.py        # Synthetic load & edge-case test scenario generator
│   ├── telemetry_agent.py     # Real-time process & metric ingestion agent
│   ├── rca_agent.py           # Deep stack-trace & log Root Cause Analysis agent
│   └── patch_agent.py         # Autonomous Git-diff/patch generation agent
├── telemetry/
│   ├── __init__.py
│   ├── process_monitor.py     # Live tracking via psutil (CPU, RAM, GPU, threads, I/O)
│   └── log_parser.py          # Structured parsing of crash logs & stack traces
├── cicd/
│   ├── __init__.py
│   ├── junit_exporter.py      # Standard JUnit XML test execution reports
│   ├── sarif_exporter.py      # SARIF v2.1.0 static analysis / defect reports
│   └── risk_scorer.py         # Deterministic Release Risk Score calculation (0-100)
├── ui/
│   ├── __init__.py
│   ├── components.py          # Custom dark-themed glass-morphism cards & Plotly charts
│   └── trace_viewer.py        # Visualizer for multi-agent reasoning traces & Gantt timeline
├── app.py                     # Main Streamlit application entry point
├── requirements.txt           # Production dependencies
└── README.md
```

---

## 🚀 Quickstart

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/hariteja-01/Game-Tester-Using-AI.git
cd Game-Tester-Using-AI

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install production dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials (Secure)

Create a local `.env` file (which is strictly excluded by `.gitignore`):

```bash
# .env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

*Note: The platform also supports runtime key entry via the dashboard UI or deployment secrets (`.streamlit/secrets.toml`).*

### 3. Launch the Developer Portal

```bash
streamlit run app.py
```

The portal will open at `http://localhost:8501`.

---

## 📊 Dashboard Modules

1. **System Overview & KPIs**: Real-time KPI metric cards, Release Risk Gauge (0–100), Framerate Stability Timeline (60/30 FPS thresholds), CPU vs. RAM utilization curves, and bug severity charts.
2. **Agent Reasoning Traces**: Interactive Gantt execution timeline displaying start/end timestamps, step-level latencies, and expandable JSON payloads for all 4 autonomous agents.
3. **RCA & Autonomous Patching**: Filterable live engine log feed paired with AI root cause attribution and syntax-highlighted, downloadable `.patch` files.
4. **CI/CD & Compliance Hub**: One-click downloads for `junit_report.xml`, `sarif_report.json`, `.pre-commit-config.yaml`, and copyable GitHub Actions CI workflow definitions.

---

## 🔄 CI/CD Pipeline Integration

### GitHub Actions Workflow

Add this to `.github/workflows/agentic_qa.yml`:

```yaml
name: Agentic QA Game Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  telemetry-qa:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Execute Autonomous QA Platform
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          python -c "from agentic_qa_platform.agents import Orchestrator; o = Orchestrator(); res = o.run_full_analysis('Cyberpunk 2077'); assert res.risk_assessment.overall_score >= 50, 'Release Gate Blocked!'"
```

---

## 🌐 Deployment to Streamlit Community Cloud

1. Push this repository to your GitHub account.
2. Navigate to [share.streamlit.io](https://share.streamlit.io/) and select this repository.
3. Set **Main file path** to `app.py`.
4. Under **Advanced settings > Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_google_gemini_api_key"
   ```
5. Click **Deploy**!

---

## 🛡️ Security & Zero-Leakage Guarantee

- Local `.env` and `.streamlit/secrets.toml` are strictly defined in `.gitignore`.
- Fallback heuristic mechanisms ensure the platform operates seamlessly even during network isolation or upstream API downtime.
- No confidential credentials or tokens are ever embedded in commits or artifacts.

---

## 📜 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
