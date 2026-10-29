"""
DashForge - Tableau Export Agent
Generates calculated fields, schema metadata, and step-by-step Tableau replication blueprints.
Provides everything needed to build and replicate the dashboard in Tableau Desktop or Tableau Public.
"""
import json
from typing import Optional

from backend.models import (
    DatasetProfile, DashboardPlan, SheetPlan, ChartSpec,
    TableauPackage, ChartType
)


class TableauExportAgent:
    """Generates Tableau calculated fields, schema guides, and replication blueprints."""

    MARK_TYPE_MAP = {
        ChartType.BAR: "Bar",
        ChartType.STACKED_BAR: "Bar",
        ChartType.LINE: "Line",
        ChartType.AREA: "Area",
        ChartType.PIE: "Pie",
        ChartType.DONUT: "Pie",
        ChartType.SCATTER: "Circle",
        ChartType.HISTOGRAM: "Bar",
        ChartType.BOX: "Bar",
        ChartType.HEATMAP: "Square",
        ChartType.TREEMAP: "Square",
        ChartType.WATERFALL: "Gantt Bar",
        ChartType.COMBO: "Automatic",
        ChartType.KPI_CARD: "Text",
        ChartType.TABLE: "Text",
        ChartType.MAP: "Map",
    }

    THEME_PALETTES = {
        "corporate_blue": ["#2196F3", "#1976D2", "#0D47A1", "#42A5F5", "#90CAF9", "#64B5F6",
                           "#BBDEFB", "#1565C0", "#1E88E5", "#2962FF"],
        "modern_dark": ["#00D4FF", "#7C4DFF", "#FF6B6B", "#4ECDC4", "#FFE66D", "#A8E6CF",
                        "#B388FF", "#FF8A80", "#84FFFF", "#EA80FC"],
        "vibrant": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40",
                    "#C9CBCF", "#7BC225", "#FF6B6B", "#45B7D1"],
        "minimal_light": ["#546E7A", "#78909C", "#90A4AE", "#B0BEC5", "#37474F", "#455A64",
                          "#607D8B", "#CFD8DC", "#263238", "#ECEFF1"],
        "earth_tones": ["#795548", "#8D6E63", "#A1887F", "#D7CCC8", "#4E342E", "#6D4C41",
                        "#BCAAA4", "#3E2723", "#5D4037", "#EFEBE9"],
    }

    def generate_package(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
    ) -> TableauPackage:
        """Generate a complete Tableau replication package with calculated fields and guides."""
        calc_fields = self._generate_calculated_fields(profiles)
        calc_script = self._format_calculated_fields_text(calc_fields, plan)
        datasource_info = self._generate_datasource_info(profiles)
        rep_guide = self._generate_replication_guide(profiles, plan, calc_fields)

        return TableauPackage(
            calculated_fields=calc_fields,
            calculated_fields_script=calc_script,
            datasource_info=datasource_info,
            replication_guide=rep_guide,
            twb_xml="",
            tds_xml="",
        )

    def _generate_calculated_fields(self, profiles: list[DatasetProfile]) -> list[dict]:
        """Generate Tableau calculated field definitions."""
        fields = [
            {
                "name": "Number of Records",
                "formula": "1",
                "type": "quantitative",
                "description": "Total record count helper"
            }
        ]

        for profile in profiles:
            table = profile.table_name

            # Aggregations for numeric columns
            for nc in profile.numeric_columns:
                clean_nc = nc.replace("'", "")
                fields.extend([
                    {
                        "name": f"Total {clean_nc}",
                        "formula": f"SUM([{clean_nc}])",
                        "type": "quantitative",
                        "description": f"Sum of {clean_nc} in {table}"
                    },
                    {
                        "name": f"Avg {clean_nc}",
                        "formula": f"AVG([{clean_nc}])",
                        "type": "quantitative",
                        "description": f"Average of {clean_nc} in {table}"
                    }
                ])

            # Profit margin if both revenue and profit exist
            rev_cols = [c for c in profile.columns if c.semantic_role == "revenue" or "sale" in c.name.lower() or "revenue" in c.name.lower()]
            prof_cols = [c for c in profile.columns if c.semantic_role == "profit" or "profit" in c.name.lower()]
            if rev_cols and prof_cols:
                fields.append({
                    "name": "Profit Margin %",
                    "formula": f"SUM([{prof_cols[0].name}]) / SUM([{rev_cols[0].name}])",
                    "type": "quantitative",
                    "description": "Profit Margin ratio"
                })

            # Year-over-Year growth
            if profile.date_columns and rev_cols:
                rname = rev_cols[0].name
                fields.append({
                    "name": f"{rname} YoY Growth %",
                    "formula": f"(ZN(SUM([{rname}])) - LOOKUP(ZN(SUM([{rname}])), -1)) / ABS(LOOKUP(ZN(SUM([{rname}])), -1))",
                    "type": "quantitative",
                    "description": f"Year-over-Year percentage growth for {rname}"
                })

        return fields

    def _format_calculated_fields_text(self, fields: list[dict], plan: DashboardPlan) -> str:
        """Format calculated fields as a pasteable text script."""
        lines = [
            "// =====================================================================",
            f"// DASHFORGE - TABLEAU CALCULATED FIELDS",
            f"// Dashboard: {plan.dashboard_title}",
            "// =====================================================================",
            "// Copy and paste each formula below into Tableau: Analysis ➔ Create Calculated Field",
            "",
        ]

        for f in fields:
            lines.extend([
                f"// Name: {f['name']}",
                f"// Description: {f.get('description', '')}",
                f"// Formula:",
                f"{f['formula']}",
                "",
            ])

        return "\n".join(lines)

    def _generate_datasource_info(self, profiles: list[DatasetProfile]) -> dict:
        """Generate schema definition for Tableau."""
        ds_info = {}
        for p in profiles:
            cols = []
            for c in p.columns:
                cols.append({
                    "name": c.name,
                    "datatype": self._get_tableau_datatype(c),
                    "role": "measure" if c.is_numeric else "dimension",
                    "type": "quantitative" if c.is_numeric else ("ordinal" if c.is_date else "nominal"),
                })
            ds_info[p.table_name] = {
                "filename": p.filename,
                "row_count": p.row_count,
                "columns": cols
            }
        return ds_info

    def _generate_replication_guide(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan,
        calc_fields: list[dict]
    ) -> str:
        """Generate a complete step-by-step Tableau Replication Guide."""
        lines = [
            f"# 🟠 Tableau Dashboard Replication Blueprint",
            f"**Dashboard:** {plan.dashboard_title}",
            f"**Subtitle:** {plan.subtitle or 'Executive Analytics'}",
            "",
            "This guide walks you through replicating this exact dashboard in **Tableau Desktop** or **Tableau Public** on your computer.",
            "",
            "---",
            "",
            "## 🔌 Step 1: Connect to Dataset",
            "1. Open **Tableau Desktop** or **Tableau Public**.",
            "2. Under **Connect** (left panel), click **Text file**.",
            "3. Select your cleaned CSV file (found in the `data/` folder of the downloaded project bundle).",
            "4. Tableau will load the data into the Data Source view. Click **Sheet 1** at the bottom.",
            "",
            "---",
            "",
            "## 📐 Step 2: Create Calculated Fields",
            "In Tableau, go to the top menu: **Analysis** ➔ **Create Calculated Field** (or right-click empty space in the Data pane ➔ Create Calculated Field).",
            "Add each calculated field below:",
            "",
        ]

        for cf in calc_fields:
            lines.extend([
                f"### Field: `{cf['name']}`",
                f"- **Formula:** `{cf['formula']}`",
                f"- **Role:** Quantitative Measure",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## 📊 Step 3: Build Each Worksheet",
            "Create a new worksheet tab for each chart in your dashboard plan:",
            "",
        ])

        for s_idx, sheet in enumerate(plan.sheets, 1):
            lines.extend([
                f"### Sheet Group {s_idx}: {sheet.title}",
                f"*Target Audience:* {sheet.target_audience}",
                "",
                "| Chart Title | Tableau Mark Type | Columns Shelf (Pill) | Rows Shelf (Pill) | Color / Detail |",
                "|:---|:---|:---|:---|:---|",
            ])
            for chart in sheet.charts:
                mark = self.MARK_TYPE_MAP.get(chart.chart_type, "Automatic")
                x = chart.x_column or chart.dimension or "-"
                y = ", ".join(f"SUM([{c}])" for c in chart.y_columns) if chart.y_columns else (f"SUM([{chart.measure}])" if chart.measure else "-")
                color = f"[{chart.color_column}]" if chart.color_column else "-"
                lines.append(f"| **{chart.title}** | `{mark}` | `[{x}]` | `{y}` | `{color}` |")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 🎨 Step 4: Assemble Dashboard Canvas",
            "1. Click the **New Dashboard** icon at the bottom of Tableau.",
            f"2. Rename the dashboard tab to **`{plan.dashboard_title}`**.",
            "3. Under **Size** (left panel), select **Automatic** or Fixed (1920 x 1080).",
            "4. Drag each worksheet created in Step 3 onto the dashboard canvas.",
            "5. Arrange the cards into a responsive 2x2 or 3x2 grid layout.",
            "6. Click **Dashboard** ➔ **Show Title** to display the executive title banner.",
            "",
        ])

        return "\n".join(lines)

    @staticmethod
    def _get_tableau_datatype(col) -> str:
        """Map column profile to Tableau data type."""
        if col.is_numeric:
            if "int" in col.dtype.lower():
                return "integer"
            return "real"
        elif col.is_date:
            return "datetime"
        return "string"


# Singleton
tableau_agent = TableauExportAgent()
