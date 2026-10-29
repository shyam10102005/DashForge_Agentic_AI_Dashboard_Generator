"""
DashForge - Dashboard Planner Agent
Uses the LLM to analyze dataset profiles and suggest dashboard sheets,
chart types, headings, and layouts for Power BI / Tableau.
"""
import json
from typing import Optional

from backend.llm_service import llm
from backend.models import (
    DatasetProfile, DashboardPlan, SheetPlan, ChartSpec,
    ChartType, ThemePreset, OutputTarget
)


class DashboardPlannerAgent:
    """Plans dashboard structure: sheets, charts, headings based on data profiles."""

    PLANNING_PROMPT = """You are an expert BI dashboard architect. Analyze the following dataset profiles
and create a comprehensive dashboard plan.

DATASETS:
{datasets_info}

USER PREFERENCES:
- Dashboard theme: {theme}
- Target platform: {target}
- User-specified charts (if any): {user_charts}

Create a dashboard plan in JSON format:
{{
    "dashboard_title": "A compelling, professional dashboard title",
    "sheets": [
        {{
            "title": "Sheet/Page Title (e.g., 'Sales Overview', 'Regional Analysis')",
            "description": "What this sheet shows",
            "dataset_id": "which dataset this sheet uses",
            "table_name": "table name from the dataset",
            "charts": [
                {{
                    "chart_type": "bar|stacked_bar|line|area|pie|donut|scatter|histogram|box|heatmap|treemap|waterfall|combo|kpi_card|table",
                    "title": "Chart title",
                    "description": "What this chart visualizes",
                    "x_column": "column name for x-axis (or category)",
                    "y_columns": ["column1", "column2"],
                    "color_column": "optional column for color/legend",
                    "aggregation": "SUM|COUNT|AVG|MIN|MAX",
                    "sort_by": "optional sort column",
                    "top_n": null
                }}
            ]
        }}
    ]
}}

RULES:
1. Create 2-5 sheets depending on data complexity.
2. Each sheet should have 3-6 charts/visuals.
3. Always include at least one KPI card sheet with key metrics.
4. Use chart types that best represent the data relationships.
5. Only reference columns that exist in the dataset profiles.
6. Group related analyses into themed sheets.
7. Include at least one trend/time-series chart if date columns exist.
8. Include at least one comparison chart for categorical columns.
9. Be creative with dashboard titles and sheet names - make them professional.
10. Match chart types to the data: use bar for categories, line for time, pie for proportions, scatter for relationships."""

    async def plan_dashboard(
        self,
        profiles: list[DatasetProfile],
        theme: ThemePreset = ThemePreset.CORPORATE_BLUE,
        target: OutputTarget = OutputTarget.BOTH,
        user_chart_requests: list[str] = None,
    ) -> DashboardPlan:
        """Generate a dashboard plan using LLM analysis of dataset profiles."""

        # Build dataset info string
        datasets_info = self._build_datasets_info(profiles)
        user_charts = ", ".join(user_chart_requests) if user_chart_requests else "Auto-detect best charts"

        prompt = self.PLANNING_PROMPT.format(
            datasets_info=datasets_info,
            theme=theme.value,
            target=target.value,
            user_charts=user_charts,
        )

        result = await llm.generate_json(
            prompt=prompt,
            system_prompt="You are a senior BI dashboard architect. Respond ONLY in valid JSON.",
            temperature=0.2,
        )

        if "error" in result:
            # Fallback: generate a rule-based plan
            return self._fallback_plan(profiles, theme, target)

        return self._parse_plan(result, profiles, theme, target)

    def _build_datasets_info(self, profiles: list[DatasetProfile]) -> str:
        """Build a text description of all datasets for the LLM prompt."""
        parts = []
        for p in profiles:
            cols_info = []
            for c in p.columns:
                role = f" [{c.semantic_role}]" if c.semantic_role else ""
                type_tag = "NUMERIC" if c.is_numeric else ("DATE" if c.is_date else ("CATEGORICAL" if c.is_categorical else "TEXT"))
                cols_info.append(f"    - {c.name} ({type_tag}, {c.dtype}){role}: {c.unique_count} unique, {c.null_pct}% null")

            parts.append(f"""
Dataset: {p.filename}
  Table: {p.table_name}
  Dataset ID: {p.dataset_id}
  Rows: {p.row_count:,} | Columns: {p.column_count}
  Quality Score: {p.data_quality_score}%
  Duplicates: {p.duplicate_row_count}
  Numeric Columns: {', '.join(p.numeric_columns)}
  Date Columns: {', '.join(p.date_columns)}
  Categorical Columns: {', '.join(p.categorical_columns)}
  Column Details:
{chr(10).join(cols_info)}
""")
        return "\n---\n".join(parts)

    def _parse_plan(
        self,
        plan_data: dict,
        profiles: list[DatasetProfile],
        theme: ThemePreset,
        target: OutputTarget
    ) -> DashboardPlan:
        """Parse LLM response into a DashboardPlan."""
        sheets = []
        for sheet_data in plan_data.get("sheets", []):
            charts = []
            for chart_data in sheet_data.get("charts", []):
                chart_type_str = chart_data.get("chart_type", "bar")
                try:
                    chart_type = ChartType(chart_type_str)
                except ValueError:
                    chart_type = ChartType.BAR

                charts.append(ChartSpec(
                    chart_type=chart_type,
                    title=chart_data.get("title", "Chart"),
                    description=chart_data.get("description", ""),
                    x_column=chart_data.get("x_column"),
                    y_columns=chart_data.get("y_columns", []),
                    color_column=chart_data.get("color_column"),
                    aggregation=chart_data.get("aggregation", "SUM"),
                    sort_by=chart_data.get("sort_by"),
                    top_n=chart_data.get("top_n"),
                ))

            # Find matching dataset
            ds_id = sheet_data.get("dataset_id", profiles[0].dataset_id if profiles else "")
            tbl = sheet_data.get("table_name", "dataset")

            sheets.append(SheetPlan(
                title=sheet_data.get("title", "Sheet"),
                description=sheet_data.get("description", ""),
                dataset_id=ds_id,
                table_name=tbl,
                charts=charts,
            ))

        return DashboardPlan(
            dashboard_title=plan_data.get("dashboard_title", "Dashboard"),
            theme=theme,
            sheets=sheets,
            target=target,
        )

    def _rank_numeric_columns(self, numeric_cols: list[str]) -> list[str]:
        """Rank numeric columns by business relevance (sales/revenue/profit > quantity > cost > other)."""
        def score(c: str) -> int:
            c_lower = c.lower()
            if any(k in c_lower for k in ["sales_amount", "revenue", "total_sales", "amount"]):
                return 100
            if any(k in c_lower for k in ["profit", "net_income", "margin"]):
                return 90
            if any(k in c_lower for k in ["quantity", "volume", "units", "qty"]):
                return 80
            if any(k in c_lower for k in ["cost_amount", "cost", "unit_price", "price"]):
                return 70
            if any(k in c_lower for k in ["discount", "rating"]):
                return 40
            if any(k in c_lower for k in ["age", "year", "day"]):
                return 10
            return 30
        return sorted(numeric_cols, key=score, reverse=True)

    def _rank_categorical_columns(self, categorical_cols: list[str]) -> list[str]:
        """Rank categorical dimensions (category > region > segment > channel, filtering out IDs)."""
        def score(c: str) -> int:
            c_lower = c.lower()
            if c_lower.endswith("_id") or c_lower == "id" or c_lower.endswith("_guid") or c_lower.endswith("_key") or "transaction" in c_lower or "order_id" in c_lower or "store_id" in c_lower:
                return -100
            if any(k in c_lower for k in ["product_category", "category", "dept"]):
                return 100
            if any(k in c_lower for k in ["region", "country", "state", "city", "market"]):
                return 90
            if any(k in c_lower for k in ["customer_segment", "segment", "type"]):
                return 80
            if any(k in c_lower for k in ["sales_channel", "channel", "payment_method", "shipping_method", "status"]):
                return 70
            if any(k in c_lower for k in ["gender", "rating", "brand"]):
                return 60
            if any(k in c_lower for k in ["name", "description"]):
                return 20
            return 30
        ranked = [c for c in categorical_cols if score(c) > 0]
        return sorted(ranked, key=score, reverse=True)

    def _fallback_plan(
        self,
        profiles: list[DatasetProfile],
        theme: ThemePreset,
        target: OutputTarget
    ) -> DashboardPlan:
        """Generate a rule-based dashboard plan when LLM is unavailable."""
        sheets = []
        # Prioritize primary analytical datasets (with numbers/dates) first
        sorted_profiles = sorted(
            profiles,
            key=lambda p: (len(p.numeric_columns) > 0, len(p.date_columns) > 0, p.row_count),
            reverse=True
        )

        for profile in sorted_profiles:
            # If dataset has numeric columns: Full analytical sheets
            if profile.numeric_columns:
                ranked_nums = self._rank_numeric_columns(profile.numeric_columns)
                ranked_cats = self._rank_categorical_columns(profile.categorical_columns)

                primary_num = ranked_nums[0] if ranked_nums else profile.numeric_columns[0]
                secondary_num = ranked_nums[1] if len(ranked_nums) > 1 else primary_num
                primary_cat = ranked_cats[0] if ranked_cats else (profile.categorical_columns[0] if profile.categorical_columns else "Category")
                cat2 = ranked_cats[1] if len(ranked_cats) > 1 else primary_cat
                cat3 = ranked_cats[2] if len(ranked_cats) > 2 else cat2
                date_col = profile.date_columns[0] if profile.date_columns else None

                # Sheet 1: Executive Overview (100% Visual Charts - No duplicate KPI card boxes!)
                overview_charts = [
                    ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"{primary_num.replace('_', ' ').title()} by {primary_cat.replace('_', ' ').title()}",
                        description=f"Comparison of {primary_num} across top {primary_cat} segments",
                        x_column=primary_cat,
                        y_columns=[primary_num],
                        aggregation="SUM",
                        top_n=10,
                    ),
                    ChartSpec(
                        chart_type=ChartType.DONUT,
                        title=f"{primary_num.replace('_', ' ').title()} Share by {cat2.replace('_', ' ').title()}",
                        description=f"Proportional contribution of {cat2} to overall {primary_num}",
                        x_column=cat2,
                        y_columns=[primary_num],
                        aggregation="SUM",
                    ),
                ]

                if date_col:
                    overview_charts.append(ChartSpec(
                        chart_type=ChartType.LINE,
                        title=f"Monthly {primary_num.replace('_', ' ').title()} & {secondary_num.replace('_', ' ').title()} Trend",
                        description=f"Timeline analysis comparing {primary_num} and {secondary_num}",
                        x_column=date_col,
                        y_columns=[primary_num, secondary_num] if secondary_num != primary_num else [primary_num],
                        aggregation="SUM",
                    ))

                if cat3 and cat3 != cat2:
                    overview_charts.append(ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"{primary_num.replace('_', ' ').title()} by {cat3.replace('_', ' ').title()}",
                        description=f"Breakdown of {primary_num} by {cat3}",
                        x_column=cat3,
                        y_columns=[primary_num],
                        aggregation="SUM",
                        top_n=10,
                    ))

                if len(ranked_nums) >= 2:
                    overview_charts.append(ChartSpec(
                        chart_type=ChartType.SCATTER,
                        title=f"{primary_num.replace('_', ' ').title()} vs {secondary_num.replace('_', ' ').title()}",
                        description=f"Correlation between {primary_num} and {secondary_num}",
                        x_column=primary_num,
                        y_columns=[secondary_num],
                    ))

                sheets.append(SheetPlan(
                    title=f"{profile.table_name.replace('_', ' ').title()} - Overview",
                    description="Executive summary charts and key business distributions",
                    dataset_id=profile.dataset_id,
                    table_name=profile.table_name,
                    charts=overview_charts,
                ))

                # Sheet 2: Deep-Dive Breakdown
                breakdown_charts = []
                name_col = next((c for c in profile.categorical_columns if any(k in c.lower() for k in ["name", "product_name", "item"])), None)
                if name_col:
                    breakdown_charts.append(ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"Top 10 {name_col.replace('_', ' ').title()} by {primary_num.replace('_', ' ').title()}",
                        x_column=name_col,
                        y_columns=[primary_num],
                        aggregation="SUM",
                        top_n=10,
                    ))

                if secondary_num != primary_num and cat2:
                    breakdown_charts.append(ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"{secondary_num.replace('_', ' ').title()} by {cat2.replace('_', ' ').title()}",
                        x_column=cat2,
                        y_columns=[secondary_num],
                        aggregation="SUM",
                        top_n=12,
                    ))

                qty_col = next((c for c in ranked_nums if any(k in c.lower() for k in ["quantity", "volume", "units"])), None)
                if qty_col:
                    breakdown_charts.append(ChartSpec(
                        chart_type=ChartType.DONUT,
                        title=f"{qty_col.replace('_', ' ').title()} Distribution by {primary_cat.replace('_', ' ').title()}",
                        x_column=primary_cat,
                        y_columns=[qty_col],
                        aggregation="SUM",
                    ))

                if len(ranked_cats) >= 4:
                    cat4 = ranked_cats[3]
                    breakdown_charts.append(ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"{primary_num.replace('_', ' ').title()} by {cat4.replace('_', ' ').title()}",
                        x_column=cat4,
                        y_columns=[primary_num],
                        aggregation="SUM",
                        top_n=10,
                    ))

                if breakdown_charts:
                    sheets.append(SheetPlan(
                        title=f"{profile.table_name.replace('_', ' ').title()} - Breakdown",
                        description="Deep-dive categorical distributions and performance analysis",
                        dataset_id=profile.dataset_id,
                        table_name=profile.table_name,
                        charts=breakdown_charts,
                    ))

                # Sheet 3: Timeline & Trend Analysis
                if date_col:
                    trend_charts = [
                        ChartSpec(
                            chart_type=ChartType.LINE,
                            title=f"{primary_num.replace('_', ' ').title()} Over Time",
                            x_column=date_col,
                            y_columns=[primary_num],
                            aggregation="SUM",
                        ),
                        ChartSpec(
                            chart_type=ChartType.AREA,
                            title=f"Cumulative {secondary_num.replace('_', ' ').title()} Trend",
                            x_column=date_col,
                            y_columns=[secondary_num],
                            aggregation="SUM",
                        ),
                    ]
                    year_col = next((c for c in profile.numeric_columns if "year" in c.lower()), None)
                    if year_col:
                        trend_charts.append(ChartSpec(
                            chart_type=ChartType.BAR,
                            title=f"Annual {primary_num.replace('_', ' ').title()} by {year_col.replace('_', ' ').title()}",
                            x_column=year_col,
                            y_columns=[primary_num],
                            aggregation="SUM",
                        ))

                    sheets.append(SheetPlan(
                        title=f"{profile.table_name.replace('_', ' ').title()} - Trends",
                        description="Time-series trends and timeline analysis",
                        dataset_id=profile.dataset_id,
                        table_name=profile.table_name,
                        charts=trend_charts,
                    ))

            else:
                # Text / Metadata table (e.g. Data Dictionary)
                dict_charts = [
                    ChartSpec(
                        chart_type=ChartType.TABLE,
                        title=f"{profile.table_name.replace('_', ' ').title()} Data Dictionary",
                        description="Complete table schema and column definitions",
                    )
                ]
                meaningful_cats = self._rank_categorical_columns(profile.categorical_columns) or profile.categorical_columns
                if meaningful_cats:
                    c1 = meaningful_cats[0]
                    dict_charts.append(ChartSpec(
                        chart_type=ChartType.BAR,
                        title=f"Distribution of {c1.replace('_', ' ').title()}",
                        x_column=c1,
                        description="Frequency count by category",
                    ))
                    if len(meaningful_cats) > 1:
                        c2 = meaningful_cats[1]
                        dict_charts.append(ChartSpec(
                            chart_type=ChartType.PIE,
                            title=f"Breakdown of {c2.replace('_', ' ').title()}",
                            x_column=c2,
                            description="Category breakdown proportion",
                        ))

                sheets.append(SheetPlan(
                    title=f"{profile.table_name.replace('_', ' ').title()} - Dictionary",
                    description="Schema specifications, data dictionary, and metadata overview",
                    dataset_id=profile.dataset_id,
                    table_name=profile.table_name,
                    charts=dict_charts,
                ))

        title_parts = [p.table_name.replace("_", " ").title() for p in sorted_profiles]
        dashboard_title = f"{' & '.join(title_parts)} Dashboard"

        return DashboardPlan(
            dashboard_title=dashboard_title,
            theme=theme,
            sheets=sheets,
            target=target,
        )


# Singleton
planner_agent = DashboardPlannerAgent()
