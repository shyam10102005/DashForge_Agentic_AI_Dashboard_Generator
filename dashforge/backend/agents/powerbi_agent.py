"""
DashForge - Power BI Export Agent
Generates DAX measures, Power Query M scripts, Python connector scripts,
Tabular Model (model.bim), and complete Power BI project bundles.
"""
import json
from pathlib import Path
from typing import Optional

from backend.models import (
    DatasetProfile, DashboardPlan, SheetPlan, ChartSpec,
    PowerBIPackage, DAXMeasure, PowerQueryStep
)


class PowerBIExportAgent:
    """Generates all Power BI assets from dashboard plans and dataset profiles."""

    # Theme color palettes
    THEME_PALETTES = {
        "corporate_blue": {
            "name": "Corporate Blue",
            "background": "#F8F9FA",
            "foreground": "#2C3E50",
            "dataColors": ["#2196F3", "#1976D2", "#0D47A1", "#42A5F5", "#90CAF9", "#64B5F6"],
            "accent1": "#2196F3",
            "accent2": "#FF9800",
        },
        "modern_dark": {
            "name": "Modern Dark",
            "background": "#1A1A2E",
            "foreground": "#E0E0E0",
            "dataColors": ["#00D4FF", "#7C4DFF", "#FF6B6B", "#4ECDC4", "#FFE66D", "#A8E6CF"],
            "accent1": "#00D4FF",
            "accent2": "#7C4DFF",
        },
        "vibrant": {
            "name": "Vibrant",
            "background": "#FFFFFF",
            "foreground": "#333333",
            "dataColors": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40"],
            "accent1": "#FF6384",
            "accent2": "#36A2EB",
        },
        "minimal_light": {
            "name": "Minimal Light",
            "background": "#FAFAFA",
            "foreground": "#424242",
            "dataColors": ["#546E7A", "#78909C", "#90A4AE", "#B0BEC5", "#37474F", "#455A64"],
            "accent1": "#546E7A",
            "accent2": "#78909C",
        },
        "earth_tones": {
            "name": "Earth Tones",
            "background": "#FFF8E1",
            "foreground": "#3E2723",
            "dataColors": ["#795548", "#8D6E63", "#A1887F", "#D7CCC8", "#4E342E", "#6D4C41"],
            "accent1": "#795548",
            "accent2": "#FF8F00",
        },
    }

    def generate_package(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
    ) -> PowerBIPackage:
        """Generate a complete Power BI package with all assets."""
        dax_measures = self._generate_dax_measures(profiles, plan)
        pq_steps = self._generate_power_query(profiles)
        model_bim = self._generate_model_bim(profiles, plan, dax_measures)
        py_script = self._generate_python_connector(profiles)
        dax_script = self._format_dax_script(dax_measures, plan)
        m_script = self._format_m_script(pq_steps)
        title_slug = plan.dashboard_title.replace(" ", "_") if plan else "Dashboard"
        rep_guide = self._generate_replication_guide(profiles, plan, dax_measures)

        return PowerBIPackage(
            dax_measures=dax_measures,
            power_query_steps=pq_steps,
            model_bim_json=model_bim,
            python_connector_script=py_script,
            dax_script=dax_script,
            m_script=m_script,
            replication_guide=rep_guide,
            pbit_bytes=None,
            pbix_filename=f"{title_slug}.pbit",
        )

    def _generate_replication_guide(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
        measures: list[DAXMeasure]
    ) -> str:
        """Generate a complete step-by-step Power BI Replication Guide."""
        lines = [
            f"# 🟡 Power BI Dashboard Replication Blueprint",
            f"**Dashboard:** {plan.dashboard_title}",
            f"**Subtitle:** {plan.subtitle or 'Executive Analytics'}",
            "",
            "This guide walks you through replicating this exact dashboard in **Power BI Desktop** on your computer.",
            "",
            "---",
            "",
            "## 🚀 Method 1: Python Connector (1-Click Import)",
            "1. Open **Power BI Desktop**.",
            "2. Click **Get Data** ➔ **Other** ➔ **Python script** ➔ **Connect**.",
            "3. Open `load_powerbi.py` from the downloaded bundle, copy all code, and paste it into the dialog.",
            "4. Click **OK**, select the tables, and click **Load**.",
            "",
            "---",
            "",
            "## 🛠️ Method 2: Standard CSV Import with Power Query (M)",
            "1. Open **Power BI Desktop**.",
            "2. Click **Get Data** ➔ **Text/CSV** ➔ Select your CSV file.",
            "3. Click **Transform Data** to open Power Query Editor.",
            "4. Click **Home** ➔ **Advanced Editor**.",
            "5. Replace contents with `transform.m` and click **Done**.",
            "6. Click **Close & Apply**.",
            "",
            "---",
            "",
            "## 📐 Step 2: Add Calculated DAX Measures",
            "In Power BI Desktop, navigate to the **Modeling** tab ➔ click **New Measure** and paste each measure below:",
            "",
        ]

        for m in measures:
            lines.extend([
                f"### `{m.name}`",
                "```dax",
                f"{m.name} = {m.expression}",
                "```",
                f"*Format String:* `{m.format_string}`" if m.format_string else "",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## 📊 Step 3: Build Sheets & Visuals",
            "Create a tab at the bottom for each sheet below, and add the visuals matching the grid:",
            "",
        ])

        for s_idx, sheet in enumerate(plan.sheets, 1):
            lines.extend([
                f"### Page {s_idx}: {sheet.title}",
                f"*Target Audience:* {sheet.target_audience} • *Description:* {sheet.description}",
                "",
                "| Visual Title | Visual Type in Power BI | X-Axis / Category | Y-Axis / Values | Aggregation |",
                "|:---|:---|:---|:---|:---|",
            ])
            for chart in sheet.charts:
                vtype = chart.chart_type.value.upper() if hasattr(chart.chart_type, 'value') else str(chart.chart_type).upper()
                x = chart.x_column or chart.dimension or "-"
                y = ", ".join(chart.y_columns) if chart.y_columns else (chart.measure or "-")
                agg = chart.aggregation or "SUM"
                lines.append(f"| **{chart.title}** | `{vtype}` | `{x}` | `{y}` | `{agg}` |")
            lines.append("")

        return "\n".join(lines)

    def _generate_dax_measures(
        self, profiles: list[DatasetProfile], plan: DashboardPlan
    ) -> list[DAXMeasure]:
        """Generate DAX measures based on profiles and dashboard plan."""
        measures = []

        for profile in profiles:
            table = profile.table_name

            # Row count
            measures.append(DAXMeasure(
                name=f"Total Records ({table})",
                expression=f"COUNTROWS('{table}')",
                format_string="#,##0",
                description=f"Total number of records in {table}",
            ))

            # Numeric column aggregations
            for nc in profile.numeric_columns:
                clean = nc.replace("'", "")
                measures.extend([
                    DAXMeasure(
                        name=f"Total {clean}",
                        expression=f"SUM('{table}'[{clean}])",
                        format_string="#,##0.00",
                        description=f"Sum of {clean}",
                    ),
                    DAXMeasure(
                        name=f"Avg {clean}",
                        expression=f"AVERAGE('{table}'[{clean}])",
                        format_string="#,##0.00",
                        description=f"Average of {clean}",
                    ),
                    DAXMeasure(
                        name=f"Min {clean}",
                        expression=f"MIN('{table}'[{clean}])",
                        format_string="#,##0.00",
                    ),
                    DAXMeasure(
                        name=f"Max {clean}",
                        expression=f"MAX('{table}'[{clean}])",
                        format_string="#,##0.00",
                    ),
                ])

            # Revenue / Profit margin measures
            revenue_cols = [c for c in profile.columns if c.semantic_role == "revenue"]
            profit_cols = [c for c in profile.columns if c.semantic_role == "profit"]

            if revenue_cols and profit_cols:
                rev = revenue_cols[0].name
                prof = profit_cols[0].name
                measures.append(DAXMeasure(
                    name="Profit Margin %",
                    expression=f"DIVIDE([Total {prof}], [Total {rev}], 0)",
                    format_string="0.00%",
                    description="Profit margin as percentage of revenue",
                ))

            # Time intelligence measures
            if profile.date_columns and revenue_cols:
                date_col = profile.date_columns[0]
                rev = revenue_cols[0].name

                measures.extend([
                    DAXMeasure(
                        name=f"{rev} YTD",
                        expression=f"TOTALYTD([Total {rev}], '{table}'[{date_col}])",
                        format_string="#,##0.00",
                    ),
                    DAXMeasure(
                        name=f"{rev} Prior Month",
                        expression=f"CALCULATE([Total {rev}], PREVIOUSMONTH('{table}'[{date_col}]))",
                        format_string="#,##0.00",
                    ),
                    DAXMeasure(
                        name=f"{rev} MoM Growth %",
                        expression=f"VAR CurrentVal = [Total {rev}]\nVAR PriorVal = [{rev} Prior Month]\nRETURN DIVIDE(CurrentVal - PriorVal, PriorVal, 0)",
                        format_string="0.00%",
                    ),
                ])

        # Deduplicate measure names across the model
        unique_measures = []
        seen_names = set()
        for m in measures:
            base_name = m.name
            unique_name = base_name
            counter = 1
            while unique_name in seen_names:
                unique_name = f"{base_name} ({counter})"
                counter += 1
            m.name = unique_name
            seen_names.add(unique_name)
            unique_measures.append(m)

        return unique_measures

    def _generate_power_query(self, profiles: list[DatasetProfile]) -> list[PowerQueryStep]:
        """Generate Power Query M steps for data transformation."""
        steps = []

        for profile in profiles:
            # Source step
            steps.append(PowerQueryStep(
                step_name=f"Load_{profile.table_name}",
                m_code=self._generate_m_code_for_profile(profile),
                description=f"Load and type-cast {profile.filename}",
            ))

        return steps

    def _generate_m_code_for_profile(self, profile: DatasetProfile, file_path: str = None) -> str:
        """Generate Power Query M code for a single dataset.
        
        Args:
            profile: Dataset profile with column info.
            file_path: Optional absolute file path. If None, uses profile.filename.
        """
        type_mappings = []
        for col in profile.columns:
            clean_name = col.name.replace('"', '""')
            if col.is_numeric:
                if "int" in col.dtype.lower():
                    m_type = "Int64.Type"
                else:
                    m_type = "type number"
            elif col.is_date:
                m_type = "type date"
            else:
                m_type = "type text"
            type_mappings.append(f'{{"{clean_name}", {m_type}}}')

        mappings_str = ",\n        ".join(type_mappings)

        # Use absolute path if provided, otherwise use filename
        source_path = file_path if file_path else profile.filename
        # Escape backslashes for M code
        source_path_escaped = source_path.replace("\\", "\\\\")

        return f"""// DashForge Power Query - {profile.filename}
// Paste into Power BI: Home → Transform Data → Advanced Editor
let
    Source = Csv.Document(
        File.Contents("{source_path_escaped}"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(
        #"Promoted Headers",
        {{
        {mappings_str}
        }}
    )
in
    #"Changed Type"
"""

    def _resolve_file_path(self, profile: DatasetProfile) -> str:
        """Resolve the absolute file path for a dataset profile."""
        from backend.config import settings
        candidate = Path(settings.storage.upload_dir) / profile.filename
        if candidate.exists():
            return str(candidate.resolve())
        # Try to find the file in common locations
        for search_dir in [settings.storage.upload_dir, settings.storage.output_dir]:
            for f in Path(search_dir).rglob(profile.filename):
                return str(f.resolve())
        # Fallback: return the upload dir path (Power BI will prompt user)
        return str(candidate)

    def _generate_model_bim(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
        measures: list[DAXMeasure]
    ) -> dict:
        """Generate Tabular Model Schema (model.bim) JSON."""
        tables = []
        assigned_measure_names = set()

        for profile in profiles:
            columns_def = []
            for col in profile.columns:
                data_type = "string"
                if col.is_numeric:
                    data_type = "int64" if "int" in col.dtype.lower() else "double"
                elif col.is_date:
                    data_type = "dateTime"

                columns_def.append({
                    "name": col.name,
                    "dataType": data_type,
                    "sourceColumn": col.name,
                    "summarizeBy": "sum" if col.is_numeric else "none",
                })

            # Assign measures that reference this table (strictly once)
            table_measures = []
            for m in measures:
                if m.name in assigned_measure_names:
                    continue
                table_ref = f"'{profile.table_name}'"
                if table_ref in m.expression or profile.table_name in m.expression or f"({profile.table_name})" in m.name:
                    table_measures.append({
                        "name": m.name,
                        "expression": m.expression,
                        "formatString": m.format_string,
                        "description": m.description,
                    })
                    assigned_measure_names.add(m.name)

            # Generate M expression for partition using ABSOLUTE file path
            abs_path = self._resolve_file_path(profile)
            m_code = self._generate_m_code_for_profile(profile, file_path=abs_path)
            m_lines = [line.strip() for line in m_code.split("\n") if line.strip() and not line.strip().startswith("//")]

            tables.append({
                "name": profile.table_name,
                "columns": columns_def,
                "partitions": [
                    {
                        "name": profile.table_name,
                        "mode": "import",
                        "source": {
                            "type": "m",
                            "expression": m_lines,
                        },
                    }
                ],
                "measures": table_measures,
            })

        # Sweep any remaining unassigned measures to the first table
        if tables:
            for m in measures:
                if m.name not in assigned_measure_names:
                    tables[0]["measures"].append({
                        "name": m.name,
                        "expression": m.expression,
                        "formatString": m.format_string,
                        "description": m.description,
                    })
                    assigned_measure_names.add(m.name)

        title_slug = plan.dashboard_title.replace(" ", "_") if plan else "Dashboard"
        return {
            "name": f"DashForge_{title_slug}",
            "compatibilityLevel": 1550,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": tables,
            },
        }

    def _generate_python_connector(self, profiles: list[DatasetProfile]) -> str:
        """Generate Python connector script for Power BI → Get Data → Python."""
        parts = [
            "# =======================================================",
            "# DashForge - Power BI Python Data Connector",
            "# Usage: Power BI Desktop → Get Data → Python script",
            "# =======================================================",
            "import pandas as pd",
            "import numpy as np",
            "",
        ]

        for i, profile in enumerate(profiles):
            var_name = f"df_{profile.table_name}"
            abs_path = self._resolve_file_path(profile)
            parts.extend([
                f"# --- Dataset: {profile.filename} ---",
                f"file_path_{i} = r'{abs_path}'",
                f"{var_name} = pd.read_csv(file_path_{i})",
                "",
            ])

            # Numeric type casting
            if profile.numeric_columns:
                parts.append(f"# Ensure numeric types")
                for nc in profile.numeric_columns:
                    parts.append(f"{var_name}['{nc}'] = pd.to_numeric({var_name}['{nc}'], errors='coerce')")
                parts.append("")

            # Date parsing
            if profile.date_columns:
                parts.append(f"# Parse date columns")
                for dc in profile.date_columns:
                    parts.append(f"{var_name}['{dc}'] = pd.to_datetime({var_name}['{dc}'], errors='coerce')")
                parts.append("")

        return "\n".join(parts)

    def _format_dax_script(self, measures: list[DAXMeasure], plan: DashboardPlan) -> str:
        """Format all DAX measures as a single pasteable script."""
        lines = [
            "// =====================================================================",
            f"// DASHFORGE - AUTO-GENERATED DAX MEASURES",
            f"// Dashboard: {plan.dashboard_title}",
            "// =====================================================================",
            "",
        ]

        for m in measures:
            lines.extend([
                f"// {m.description}" if m.description else f"// Measure: {m.name}",
                f"{m.name} =",
                f"{m.expression}",
                "",
            ])

        return "\n".join(lines)

    def _format_m_script(self, steps: list[PowerQueryStep]) -> str:
        """Format all Power Query steps into a single script."""
        parts = []
        for step in steps:
            parts.append(f"// === {step.description} ===")
            parts.append(step.m_code)
            parts.append("")

        return "\n".join(parts)

    def generate_theme_json(self, plan: DashboardPlan) -> str:
        """Generate a Power BI theme JSON file."""
        theme_key = plan.theme.value if hasattr(plan.theme, 'value') else "corporate_blue"
        palette = self.THEME_PALETTES.get(theme_key, self.THEME_PALETTES["corporate_blue"])

        theme = {
            "name": palette["name"],
            "dataColors": palette["dataColors"],
            "background": palette["background"],
            "foreground": palette["foreground"],
            "tableAccent": palette["accent1"],
            "visualStyles": {
                "*": {
                    "*": {
                        "background": [{"color": {"solid": {"color": palette["background"]}}}]
                    }
                }
            }
        }
        return json.dumps(theme, indent=2)

    def _compile_pbit(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
        model_bim: dict,
    ) -> bytes:
        """Compile a native Power BI Template (.pbit) package.
        
        Uses the classic PBIT format with Report/Layout (not Fabric PBIR).
        Power BI Desktop will execute the M queries to load data on open.
        """
        import zipfile
        import io

        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
            # 1. Version
            z.writestr("Version", "1.32".encode("utf-16"))

            # 2. Settings
            settings_data = {
                "Version": 4,
                "ReportSettings": {},
                "QueriesSettings": {
                    "TypeDetectionEnabled": True,
                    "RelationshipImportEnabled": True,
                    "Version": "2.129.255.0",
                },
            }
            z.writestr("Settings", json.dumps(settings_data).encode("utf-16"))

            # 3. Metadata
            meta_data = {
                "Version": 5,
                "AutoCreatedRelationships": [],
                "CreatedFrom": "DashForge",
                "CreatedFromRelease": "2026.10",
            }
            z.writestr("Metadata", json.dumps(meta_data).encode("utf-16"))

            # 4. DiagramLayout
            diagram_data = {"version": "1.1.0", "diagrams": []}
            z.writestr("DiagramLayout", json.dumps(diagram_data).encode("utf-16"))

            # 5. [Content_Types].xml
            content_types_xml = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                '  <Default Extension="json" ContentType="application/json" />\n'
                '  <Default Extension="xml" ContentType="application/xml" />\n'
                '  <Override PartName="/DataModelSchema" ContentType="" />\n'
                '  <Override PartName="/Settings" ContentType="" />\n'
                '  <Override PartName="/Metadata" ContentType="" />\n'
                '  <Override PartName="/Version" ContentType="" />\n'
                '  <Override PartName="/DiagramLayout" ContentType="" />\n'
                '  <Override PartName="/Report/Layout" ContentType="" />\n'
                '</Types>'
            )
            z.writestr("[Content_Types].xml", content_types_xml.encode("utf-8"))

            # 6. DataModelSchema (TMSL model with M scripts and DAX measures)
            z.writestr("DataModelSchema", json.dumps(model_bim, indent=2).encode("utf-16"))

            # 7. Report/Layout (CLASSIC Power BI report layout with themeCollection and resourcePackages)
            sections = []
            if plan and plan.sheets:
                for idx, sheet in enumerate(plan.sheets):
                    section_name = f"ReportSection{idx + 1}"
                    section_config = {
                        "name": section_name,
                        "layouts": [{"id": 0, "position": {
                            "x": 0, "y": 0, "z": 0,
                            "width": 1280, "height": 720
                        }}],
                    }
                    sections.append({
                        "id": idx,
                        "name": section_name,
                        "displayName": sheet.title,
                        "filters": "[]",
                        "ordinal": idx,
                        "visualContainers": [],
                        "config": json.dumps(section_config),
                        "width": 1280,
                        "height": 720,
                    })

            # Fallback: at least one blank page
            if not sections:
                sections.append({
                    "id": 0,
                    "name": "ReportSection1",
                    "displayName": "Overview",
                    "filters": "[]",
                    "ordinal": 0,
                    "visualContainers": [],
                    "config": json.dumps({
                        "name": "ReportSection1",
                        "layouts": [{"id": 0, "position": {
                            "x": 0, "y": 0, "z": 0,
                            "width": 1280, "height": 720
                        }}],
                    }),
                    "width": 1280,
                    "height": 720,
                })

            report_config = {
                "version": "5.50",
                "themeCollection": {
                    "baseTheme": {
                        "name": "CY24SU06",
                        "version": "5.50",
                        "type": 2
                    }
                },
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "settings": {
                    "useNewFilterPaneExperience": True,
                    "allowChangeFilterTypes": True,
                },
            }

            layout_data = {
                "id": 0,
                "resourcePackages": [
                    {
                        "resourcePackage": {
                            "name": "SharedResources",
                            "type": 2,
                            "items": [],
                            "disabled": False
                        }
                    }
                ],
                "sections": sections,
                "config": json.dumps(report_config),
                "layoutOptimization": 0,
            }
            z.writestr("Report/Layout", json.dumps(layout_data).encode("utf-16"))

        return bio.getvalue()


# Singleton
powerbi_agent = PowerBIExportAgent()

