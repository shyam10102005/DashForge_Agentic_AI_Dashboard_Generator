# ⚡ DashForge — Agentic AI BI & Interactive Dashboard Suite

> **Autonomous multi-agent data intelligence platform.** Ingest any dataset, perform deep statistical profiling, generate multi-sheet executive dashboards, and export standalone interactive HTML dashboards alongside copy-paste blueprints for Power BI and Tableau.

---

## 🌟 Architecture & Core Capabilities

DashForge is built as a specialized pipeline of collaborative AI agents:

```
[Uploaded Datasets (CSV/Excel)]
              │
              ▼
   ┌─────────────────────┐
   │ 📂 Ingestion Agent   │ ➔ File validation, encoding detection, DuckDB staging
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │ 🔍 Profiler Agent    │ ➔ Schema inference, nulls, duplicates, quality score
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │ 🧹 Preprocessing    │ ➔ Smart type casting, deduplication, imputation
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │ 🤖 AI Planner Agent │ ➔ Ollama local LLM (qwen3:4b) multi-sheet architecture
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │ 🗄️ SQL Engine Agent │ ➔ Analytical queries, aggregation, validation
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │ 📊 Dashboard Agent  │ ➔ Live Plotly figures, KPIs, self-contained HTML
   └──────────┬──────────┘
              ▼
   ┌────────────────────────────────────────────────────────┐
   │ 📦 Packaging & Replication Blueprint Agent              │
   ├────────────────────────┬───────────────────────────────┤
   │ 🌐 Standalone HTML     │ Complete interactive web app  │
   │ 🟡 Power BI Desktop    │ measures.dax, transform.m,    │
   │                        │ model.bim, load_powerbi.py    │
   │ 🟠 Tableau Desktop     │ calculated_fields.txt / json, │
   │                        │ shelf pill layout blueprint   │
   │ 🎁 Project Bundle      │ Full organized ZIP package    │
   └────────────────────────┴───────────────────────────────┘
```

---

## 🚀 Key Features

1. **Standalone Interactive HTML Dashboard**:
   - Zero vendor lock-in: Generates a self-contained `.html` file with dark executive styling, responsive multi-sheet tabs, KPI metric cards, and interactive Plotly charts.
   - Usable completely offline or in any modern web browser.
2. **Native In-App Visualization**:
   - Step 7 renders native Plotly charts directly inside DashForge for instant interactivity (pan, zoom, hover tooltips, box-select).
3. **Power BI Replication Blueprint**:
   - Production-ready `measures.dax` (safe DAX formulas using `DIVIDE`, `COALESCE`, `SUMX`).
   - Power Query `transform.m` script.
   - Tabular model schema `model.bim` for Tabular Editor / Analysis Services.
   - Python connector script `load_powerbi.py`.
   - Step-by-step visual mapping guide.
4. **Tableau Replication Blueprint**:
   - Production-ready calculated fields (`calculated_fields.txt` and `.json`).
   - Step-by-step shelf pill mappings (Columns, Rows, Color, Marks) for each visual sheet.
5. **Local & Private LLM Inference**:
   - Powered by local Ollama (`qwen3:4b` or any compatible model). No data leaves your machine.

---

## 📁 Project Directory Structure

```
dashforge/
├── .env                  # Environment configuration (Ollama URL, model, limits)
├── .venv/                # Dedicated self-contained Python virtual environment
├── requirements.txt      # Python dependencies
├── start_all.bat         # 1-Click launcher (starts backend + frontend)
├── run_backend.bat       # FastAPI backend launcher (Port 8001)
├── run_frontend.bat      # Streamlit frontend launcher (Port 8502)
├── backend/
│   ├── api.py            # FastAPI REST endpoints
│   ├── config.py         # Pydantic settings & environment management
│   ├── database.py       # DuckDB analytical database engine
│   ├── models.py         # Data models and schemas
│   ├── orchestrator.py   # Multi-agent pipeline controller
│   ├── llm_service.py    # Local Ollama LLM provider
│   └── agents/
│       ├── ingestion_agent.py    # Ingestion & file parser
│       ├── profiler_agent.py     # Data profiler & quality scoring
│       ├── preprocessing_agent.py# Data cleaning & transformation
│       ├── planner_agent.py      # AI Dashboard Planner & semantic ranking
│       ├── sql_agent.py          # SQL code generation & execution
│       ├── dashboard_agent.py    # Plotly interactive dashboard engine
│       ├── powerbi_agent.py      # Power BI DAX & M asset generator
│       ├── tableau_agent.py      # Tableau calculated fields & blueprints
│       ├── codegen_agent.py      # Python & SQL code generator
│       └── packaging_agent.py    # Bundle packaging (.ZIP)
├── frontend/
│   ├── app.py            # Streamlit multi-step web application
│   └── components/       # Custom UI components & CSS design tokens
├── data/
│   ├── uploads/          # Uploaded dataset staging
│   └── exports/          # Generated output bundles and dashboards
└── samples/              # Reference templates and test files
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python 3.11+**
- **Ollama** running locally with `qwen3:4b` (`ollama run qwen3:4b`)

### 2. Start DashForge (1-Click)
Double-click `start_all.bat` or run:
```powershell
.\start_all.bat
```

Or start services individually:
- **Backend API**:
  ```powershell
  .\run_backend.bat
  ```
  API Docs: [http://localhost:8001/docs](http://localhost:8001/docs)

- **Frontend UI**:
  ```powershell
  .\run_frontend.bat
  ```
  App: [http://localhost:8502](http://localhost:8502)

---

## 📊 End-to-End Workflow

1. **Step 1 — Upload**: Drag and drop CSV or Excel files (e.g., `Sales_transactions.csv`, `Sales_Data_Dictionary.csv`).
2. **Step 2 — Preferences**: Choose output targets (Power BI, Tableau, or Both) and theme preset (Corporate Blue, Modern Dark, Vibrant, etc.).
3. **Step 3 — Ingestion & Profiling**: Automated quality scores, missing values, duplicates, and semantic types.
4. **Step 4 — Preprocessing**: Automated cleaning rules and data type standardization.
5. **Step 5 — AI Planning**: The AI agent creates multi-sheet architecture tailored to your data's business dimensions and metrics.
6. **Step 6 — SQL & Analysis**: Automated SQL query execution and verification against DuckDB.
7. **Step 7 — Dashboard & Blueprints**:
   - Interact with live charts directly in DashForge.
   - Download the standalone `.html` dashboard to use or share offline.
   - Copy DAX measures, M scripts, or Tableau calculated fields using step-by-step guides.
   - Download the complete project `.zip` bundle.
