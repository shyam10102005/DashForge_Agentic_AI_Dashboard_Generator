"""
DashForge - FastAPI Backend
REST API for the dashboard generation pipeline.
"""
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from backend.config import settings
from backend.orchestrator import orchestrator
from backend.models import OutputTarget, ThemePreset, PipelineRun
from backend.llm_service import llm


# =============================================
# FastAPI App
# =============================================
app = FastAPI(
    title="DashForge",
    description="Agentic AI Dashboard Generator — Power BI & Tableau",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for pipeline runs
_runs: dict[str, PipelineRun] = {}


# =============================================
# Request/Response Models
# =============================================
class PipelineRequest(BaseModel):
    target: str = "both"
    theme: str = "corporate_blue"
    custom_colors: list[str] = []
    user_chart_requests: list[str] = []


# =============================================
# API Endpoints
# =============================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    ollama_ok = await llm.check_health()
    return {
        "status": "healthy",
        "version": settings.app.version,
        "ollama_connected": ollama_ok,
        "ollama_model": settings.ollama.model,
    }


@app.post("/pipeline/run")
async def run_pipeline(
    files: list[UploadFile] = File(...),
    target: str = Form("both"),
    theme: str = Form("corporate_blue"),
    user_charts: str = Form(""),
):
    """Run the full dashboard generation pipeline.

    Upload one or more files (CSV, XLSX, ZIP) and generate Power BI / Tableau dashboards.
    """
    # Validate target
    try:
        output_target = OutputTarget(target)
    except ValueError:
        raise HTTPException(400, f"Invalid target: {target}. Must be 'powerbi', 'tableau', or 'both'.")

    try:
        theme_preset = ThemePreset(theme)
    except ValueError:
        theme_preset = ThemePreset.CORPORATE_BLUE

    # Save uploaded files
    file_infos = []
    for upload_file in files:
        file_id = uuid.uuid4().hex[:8]
        filename = upload_file.filename or f"dataset_{file_id}.csv"
        save_path = Path(settings.storage.upload_dir) / f"{file_id}_{filename}"

        with open(save_path, "wb") as f:
            content = await upload_file.read()
            f.write(content)

        file_infos.append({
            "path": str(save_path),
            "filename": filename,
        })

    # Parse user chart requests
    chart_requests = [c.strip() for c in user_charts.split(",") if c.strip()] if user_charts else []

    # Run pipeline
    run = await orchestrator.run_pipeline(
        file_paths=file_infos,
        target=output_target,
        theme=theme_preset,
        user_chart_requests=chart_requests,
    )

    _runs[run.run_id] = run

    return {
        "run_id": run.run_id,
        "status": run.status.value,
        "dashboard_title": run.dashboard_plan.dashboard_title if run.dashboard_plan else None,
        "datasets": [
            {
                "filename": ds.filename,
                "table_name": ds.table_name,
                "rows": ds.row_count,
                "columns": ds.column_count,
                "quality_score": ds.data_quality_score,
                "duplicates": ds.duplicate_row_count,
            }
            for ds in run.datasets
        ],
        "preprocessing_steps": len(run.preprocessing_logs),
        "sql_queries_executed": len(run.sql_artifacts),
        "dashboard_sheets": len(run.dashboard_plan.sheets) if run.dashboard_plan else 0,
        "output_folder": run.output_folder,
        "error": run.error,
        "events": [
            {"step": e.step, "message": e.message, "timestamp": str(e.timestamp)}
            for e in run.events
        ],
    }


@app.get("/pipeline/{run_id}")
async def get_pipeline_run(run_id: str):
    """Get the status and results of a pipeline run."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Pipeline run '{run_id}' not found.")

    return {
        "run_id": run.run_id,
        "status": run.status.value,
        "target": run.target.value,
        "theme": run.theme.value,
        "dashboard_title": run.dashboard_plan.dashboard_title if run.dashboard_plan else None,
        "datasets": [ds.model_dump() for ds in run.datasets],
        "preprocessing_logs": [l.model_dump() for l in run.preprocessing_logs],
        "dashboard_plan": run.dashboard_plan.model_dump() if run.dashboard_plan else None,
        "sql_artifacts_count": len(run.sql_artifacts),
        "has_powerbi": run.powerbi_package is not None,
        "has_tableau": run.tableau_package is not None,
        "output_folder": run.output_folder,
        "events": [e.model_dump() for e in run.events],
        "error": run.error,
    }


@app.get("/pipeline/{run_id}/download")
async def download_output(run_id: str):
    """Download the complete output as a ZIP file."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Pipeline run '{run_id}' not found.")
    if not run.output_folder:
        raise HTTPException(400, "Output folder not available.")

    zip_bytes = packaging_from_run(run)

    folder_name = Path(run.output_folder).name
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={folder_name}.zip"}
    )


