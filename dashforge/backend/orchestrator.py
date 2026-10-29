"""
DashForge - Pipeline Orchestrator
Master orchestrator that coordinates all agents through the full pipeline:
Ingest → Profile → Preprocess → Plan → SQL → Export (Power BI + Tableau) → Package
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.models import (
    PipelineRun, PipelineStatus, PipelineEvent, OutputTarget,
    ThemePreset, DashboardPlan
)
from backend.agents.ingestion_agent import ingestion_agent
from backend.agents.profiler_agent import profiler_agent
from backend.agents.planner_agent import planner_agent
from backend.agents.sql_agent import sql_agent
from backend.agents.powerbi_agent import powerbi_agent
from backend.agents.tableau_agent import tableau_agent
from backend.agents.codegen_agent import codegen_agent
from backend.agents.packaging_agent import packaging_agent
from backend.agents.dashboard_agent import dashboard_agent


class PipelineOrchestrator:
    """Coordinates the full dashboard generation pipeline."""

    async def run_pipeline(
        self,
        file_paths: list[dict],  # List of {path, filename}
        target: OutputTarget = OutputTarget.BOTH,
        theme: ThemePreset = ThemePreset.CORPORATE_BLUE,
        custom_colors: list[str] = None,
        user_chart_requests: list[str] = None,
        progress_callback=None,
        on_progress=None,
        **kwargs,
    ) -> PipelineRun:
        """Execute the complete dashboard generation pipeline."""
        run = PipelineRun(
            target=target,
            theme=theme,
            custom_colors=custom_colors or [],
        )

        callback = on_progress or progress_callback

        async def report(status: PipelineStatus, message: str):
            run.status = status
            event = self._add_event(run, status.value, message)
            if callback:
                try:
                    import inspect
                    if inspect.iscoroutinefunction(callback):
                        try:
                            await callback(event)
                        except TypeError:
                            await callback(status.value, message)
                    else:
                        try:
                            callback(event)
                        except TypeError:
                            callback(status.value, message)
                except Exception:
                    pass

        try:
            # ════════════════════════════════════════
            # STEP 1: INGEST DATASETS
            # ════════════════════════════════════════
            await report(PipelineStatus.INGESTING, "Ingesting datasets...")

            all_ingested = []
            for file_info in file_paths:
                if isinstance(file_info, str):
                    f_path = file_info
                    f_name = Path(file_info).name
                else:
                    f_path = file_info["path"]
                    f_name = file_info.get("filename", Path(f_path).name)
                results = await ingestion_agent.ingest(f_path, f_name)
                all_ingested.extend(results)

            await report(PipelineStatus.INGESTING,
                f"Ingested {len(all_ingested)} dataset(s)")

            # ════════════════════════════════════════
            # STEP 2: PROFILE DATASETS
            # ════════════════════════════════════════
            await report(PipelineStatus.PROFILING, "Profiling datasets...")

            profiles = []
            for ingested in all_ingested:
                profile = await profiler_agent.profile(
                    dataset_id=ingested["dataset_id"],
                    table_name=ingested["table_name"],
                    filename=ingested["filename"],
                )
                profiles.append(profile)

            run.datasets = profiles

            total_rows = sum(p.row_count for p in profiles)
            total_cols = sum(p.column_count for p in profiles)
            await report(PipelineStatus.PROFILING,
                f"Profiled {len(profiles)} dataset(s): {total_rows:,} total rows, {total_cols} total columns")

            # ════════════════════════════════════════
            # STEP 3: PREPROCESS
            # ════════════════════════════════════════
            await report(PipelineStatus.PREPROCESSING, "Preprocessing datasets...")

            all_logs = []
            for ingested in all_ingested:
                logs = await profiler_agent.preprocess(
                    dataset_id=ingested["dataset_id"],
                    table_name=ingested["table_name"],
                )
                all_logs.extend(logs)

            run.preprocessing_logs = all_logs

            # Re-profile after preprocessing
            updated_profiles = []
            for ingested in all_ingested:
                profile = await profiler_agent.profile(
                    dataset_id=ingested["dataset_id"],
                    table_name=ingested["table_name"],
                    filename=ingested["filename"],
                )
                updated_profiles.append(profile)
            run.datasets = updated_profiles
            profiles = updated_profiles

            await report(PipelineStatus.PREPROCESSING,
                f"Applied {len(all_logs)} preprocessing steps")

            # ════════════════════════════════════════
            # STEP 4: PLAN DASHBOARD
            # ════════════════════════════════════════
            await report(PipelineStatus.PLANNING, "Planning dashboard layout...")

            plan = await planner_agent.plan_dashboard(
                profiles=profiles,
                theme=theme,
                target=target,
                user_chart_requests=user_chart_requests,
            )
            run.dashboard_plan = plan

            total_charts = sum(len(s.charts) for s in plan.sheets)
            await report(PipelineStatus.PLANNING,
                f"Dashboard plan: {plan.dashboard_title} — {len(plan.sheets)} sheets, {total_charts} charts")

            # ════════════════════════════════════════
            # STEP 5: GENERATE SQL QUERIES
            # ════════════════════════════════════════
            await report(PipelineStatus.GENERATING_SQL, "Generating SQL queries...")

            # Exploration queries
            for profile in profiles:
                exploration = await sql_agent.generate_exploration_queries(profile)
                run.sql_artifacts.extend(exploration)

            # Chart-specific queries
            chart_queries = await sql_agent.generate_queries_for_plan(profiles, plan)
            run.sql_artifacts.extend(chart_queries)

            success_count = sum(1 for a in run.sql_artifacts if a.success)
            await report(PipelineStatus.GENERATING_SQL,
                f"Executed {len(run.sql_artifacts)} queries ({success_count} successful)")

            # ════════════════════════════════════════
            # STEP 6: GENERATE DASHBOARD EXPORTS
            # ════════════════════════════════════════
            await report(PipelineStatus.GENERATING_DASHBOARDS, "Generating dashboard exports...")

            # Generate Standalone Interactive HTML Dashboard
            dash_res = dashboard_agent.generate_dashboard(profiles, plan)
            run.dashboard_html = dash_res.get("dashboard_html", "")
            run.sheet_kpis = dash_res.get("sheet_kpis", {})
            run.sheet_figures = dash_res.get("sheet_figures", {})

            # Generate Python preprocessing script
            preprocess_script = codegen_agent.generate_preprocessing_script(profiles, all_logs)
            run.python_artifacts.append(preprocess_script)

            # Generate SQL script
            sql_script = codegen_agent.generate_sql_script(profiles, run.sql_artifacts, plan)
            run.python_artifacts.append(sql_script)

            # Power BI
            if target in (OutputTarget.POWERBI, OutputTarget.BOTH):
                pbi_package = powerbi_agent.generate_package(profiles, plan)
                run.powerbi_package = pbi_package
                await report(PipelineStatus.GENERATING_DASHBOARDS,
                    f"Power BI package: {len(pbi_package.dax_measures)} DAX measures, {len(pbi_package.power_query_steps)} M steps + TMSL Model")

            # Tableau
            if target in (OutputTarget.TABLEAU, OutputTarget.BOTH):
                tab_package = tableau_agent.generate_package(profiles, plan)
                run.tableau_package = tab_package
                await report(PipelineStatus.GENERATING_DASHBOARDS,
                    f"Tableau package: {len(tab_package.calculated_fields)} calculated fields + replication blueprint")

            # ════════════════════════════════════════
            # STEP 7: PACKAGE OUTPUT
            # ════════════════════════════════════════
            await report(PipelineStatus.PACKAGING, "Packaging output...")

            output_folder = packaging_agent.create_output_folder(run)
            run.output_folder = output_folder

            await report(PipelineStatus.PACKAGING, f"Output saved to: {output_folder}")

            # ════════════════════════════════════════
            # DONE
            # ════════════════════════════════════════
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.now()
            self._add_event(run, "completed", "Pipeline completed successfully! 🎉")

        except Exception as e:
            import traceback
            traceback.print_exc()
            run.status = PipelineStatus.FAILED
            run.error = traceback.format_exc()
            run.completed_at = datetime.now()
            self._add_event(run, "failed", f"Pipeline failed: {str(e)}")

        return run

    def _add_event(self, run: PipelineRun, step: str, message: str) -> PipelineEvent:
        """Add an event to the pipeline run."""
        event = PipelineEvent(
            step=step,
            status="success" if step not in ("failed",) else "failure",
            message=message,
        )
        run.events.append(event)
        return event


# Singleton
orchestrator = PipelineOrchestrator()
