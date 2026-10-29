"""
DashForge - Interactive Dashboard Agent
Generates live, interactive Plotly visualizations and a standalone HTML dashboard package.
Users can view the dashboard directly in the app or download a self-contained .html dashboard.
"""
import json
import uuid
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.database import db
from backend.models import (
    DatasetProfile, DashboardPlan, SheetPlan, ChartSpec, ChartType
)


class DashboardAgent:
    """Generates interactive Plotly dashboards and standalone HTML dashboard files."""

    THEME_COLORS = {
        "corporate_blue": ["#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#1d4ed8", "#1e40af"],
        "modern_dark": ["#38bdf8", "#818cf8", "#f472b6", "#34d399", "#fbbf24", "#a78bfa"],
        "vibrant": ["#ec4899", "#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#06b6d4"],
        "minimal_light": ["#334155", "#475569", "#64748b", "#94a3b8", "#0ea5e9", "#2563eb"],
        "earth_tones": ["#854d0e", "#b45309", "#d97706", "#ca8a04", "#65a30d", "#16a34a"],
    }

    def generate_dashboard(
        self,
        profiles: list[DatasetProfile],
        plan: DashboardPlan
    ) -> dict:
        """Generate interactive charts and a complete standalone HTML dashboard.

        Returns:
            dict with:
                - 'dashboard_html': Complete standalone HTML string
                - 'sheet_figures': dict mapping sheet title -> list of plotly figure dicts
                - 'sheet_kpis': dict mapping sheet title -> list of KPI dicts
        """
        theme_key = plan.theme.value if hasattr(plan.theme, "value") else str(plan.theme).lower()
        palette = self.THEME_COLORS.get(theme_key, self.THEME_COLORS["corporate_blue"])

        # Map profiles by dataset_id and table_name
        profile_map = {p.dataset_id: p for p in profiles}
        table_map = {p.table_name.lower(): p for p in profiles}

        # Load dataframes
        df_map = {}
        for p in profiles:
            try:
                df = db.get_dataframe(p.dataset_id, p.table_name)
                df_map[p.table_name] = df
            except Exception:
                # Fallback: try loading directly from uploaded file
                cand = Path(settings.storage.upload_dir) / p.filename
                if cand.exists():
                    try:
                        df_map[p.table_name] = pd.read_csv(cand)
                    except Exception:
                        pass

        sheet_figures = {}
        sheet_kpis = {}
        sheet_chart_htmls = {}

        for sheet_idx, sheet in enumerate(plan.sheets):
            # Resolve dataframe for sheet
            p = profile_map.get(sheet.dataset_id, profiles[0] if profiles else None)
            df = df_map.get(p.table_name, list(df_map.values())[0]) if df_map else pd.DataFrame()

            # 1. Compute Sheet KPIs
            kpis = self._compute_kpis(df, sheet, p)
            sheet_kpis[sheet.title] = kpis

            # 2. Build Charts
            figures = []
            chart_html_snippets = []

            for ci, chart in enumerate(sheet.charts):
                fig = self._build_chart_figure(df, chart, palette, sheet_idx * 10 + ci)
                if fig:
                    figures.append({"title": chart.title, "chart_type": str(chart.chart_type), "figure": fig})
                    chart_div = fig.to_html(
                        include_plotlyjs=False,
                        full_html=False,
                        config={"responsive": True, "displayModeBar": True, "displaylogo": False}
                    )
                    chart_html_snippets.append({
                        "title": chart.title,
                        "description": chart.description,
                        "chart_type": str(chart.chart_type.value if hasattr(chart.chart_type, 'value') else chart.chart_type).upper(),
                        "html": chart_div,
                        "width": getattr(chart, "width", 6),
                    })

            sheet_figures[sheet.title] = figures
            sheet_chart_htmls[sheet.title] = chart_html_snippets

        # 3. Assemble Standalone HTML Dashboard
        dashboard_html = self._assemble_html(plan, sheet_kpis, sheet_chart_htmls, palette)

        return {
            "dashboard_html": dashboard_html,
            "sheet_figures": sheet_figures,
            "sheet_kpis": sheet_kpis,
        }

    def _compute_kpis(self, df: pd.DataFrame, sheet: SheetPlan, profile: Optional[DatasetProfile]) -> list[dict]:
        """Compute top-level KPI metrics for a sheet."""
        kpis = []
        if df.empty:
            return [{"title": "Total Records", "value": "0", "subtitle": "Records loaded"}]

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        # 1. Total Volume / Records
        is_transactional = any("trans" in c.lower() or "order" in c.lower() for c in df.columns)
        kpis.append({
            "title": "Total Transactions" if is_transactional else "Total Records",
            "value": f"{len(df):,}",
            "subtitle": f"Source: {profile.table_name if profile else 'Dataset'}"
        })

        # 2. Revenue / Sales Amount
        rev_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["sales_amount", "revenue", "total_sales", "amount"])]
        if not rev_candidates:
            rev_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["sale", "price"])]

        if rev_candidates:
            rc = rev_candidates[0]
            total_rev = float(df[rc].sum())
            kpis.append({
                "title": f"Total {rc.replace('_', ' ').title()}",
                "value": f"${total_rev:,.2f}" if total_rev >= 1000 else f"{total_rev:,.2f}",
                "subtitle": f"Sum of {rc}"
            })

        # 3. Profit / Net Margin
        prof_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["profit", "net_income", "margin"])]
        if prof_candidates:
            pc = prof_candidates[0]
            total_prof = float(df[pc].sum())
            kpis.append({
                "title": f"Total {pc.replace('_', ' ').title()}",
                "value": f"${total_prof:,.2f}" if total_prof >= 1000 else f"{total_prof:,.2f}",
                "subtitle": f"Sum of {pc}"
            })

        # 4. Quantity / Volume Sold
        qty_candidates = [c for c in numeric_cols if any(k in c.lower() for k in ["quantity", "volume", "units", "qty"])]
        if qty_candidates:
            qc = qty_candidates[0]
            total_qty = float(df[qc].sum())
            kpis.append({
                "title": f"Total {qc.replace('_', ' ').title()}",
                "value": f"{total_qty:,.0f}",
                "subtitle": f"Sum of {qc}"
            })
        elif len(kpis) < 4:
            entity_candidates = [c for c in df.columns if any(k in c.lower() for k in ["customer_name", "product_name", "store_name", "city", "region"])]
            if not entity_candidates:
                entity_candidates = [c for c in df.columns if any(k in c.lower() for k in ["customer", "order", "product", "client"])]
            if entity_candidates:
                ec = entity_candidates[0]
                kpis.append({
                    "title": f"Unique {ec.replace('_', ' ').title()}",
                    "value": f"{df[ec].nunique():,}",
                    "subtitle": f"Distinct count"
                })

        return kpis[:4]

    def _build_chart_figure(
        self,
        df: pd.DataFrame,
        chart: ChartSpec,
        palette: list[str],
        seed_idx: int = 0
    ) -> Optional[go.Figure]:
        """Build an interactive Plotly figure based on chart spec."""
        if df.empty:
            return None

        ctype = str(chart.chart_type.value if hasattr(chart.chart_type, 'value') else chart.chart_type).lower()
        
        # Categorical, numeric, and date column discovery
        cat_cols = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        date_cols = [c for c in df.columns if any(k in c.lower() for k in ["date", "time", "year", "month", "day", "period"])]

        # Filter out IDs from categorical column defaults
        meaningful_cat_cols = [c for c in cat_cols if not (c.lower().endswith("_id") or c.lower() == "id" or "transaction" in c.lower() or "order_id" in c.lower())]

        # Smart column resolution (case-insensitive + fallback)
        x_col = chart.x_column if chart.x_column in df.columns else None
        if not x_col and chart.x_column:
            for c in df.columns:
                if c.lower() == chart.x_column.lower():
                    x_col = c
                    break
        if not x_col:
            x_col = meaningful_cat_cols[0] if meaningful_cat_cols else (cat_cols[0] if cat_cols else (date_cols[0] if date_cols else df.columns[0]))

        y_cols = [y for y in chart.y_columns if y in df.columns]
        if not y_cols and chart.y_columns:
            for yc in chart.y_columns:
                for c in df.columns:
                    if c.lower() == yc.lower():
                        y_cols.append(c)
                        break
        if not y_cols and num_cols:
            y_cols = [num_cols[0]]

        # Layout themes (valid Plotly font config without unsupported properties)
        cartesian_layout = dict(
            paper_bgcolor="rgba(15, 23, 42, 0)",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            font=dict(color="#e2e8f0", family="Inter, -apple-system, sans-serif"),
            title=dict(text=chart.title, font=dict(size=14, color="#f8fafc"), x=0.02, y=0.96),
            xaxis=dict(gridcolor="rgba(148, 163, 184, 0.15)", linecolor="rgba(148, 163, 184, 0.2)"),
            yaxis=dict(gridcolor="rgba(148, 163, 184, 0.15)", linecolor="rgba(148, 163, 184, 0.2)"),
            margin=dict(l=45, r=25, t=50, b=45),
            colorway=palette,
        )

        non_axis_layout = dict(
            paper_bgcolor="rgba(15, 23, 42, 0)",
            plot_bgcolor="rgba(15, 23, 42, 0)",
            font=dict(color="#e2e8f0", family="Inter, -apple-system, sans-serif"),
            title=dict(text=chart.title, font=dict(size=14, color="#f8fafc"), x=0.02, y=0.96),
            margin=dict(l=20, r=20, t=50, b=20),
            colorway=palette,
        )

        try:
            # 1. Bar Chart
            if ctype in ["bar", "stacked_bar"]:
                if x_col and y_cols and y_cols[0] in num_cols:
                    agg_df = df.groupby(x_col, as_index=False)[y_cols[0]].sum().sort_values(by=y_cols[0], ascending=False).head(15)
                    fig = px.bar(agg_df, x=x_col, y=y_cols[0], title=chart.title, color_discrete_sequence=palette)
                elif x_col:
                    counts = df[x_col].value_counts().reset_index().head(15)
                    counts.columns = [x_col, "Count"]
                    fig = px.bar(counts, x=x_col, y="Count", title=chart.title, color_discrete_sequence=palette)
                elif num_cols:
                    fig = px.bar(df.head(20), y=num_cols[0], title=chart.title, color_discrete_sequence=palette)
                else:
                    counts = df[df.columns[0]].value_counts().reset_index().head(15)
                    counts.columns = [df.columns[0], "Count"]
                    fig = px.bar(counts, x=df.columns[0], y="Count", title=chart.title, color_discrete_sequence=palette)
                fig.update_layout(**cartesian_layout)
                return fig

            # 2. Line / Area Chart
            elif ctype in ["line", "area"]:
                time_col = date_cols[0] if date_cols else x_col
                valid_y = [y for y in y_cols if y in num_cols] or (num_cols[:2] if num_cols else [])
                if time_col and valid_y:
                    agg_df = df.groupby(time_col, as_index=False)[valid_y].sum().sort_values(by=time_col).head(35)
                    if ctype == "area":
                        fig = px.area(agg_df, x=time_col, y=valid_y[0], title=chart.title, color_discrete_sequence=palette)
                    else:
                        y_val = valid_y if len(valid_y) > 1 else valid_y[0]
                        fig = px.line(agg_df, x=time_col, y=y_val, markers=True, title=chart.title, color_discrete_sequence=palette)
                elif valid_y:
                    y_val = valid_y if len(valid_y) > 1 else valid_y[0]
                    fig = px.line(df.head(50), y=y_val, markers=True, title=chart.title, color_discrete_sequence=palette)
                else:
                    counts = df[df.columns[0]].value_counts().reset_index().head(20)
                    counts.columns = [df.columns[0], "Count"]
                    fig = px.line(counts, x=df.columns[0], y="Count", markers=True, title=chart.title, color_discrete_sequence=palette)
                fig.update_layout(**cartesian_layout)
                return fig

            # 3. Pie / Donut Chart
            elif ctype in ["pie", "donut"]:
                cat_col = x_col if (x_col in meaningful_cat_cols or x_col in cat_cols) else (meaningful_cat_cols[0] if meaningful_cat_cols else (cat_cols[0] if cat_cols else df.columns[0]))
                val_col = y_cols[0] if (y_cols and y_cols[0] in num_cols) else None
                if val_col:
                    pie_data = df.groupby(cat_col, as_index=False)[val_col].sum().sort_values(by=val_col, ascending=False).head(8)
                    fig = px.pie(pie_data, names=cat_col, values=val_col, title=chart.title,
                                 hole=0.45 if ctype == "donut" else 0, color_discrete_sequence=palette)
                else:
                    counts = df[cat_col].value_counts().reset_index().head(8)
                    counts.columns = [cat_col, "Count"]
                    fig = px.pie(counts, names=cat_col, values="Count", title=chart.title,
                                 hole=0.45 if ctype == "donut" else 0, color_discrete_sequence=palette)
                fig.update_layout(**non_axis_layout)
                return fig

            # 4. Scatter Plot
            elif ctype == "scatter":
                if len(num_cols) >= 2:
                    fig = px.scatter(df.head(300), x=num_cols[0], y=num_cols[1], title=chart.title,
                                     color_discrete_sequence=palette, opacity=0.85)
                elif num_cols and cat_cols:
                    fig = px.strip(df.head(200), x=cat_cols[0], y=num_cols[0], title=chart.title,
                                   color_discrete_sequence=palette)
                else:
                    fig = px.bar(df.head(15), y=df.columns[0], title=chart.title, color_discrete_sequence=palette)
                fig.update_layout(**cartesian_layout)
                return fig

            # 5. Histogram / Box
            elif ctype in ["histogram", "box"]:
                target_col = y_cols[0] if (y_cols and y_cols[0] in num_cols) else (num_cols[0] if num_cols else df.columns[0])
                if ctype == "histogram":
                    fig = px.histogram(df, x=target_col, nbins=25, title=chart.title, color_discrete_sequence=palette)
                else:
                    fig = px.box(df, y=target_col, title=chart.title, color_discrete_sequence=palette)
                fig.update_layout(**cartesian_layout)
                return fig

            # 6. KPI Card / Metric Indicator
            elif ctype in ["kpi_card", "indicator"]:
                val_col = y_cols[0] if (y_cols and y_cols[0] in num_cols) else (num_cols[0] if num_cols else None)
                if val_col:
                    total_val = float(df[val_col].sum())
                    fig = go.Figure(go.Indicator(
                        mode="number",
                        value=total_val,
                        number={"font": {"size": 36, "color": "#38bdf8"}, "valueformat": ",.0f" if total_val > 1000 else ",.2f"},
                    ))
                    fig.update_layout(
                        title=dict(text=chart.title, font=dict(size=14, color="#f8fafc"), x=0.5, y=0.88),
                        margin=dict(l=20, r=20, t=40, b=20),
                        paper_bgcolor="rgba(15, 23, 42, 0)",
                        plot_bgcolor="rgba(15, 23, 42, 0)",
                        font=dict(color="#e2e8f0"),
                    )
                    return fig
                else:
                    # Categorical table preview
                    sample_cols = list(df.columns[:6])
                    table_df = df[sample_cols].head(12)
                    fig = go.Figure(data=[go.Table(
                        header=dict(values=[f"<b>{c}</b>" for c in table_df.columns], fill_color="#1e293b", align="left", font=dict(color="#f8fafc", size=12)),
                        cells=dict(values=[table_df[c] for c in table_df.columns], fill_color="#0f172a", align="left", font=dict(color="#cbd5e1", size=11))
                    )])
                    fig.update_layout(**non_axis_layout)
                    return fig

            # 7. Table
            elif ctype == "table":
                sample_cols = list(df.columns[:8])
                table_df = df[sample_cols].head(15)
                fig = go.Figure(data=[go.Table(
                    header=dict(values=[f"<b>{c}</b>" for c in table_df.columns], fill_color="#1e293b", align="left", font=dict(color="#f8fafc", size=12)),
                    cells=dict(values=[table_df[c] for c in table_df.columns], fill_color="#0f172a", align="left", font=dict(color="#cbd5e1", size=11))
                )])
                fig.update_layout(**non_axis_layout)
                return fig

            else:
                # Default bar chart
                target_col = num_cols[0] if num_cols else df.columns[0]
                fig = px.bar(df.head(15), y=target_col, title=chart.title, color_discrete_sequence=palette)
                fig.update_layout(**cartesian_layout)
                return fig

        except Exception as e:
            # Absolute fallback: simple table or bar
            try:
                if num_cols:
                    fig = px.bar(df.head(10), y=num_cols[0], title=chart.title, color_discrete_sequence=palette)
                    fig.update_layout(paper_bgcolor="rgba(15, 23, 42, 0)", plot_bgcolor="rgba(15, 23, 42, 0.4)", font=dict(color="#e2e8f0"))
                    return fig
                else:
                    sample_cols = list(df.columns[:5])
                    table_df = df[sample_cols].head(10)
                    fig = go.Figure(data=[go.Table(
                        header=dict(values=[f"<b>{c}</b>" for c in table_df.columns], fill_color="#1e293b", font=dict(color="#fff")),
                        cells=dict(values=[table_df[c] for c in table_df.columns], fill_color="#0f172a", font=dict(color="#cbd5e1"))
                    )])
                    fig.update_layout(paper_bgcolor="rgba(15, 23, 42, 0)", font=dict(color="#e2e8f0"))
                    return fig
            except Exception:
                return None

    def _assemble_html(
        self,
        plan: DashboardPlan,
        sheet_kpis: dict,
        sheet_chart_htmls: dict,
        palette: list[str]
    ) -> str:
        """Assemble a single standalone, self-contained interactive HTML dashboard."""
        accent_color = palette[0]
        secondary_color = palette[1] if len(palette) > 1 else palette[0]

        # Generate Tab Headers and Tab Panes
        tab_buttons = []
        tab_panes = []

        for idx, sheet in enumerate(plan.sheets):
            active_class = "active" if idx == 0 else ""
            tab_id = f"sheet-{idx}"
            tab_buttons.append(
                f'<button class="tab-button {active_class}" onclick="openSheet(\'{tab_id}\')">'
                f'📊 {sheet.title}'
                f'</button>'
            )

            # KPIs HTML
            kpis = sheet_kpis.get(sheet.title, [])
            kpi_cards = []
            for k in kpis:
                kpi_cards.append(f"""
                <div class="kpi-card">
                    <div class="kpi-title">{k.get('title', 'Metric')}</div>
                    <div class="kpi-value">{k.get('value', '-')}</div>
                    <div class="kpi-sub">{k.get('subtitle', '')}</div>
                </div>
                """)
            kpis_html = "".join(kpi_cards)

            # Charts HTML
            charts = sheet_chart_htmls.get(sheet.title, [])
            charts_html_list = []
            for c in charts:
                charts_html_list.append(f"""
                <div class="chart-container">
                    <div class="chart-header">
                        <span class="chart-badge">{c['chart_type']}</span>
                        <div class="chart-title">{c['title']}</div>
                    </div>
                    <div class="chart-body">
                        {c['html']}
                    </div>
                </div>
                """)
            charts_html = "".join(charts_html_list)

            tab_panes.append(f"""
            <div id="{tab_id}" class="sheet-pane {active_class}">
                <div class="sheet-desc">
                    <strong>{sheet.title}</strong> — {sheet.description or 'Analytical view'} 
                    <span style="color:#94a3b8;font-size:0.85rem;margin-left:8px;">(Target: {sheet.target_audience})</span>
                </div>
                <div class="kpi-grid">
                    {kpis_html}
                </div>
                <div class="charts-grid">
                    {charts_html}
                </div>
            </div>
            """)

        tabs_nav_html = "\n".join(tab_buttons)
        tabs_content_html = "\n".join(tab_panes)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{plan.dashboard_title} — DashForge Interactive Dashboard</title>
    <!-- Plotly.js for standalone execution -->
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-card: rgba(18, 26, 43, 0.75);
            --bg-card-hover: rgba(30, 41, 59, 0.85);
            --border-card: rgba(148, 163, 184, 0.12);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: {accent_color};
            --accent-sub: {secondary_color};
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(at 0% 0%, rgba(37, 99, 235, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.1) 0px, transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px;
        }}

        .dashboard-header {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .title-group h1 {{
            font-size: 1.85rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }}

        .title-group p {{
            color: var(--text-muted);
            font-size: 0.95rem;
        }}

        .badge-bar {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .pill-badge {{
            background: rgba(37, 99, 235, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.35);
            color: #93c5fd;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        /* Tab Navigation */
        .tabs-nav {{
            display: flex;
            gap: 10px;
            margin-bottom: 24px;
            overflow-x: auto;
            padding-bottom: 4px;
        }}

        .tab-button {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            color: var(--text-muted);
            padding: 12px 24px;
            border-radius: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }}

        .tab-button:hover {{
            background: var(--bg-card-hover);
            color: #ffffff;
            border-color: rgba(148, 163, 184, 0.25);
        }}

        .tab-button.active {{
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
        }}

        /* Sheet Panes */
        .sheet-pane {{
            display: none;
            animation: fadeIn 0.3s ease;
        }}

        .sheet-pane.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(6px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .sheet-desc {{
            background: rgba(30, 41, 59, 0.4);
            border-left: 4px solid var(--accent);
            padding: 12px 18px;
            border-radius: 0 8px 8px 0;
            font-size: 0.95rem;
            margin-bottom: 20px;
            color: #cbd5e1;
        }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            backdrop-filter: blur(8px);
            border-radius: 14px;
            padding: 20px;
            transition: transform 0.2s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(148, 163, 184, 0.25);
        }}

        .kpi-title {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .kpi-value {{
            font-size: 1.85rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 4px;
        }}

        .kpi-sub {{
            font-size: 0.8rem;
            color: #64748b;
        }}

        /* Charts Grid */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}

        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 18px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .chart-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
        }}

        .chart-badge {{
            background: rgba(148, 163, 184, 0.12);
            color: #94a3b8;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            text-transform: uppercase;
        }}

        .chart-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #f1f5f9;
        }}

        .chart-body {{
            flex: 1;
            min-height: 340px;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            color: #64748b;
            font-size: 0.85rem;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px solid var(--border-card);
        }}
    </style>
