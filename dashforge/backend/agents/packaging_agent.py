"""
DashForge - Packaging Agent
Bundles all generated artifacts into a structured output folder and ZIP archive.
"""
import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

from backend.config import settings
from backend.models import (
    PipelineRun, DashboardPlan, PowerBIPackage, TableauPackage,
    PythonCodeArtifact, DatasetProfile
)


class PackagingAgent:
    """Packages all pipeline outputs into a structured folder and ZIP."""

    def create_output_folder(self, run: PipelineRun) -> str:
        """Create a structured output folder with all artifacts.

        Returns:
            Path to the output folder.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"DashForge_{run.dashboard_plan.dashboard_title.replace(' ', '_')}_{timestamp}" if run.dashboard_plan else f"DashForge_{timestamp}"
        folder_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in folder_name)

        output_dir = Path(settings.storage.output_dir) / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (output_dir / "data").mkdir(exist_ok=True)
        (output_dir / "python").mkdir(exist_ok=True)
        (output_dir / "sql").mkdir(exist_ok=True)
        (output_dir / "powerbi").mkdir(exist_ok=True)
        (output_dir / "tableau").mkdir(exist_ok=True)
        (output_dir / "docs").mkdir(exist_ok=True)

        # 1. Save cleaned data files
        for profile in run.datasets:
            from backend.database import db
            try:
                df = db.get_dataframe(profile.dataset_id, profile.table_name)
                csv_path = output_dir / "data" / f"{profile.table_name}_cleaned.csv"
                df.to_csv(csv_path, index=False)
            except Exception:
                pass

        # 2. Save Python code artifacts
        for artifact in run.python_artifacts:
            path = output_dir / "python" / artifact.filename
            with open(path, "w", encoding="utf-8") as f:
                f.write(artifact.code)

            # Save output logs
            if artifact.output:
                output_path = output_dir / "python" / f"{Path(artifact.filename).stem}_output.txt"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(artifact.output)

        # 3. Save SQL scripts
        sql_artifacts = [a for a in run.python_artifacts if a.filename.endswith(".sql")]
        for artifact in sql_artifacts:
            path = output_dir / "sql" / artifact.filename
            with open(path, "w", encoding="utf-8") as f:
                f.write(artifact.code)

        # Also save the SQL artifact outputs separately
        if run.sql_artifacts:
            sql_results_path = output_dir / "sql" / "query_results.json"
            results = []
            for sa in run.sql_artifacts:
                results.append({
                    "description": sa.description,
                    "sql": sa.sql,
                    "success": sa.success,
                    "row_count": sa.row_count,
                    "columns": sa.columns,
                    "rows": sa.rows[:20],  # First 20 rows
                    "execution_time_ms": sa.execution_time_ms,
                    "error": sa.error,
                })
            with open(sql_results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)

        # 3. Save Standalone Interactive HTML Dashboard
        if getattr(run, "dashboard_html", None):
            dash_dir = output_dir / "dashboard"
            dash_dir.mkdir(exist_ok=True)
            with open(dash_dir / "dashboard.html", "w", encoding="utf-8") as f:
                f.write(run.dashboard_html)

        # 4. Save Power BI assets
        if run.powerbi_package:
            pbi = run.powerbi_package
            pbi_dir = output_dir / "powerbi"
            pbi_dir.mkdir(exist_ok=True)

            with open(pbi_dir / "measures.dax", "w", encoding="utf-8") as f:
                f.write(pbi.dax_script)

            with open(pbi_dir / "transform.m", "w", encoding="utf-8") as f:
                f.write(pbi.m_script)

            with open(pbi_dir / "model.bim", "w", encoding="utf-8") as f:
                json.dump(pbi.model_bim_json, f, indent=2)

            with open(pbi_dir / "load_powerbi.py", "w", encoding="utf-8") as f:
                f.write(pbi.python_connector_script)

            if getattr(pbi, "replication_guide", None):
                with open(pbi_dir / "POWERBI_REPLICATION_GUIDE.md", "w", encoding="utf-8") as f:
                    f.write(pbi.replication_guide)

            # Theme file
            if run.dashboard_plan:
                from backend.agents.powerbi_agent import powerbi_agent
                theme_json = powerbi_agent.generate_theme_json(run.dashboard_plan)
                with open(pbi_dir / "theme.json", "w", encoding="utf-8") as f:
                    f.write(theme_json)

        # 5. Save Tableau assets
        if run.tableau_package:
            tab = run.tableau_package
            tab_dir = output_dir / "tableau"
            tab_dir.mkdir(exist_ok=True)

            if getattr(tab, "calculated_fields_script", None):
                with open(tab_dir / "calculated_fields.txt", "w", encoding="utf-8") as f:
                    f.write(tab.calculated_fields_script)

            if tab.calculated_fields:
                with open(tab_dir / "calculated_fields.json", "w", encoding="utf-8") as f:
                    json.dump(tab.calculated_fields, f, indent=2)

            if getattr(tab, "datasource_info", None):
                with open(tab_dir / "datasource_info.json", "w", encoding="utf-8") as f:
                    json.dump(tab.datasource_info, f, indent=2)

            if getattr(tab, "replication_guide", None):
                with open(tab_dir / "TABLEAU_REPLICATION_GUIDE.md", "w", encoding="utf-8") as f:
                    f.write(tab.replication_guide)

        # 6. Generate README
        readme = self._generate_readme(run)
        with open(output_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)

        # 7. Save dashboard plan
        if run.dashboard_plan:
            with open(output_dir / "docs" / "dashboard_plan.json", "w", encoding="utf-8") as f:
                json.dump(run.dashboard_plan.model_dump(), f, indent=2, default=str)

        # 8. Save preprocessing report
        if run.preprocessing_logs:
            report = self._generate_preprocessing_report(run)
            with open(output_dir / "docs" / "preprocessing_report.md", "w", encoding="utf-8") as f:
                f.write(report)

        # 9. Save pipeline event log
        events_log = [{"step": e.step, "status": e.status, "message": e.message, "duration_ms": e.duration_ms, "timestamp": str(e.timestamp)} for e in run.events]
        with open(output_dir / "docs" / "pipeline_log.json", "w", encoding="utf-8") as f:
            json.dump(events_log, f, indent=2)

        return str(output_dir)

    def create_zip_bundle(self, output_folder: str) -> bytes:
        """Create a ZIP archive from the output folder."""
        buffer = io.BytesIO()
        folder_path = Path(output_folder)

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(folder_path.parent)
                    zf.write(file_path, arcname=str(arcname))

        zip_bytes = buffer.getvalue()
        buffer.close()
        return zip_bytes

    def _generate_readme(self, run: PipelineRun) -> str:
        """Generate a comprehensive README for the output package."""
        title = run.dashboard_plan.dashboard_title if run.dashboard_plan else "Dashboard"
        target = run.target.value if run.target else "both"

        datasets_info = []
        for ds in run.datasets:
            datasets_info.append(f"- **{ds.filename}** ({ds.table_name}): {ds.row_count:,} rows × {ds.column_count} cols | Quality: {ds.data_quality_score}%")

        preprocessing_info = []
        for log in run.preprocessing_logs:
            preprocessing_info.append(f"- {log.step}: {log.description}")

        sheets_info = []
        if run.dashboard_plan:
            for sheet in run.dashboard_plan.sheets:
                charts = ", ".join(f"{c.chart_type.value}: {c.title}" for c in sheet.charts)
                sheets_info.append(f"- **{sheet.title}**: {len(sheet.charts)} charts ({charts})")

        readme = f"""# 📊 DashForge Output: {title}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Target Platform: {target.upper()}