@app.get("/pipeline/{run_id}/dax")
async def get_dax_measures(run_id: str):
    """Get the generated DAX measures script."""
    run = _runs.get(run_id)
    if not run or not run.powerbi_package:
        raise HTTPException(404, "DAX measures not available.")
    return {"dax_script": run.powerbi_package.dax_script}


@app.get("/pipeline/{run_id}/m-code")
async def get_m_code(run_id: str):
    """Get the generated Power Query M code."""
    run = _runs.get(run_id)
    if not run or not run.powerbi_package:
        raise HTTPException(404, "M code not available.")
    return {"m_script": run.powerbi_package.m_script}


@app.get("/pipeline/{run_id}/dashboard-html")
async def get_dashboard_html(run_id: str):
    """Get the generated standalone HTML dashboard."""
    run = _runs.get(run_id)
    if not run or not getattr(run, "dashboard_html", None):
        raise HTTPException(404, "Dashboard HTML not available.")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=run.dashboard_html)


@app.get("/pipeline/{run_id}/tableau-fields")
async def get_tableau_fields(run_id: str):
    """Get the generated Tableau calculated fields and replication guide."""
    run = _runs.get(run_id)
    if not run or not run.tableau_package:
        raise HTTPException(404, "Tableau package not available.")
    return {
        "calculated_fields": run.tableau_package.calculated_fields,
        "calculated_fields_script": run.tableau_package.calculated_fields_script,
        "replication_guide": run.tableau_package.replication_guide
    }


@app.get("/pipeline/{run_id}/twb")
async def get_twb(run_id: str):
    """Get the generated Tableau .twb XML (legacy endpoint)."""
    run = _runs.get(run_id)
    if not run or not run.tableau_package:
        raise HTTPException(404, "Tableau workbook not available.")
    return {"twb_xml": run.tableau_package.twb_xml}


@app.get("/pipeline/{run_id}/sql")
async def get_sql_results(run_id: str):
    """Get all SQL queries and their results."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Pipeline run '{run_id}' not found.")

    return {
        "queries": [
            {
                "description": a.description,
                "sql": a.sql,
                "success": a.success,
                "row_count": a.row_count,
                "columns": a.columns,
                "rows": a.rows[:20],
                "execution_time_ms": a.execution_time_ms,
                "error": a.error,
            }
            for a in run.sql_artifacts
        ]
    }


@app.get("/pipeline/{run_id}/python")
async def get_python_code(run_id: str):
    """Get generated Python preprocessing code."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Pipeline run '{run_id}' not found.")

    return {
        "artifacts": [
            {
                "filename": a.filename,
                "description": a.description,
                "code": a.code,
                "output": a.output,
            }
            for a in run.python_artifacts
        ]
    }


@app.get("/runs")
async def list_runs():
    """List all pipeline runs."""
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "status": r.status.value,
                "dashboard_title": r.dashboard_plan.dashboard_title if r.dashboard_plan else None,
                "datasets": len(r.datasets),
                "started_at": str(r.started_at),
                "completed_at": str(r.completed_at) if r.completed_at else None,
            }
            for r in _runs.values()
        ]
    }


def packaging_from_run(run: PipelineRun) -> bytes:
    """Create ZIP from run output folder."""
    from backend.agents.packaging_agent import packaging_agent
    return packaging_agent.create_zip_bundle(run.output_folder)