</head>
<body>

    <header class="dashboard-header">
        <div class="title-group">
            <h1>{plan.dashboard_title}</h1>
            <p>{plan.subtitle or 'AI-Generated Executive Analytics Dashboard'}</p>
        </div>
        <div class="badge-bar">
            <span class="pill-badge">✨ Standalone Interactive</span>
            <span class="pill-badge">⚡ DashForge 1.0</span>
        </div>
    </header>

    <nav class="tabs-nav">
        {tabs_nav_html}
    </nav>

    <main>
        {tabs_content_html}
    </main>

    <footer class="footer">
        Generated by <strong>DashForge</strong> • Complete Standalone Interactive Dashboard • Use offline or online in any browser
    </footer>

    <script>
        function openSheet(sheetId) {{
            // Hide all sheet panes
            const panes = document.querySelectorAll('.sheet-pane');
            panes.forEach(p => p.classList.remove('active'));

            // Remove active from all buttons
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(b => b.classList.remove('active'));

            // Show selected pane
            const targetPane = document.getElementById(sheetId);
            if (targetPane) {{
                targetPane.classList.add('active');
            }}

            // Highlight clicked button
            event.currentTarget.classList.add('active');

            // Trigger window resize so Plotly reflows correctly in newly visible tab
            window.dispatchEvent(new Event('resize'));
        }}
    </script>
</body>
</html>"""
        return html_template


# Global Singleton
dashboard_agent = DashboardAgent()