Theme: {run.theme.value if run.theme else 'corporate_blue'}

---

## 📁 Folder Structure

```
├── data/                  # Cleaned datasets (CSV)
├── python/                # Preprocessing Python scripts
├── sql/                   # SQL queries and results
├── powerbi/               # Power BI assets (DAX, M, model.bim, theme)
├── tableau/               # Tableau assets (.twb, .tds, calculated fields)
├── docs/                  # Documentation and reports
└── README.md              # This file
```

## 📋 Datasets

{chr(10).join(datasets_info) if datasets_info else "No datasets loaded."}

## 🔧 Preprocessing Applied

{chr(10).join(preprocessing_info) if preprocessing_info else "No preprocessing was needed."}

## 📊 Dashboard Sheets

{chr(10).join(sheets_info) if sheets_info else "No dashboard plan generated."}

---

## 🚀 Power BI Setup

### Method 1: Python Connector (Fastest)
1. Open **Power BI Desktop**
2. **Get Data** → **Other** → **Python script** → **Connect**
3. Paste contents of `powerbi/load_powerbi.py`
4. Click **OK**, select `df_cleaned`, click **Load**
5. Paste measures from `powerbi/measures.dax`

### Method 2: CSV Import with Power Query
1. Open **Power BI Desktop**
2. **Get Data** → **Text/CSV** → Select files from `data/` folder
3. **Transform Data** → **Advanced Editor** → Paste from `powerbi/transform.m`
4. **Close & Apply**
5. Add measures from `powerbi/measures.dax`

### Method 3: Tabular Model (Advanced)
1. Open `powerbi/model.bim` in **Tabular Editor**
2. Review and deploy to Power BI Service

### Apply Theme
- In Power BI: **View** → **Themes** → **Browse for themes** → Select `powerbi/theme.json`

---

## 🎨 Tableau Setup

1. Open **Tableau Desktop**
2. **File** → **Open** → Select `tableau/dashboard.twb`
3. If prompted, point to data files in the `data/` folder
4. Review calculated fields from `tableau/calculated_fields.json`

---

## 🐍 Python Code

- `python/preprocessing.py` — Reproducible data cleaning script
- `python/preprocessing_output.txt` — Execution output log

## 🗃️ SQL Queries

- `sql/queries.sql` — All SQL queries used for data extraction
- `sql/query_results.json` — Query results in JSON format

---

*Generated by DashForge v1.0 — Agentic Dashboard Generator*
"""
        return readme

    def _generate_preprocessing_report(self, run: PipelineRun) -> str:
        """Generate a preprocessing report."""
        lines = ["# Preprocessing Report\n"]

        for ds in run.datasets:
            lines.append(f"## Dataset: {ds.filename}")
            lines.append(f"- Rows: {ds.row_count:,}")
            lines.append(f"- Columns: {ds.column_count}")
            lines.append(f"- Duplicates found: {ds.duplicate_row_count}")
            lines.append(f"- Quality Score: {ds.data_quality_score}%")
            lines.append("")

            lines.append("### Column Details")
            lines.append("| Column | Type | Nulls | Null% | Unique | Semantic Role |")
            lines.append("|--------|------|-------|-------|--------|---------------|")
            for col in ds.columns:
                lines.append(f"| {col.name} | {col.dtype} | {col.null_count} | {col.null_pct}% | {col.unique_count} | {col.semantic_role or '-'} |")
            lines.append("")

        lines.append("## Steps Applied")
        for log in run.preprocessing_logs:
            lines.append(f"- **{log.step}**: {log.description}")
            if log.columns_affected:
                lines.append(f"  - Columns: {', '.join(log.columns_affected)}")
            if log.rows_affected:
                lines.append(f"  - Rows affected: {log.rows_affected}")

        return "\n".join(lines)


# Singleton
packaging_agent = PackagingAgent()
