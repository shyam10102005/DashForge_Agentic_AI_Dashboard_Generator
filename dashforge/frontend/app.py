"""
DashForge - Streamlit Frontend
Sequential Step-by-Step (One-after-One) Agentic AI Dashboard Generator
"""
import sys
import os
import json
import asyncio
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

# Fix Streamlit / PyArrow "Unrecognized type: LargeUtf8"
# PyArrow on Windows defaults string columns to large_string (type 20).
# This patch converts them to standard utf8 before sending to browser JS.
try:
    import pyarrow as pa
    import streamlit.type_util as _stu
    _orig_pyarrow_table_to_bytes = _stu.pyarrow_table_to_bytes

    def _safe_pyarrow_table_to_bytes(table: pa.Table) -> bytes:
        try:
            new_fields = []
            has_large = False
            for f in table.schema:
                t_str = str(f.type)
                if f.type == pa.large_string() or f.type == pa.large_utf8() or t_str == "large_string":
                    new_fields.append(f.with_type(pa.string()))
                    has_large = True
                elif f.type == pa.large_binary() or t_str == "large_binary":
                    new_fields.append(f.with_type(pa.binary()))
                    has_large = True
                else:
                    new_fields.append(f)
            if has_large and hasattr(table, "schema") and table.schema is not None:
                table = table.cast(pa.schema(new_fields, metadata=table.schema.metadata))
        except Exception:
            pass
        return _orig_pyarrow_table_to_bytes(table)

    _stu.pyarrow_table_to_bytes = _safe_pyarrow_table_to_bytes
except Exception:
    pass

from backend.config import settings
from backend.models import OutputTarget, ThemePreset, THEME_PALETTES
from backend.orchestrator import orchestrator
from backend.agents.packaging_agent import packaging_agent

# Page config - collapsed sidebar to focus entirely on sequential one-after-one workflow
st.set_page_config(
    page_title="DashForge — Agentic AI Dashboard Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at top left, #0f172a, #020617);
        color: #f8fafc;
    }
    
    .hero-container {
        padding: 1.8rem 2.2rem;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 16px;
        box-shadow: 0 16px 36px -12px rgba(0, 0, 0, 0.5);
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    
    .hero-container::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc, #f472b6);
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
        letter-spacing: -0.03em;
    }
    
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    
    /* Stepper Navigation Bar */
    .stepper-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 14px;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1.8rem;
        overflow-x: auto;
    }
    
    .step-item {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748b;
        white-space: nowrap;
        transition: all 0.2s ease;
    }
    
    .step-item.active {
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.35);
    }
    
    .step-item.completed {
        color: #34d399;
    }
    
    .step-arrow {
        color: #475569;
        font-size: 0.75rem;
    }
    
    .card-box {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 14px;
        padding: 1.6rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    
    .metric-val {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metric-lbl {
        font-size: 0.75rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }
    
    .sheet-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
    }
    
    .chart-pill {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.3rem;
    }
    
    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        letter-spacing: 0.01em;
        padding: 0.55rem 1.4rem;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
def init_session_state():
    if "current_step" not in st.session_state:
        st.session_state.current_step = 1
    if "uploaded_file_paths" not in st.session_state:
        st.session_state.uploaded_file_paths = []
    if "target_choice" not in st.session_state:
        st.session_state.target_choice = "Both (Interactive Dashboard + Power BI & Tableau Blueprints)"
    if "theme_label" not in st.session_state:
        st.session_state.theme_label = "Corporate Blue (Classic executive)"
    if "custom_chart_reqs" not in st.session_state:
        st.session_state.custom_chart_reqs = ""
    if "pipeline_run" not in st.session_state:
        st.session_state.pipeline_run = None
    if "events" not in st.session_state:
        st.session_state.events = []


init_session_state()

# Navigation Helpers
TOTAL_STEPS = 7
STEP_NAMES = [
    "1. Dataset Upload",
    "2. Theme & Options",
    "3. Preprocessing",
    "4. Headings & Sheets",
    "5. Python Script",
    "6. SQL Code",
    "7. Dashboard & Blueprints"
]


def go_to_step(step_num):
    st.session_state.current_step = step_num
    st.rerun()


# Top Hero Header
st.markdown(f"""
<div class="hero-container">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div class="hero-title">⚡ DashForge</div>
            <div class="hero-subtitle">
                Sequential Agentic AI Dashboard Generator — Step-by-Step from Dataset to <b>Standalone Interactive Dashboard</b> + <b>Power BI & Tableau Blueprints</b>
            </div>
        </div>
        <div style="text-align:right;">
            <span style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); padding:0.35rem 0.8rem; border-radius:9999px; font-size:0.8rem; font-weight:600;">
                🤖 LLM: {settings.ollama.model}
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Top Stepper Bar (One-after-One progress)
cur = st.session_state.current_step
stepper_html = '<div class="stepper-container">'
for idx, name in enumerate(STEP_NAMES, 1):
    active_class = "active" if idx == cur else ("completed" if idx < cur else "")
    icon = "✓ " if idx < cur else f"{idx}. "
    display_name = name.split(". ")[1]
    stepper_html += f'<div class="step-item {active_class}">{icon}{display_name}</div>'
    if idx < TOTAL_STEPS:
        stepper_html += '<span class="step-arrow">➔</span>'
stepper_html += '</div>'
st.markdown(stepper_html, unsafe_allow_html=True)


def create_sample_dataset() -> list[dict]:
    """Create a realistic sample retail sales dataset."""
    import numpy as np
    np.random.seed(42)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    categories = ["Technology", "Furniture", "Office Supplies"]
    subcats = {
        "Technology": ["Phones", "Laptops", "Accessories"],
        "Furniture": ["Chairs", "Tables", "Bookcases"],
        "Office Supplies": ["Paper", "Binders", "Storage"],
    }
    regions = ["North", "South", "East", "West"]
    segments = ["Consumer", "Corporate", "Home Office"]
    
    cat_choices = np.random.choice(categories, n)
    subcat_choices = [np.random.choice(subcats[c]) for c in cat_choices]
    sales = np.round(np.random.exponential(250, n) + 20, 2)
    profits = np.round(sales * np.random.uniform(-0.15, 0.4, n), 2)
    quantities = np.random.randint(1, 10, n)
    discounts = np.round(np.random.choice([0.0, 0.1, 0.15, 0.2, 0.3], n, p=[0.5, 0.2, 0.15, 0.1, 0.05]), 2)
    
    df = pd.DataFrame({
        "Order_ID": [f"ORD-{1000+i}" for i in range(n)],
        "Order_Date": dates,
        "Customer_Segment": np.random.choice(segments, n),
        "Region": np.random.choice(regions, n),
        "Category": cat_choices,
        "Sub_Category": subcat_choices,
        "Sales": sales,
        "Profit": profits,
        "Quantity": quantities,
        "Discount": discounts,
    })
    
    # Introduce sample nulls and duplicates for quality check demo
    df.loc[10, "Sales"] = None
    df.loc[25, "Profit"] = None
    df = pd.concat([df, df.iloc[[5, 12]]], ignore_index=True)
    
    sample_dir = Path(settings.storage.upload_dir) / "sample_superstore"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_path = sample_dir / "Superstore_Sales.csv"
    df.to_csv(sample_path, index=False)
    
    return [{"path": str(sample_path), "filename": "Superstore_Sales.csv"}]


# Theme Preset Maps
THEME_OPTIONS = {
    "Corporate Blue (Classic executive)": ThemePreset.CORPORATE_BLUE,
    "Midnight Dark (Modern sleek dark)": ThemePreset.MODERN_DARK,
    "Emerald Growth (Finance & ROI)": ThemePreset.EMERALD_GROWTH,
    "Sunset Crimson (Marketing & Retail)": ThemePreset.SUNSET_CRIMSON,
    "Nordic Frost (Clean minimalist)": ThemePreset.NORDIC_FROST,
    "Vibrant Tech (High-contrast SaaS)": ThemePreset.VIBRANT_TECH,
}

TARGET_MAP = {
    "Both (Interactive Dashboard + Power BI & Tableau Blueprints)": OutputTarget.BOTH,
    "Power BI Focus (Interactive Dashboard + DAX / M / TMSL Blueprint)": OutputTarget.POWERBI,
    "Tableau Focus (Interactive Dashboard + Calculated Fields Blueprint)": OutputTarget.TABLEAU,
}


# =========================================================
# STEP 1: DATASET UPLOAD
# =========================================================
if cur == 1:
    st.markdown("### 📂 Step 1: Upload Your Dataset")
    st.caption("Provide your dataset in any format: **CSV, Excel (.xlsx, .xls), or ZIP archive** containing multiple data files.")
    
    with st.container():
        uploaded_files = st.file_uploader(
            "Select or drag & drop files",
            type=["csv", "xlsx", "xls", "zip"],
            accept_multiple_files=True,
            help="Upload single or multiple files. If a ZIP is provided, it will be automatically unpacked."
        )
        
        col_sample, col_status = st.columns([1, 2])
        with col_sample:
            if st.button("✨ Load Sample Superstore Data", use_container_width=True):
                st.session_state.uploaded_file_paths = create_sample_dataset()
                st.toast("Loaded Sample Superstore dataset!", icon="✨")
                st.rerun()
                
        if uploaded_files:
            upload_dir = Path(settings.storage.upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)
            saved_paths = []
            for uf in uploaded_files:
                file_path = upload_dir / uf.name
                with open(file_path, "wb") as f:
                    f.write(uf.getbuffer())
                saved_paths.append({"path": str(file_path), "filename": uf.name})
            st.session_state.uploaded_file_paths = saved_paths

        # Show current files
        if st.session_state.uploaded_file_paths:
            st.success(f"✅ Ready with {len(st.session_state.uploaded_file_paths)} dataset file(s):")
            for f in st.session_state.uploaded_file_paths:
                st.markdown(f"- **`{f['filename']}`** (`{f['path']}`)")
                
            st.markdown("<br>", unsafe_allow_html=True)
            col_b, col_next = st.columns([3, 1])
            with col_next:
                if st.button("Next: Configure Theme & Options ➔", type="primary", use_container_width=True):
                    go_to_step(2)
        else:
            st.info("Upload your dataset above or click 'Load Sample Superstore Data' to continue.")


# =========================================================
# STEP 2: THEME & REPORT OPTIONS
# =========================================================
elif cur == 2:
    st.markdown("### 🎨 Step 2: Theme & Report Configuration")
    st.caption("Select your dashboard target format, color palette, and specify any custom chart preferences.")
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.session_state.target_choice = st.radio(
            "🎯 Output Format Target",
            options=list(TARGET_MAP.keys()),
            index=list(TARGET_MAP.keys()).index(st.session_state.target_choice) if st.session_state.target_choice in TARGET_MAP else 0,
        )
        
        st.session_state.theme_label = st.selectbox(
            "🎨 Select Dashboard Theme",
            options=list(THEME_OPTIONS.keys()),
            index=list(THEME_OPTIONS.keys()).index(st.session_state.theme_label) if st.session_state.theme_label in THEME_OPTIONS else 0,
        )
        
        selected_theme = THEME_OPTIONS[st.session_state.theme_label]
        palette = THEME_PALETTES.get(selected_theme, THEME_PALETTES["corporate_blue"])
        palette_html = "".join([
            f'<div style="background-color: {c}; width: 26px; height: 26px; border-radius: 6px; display: inline-block; margin-right: 6px; border: 1px solid rgba(255,255,255,0.2);" title="{c}"></div>'
            for c in palette[:8]
        ])
        st.markdown(f"**Palette Preview:**<br>{palette_html}", unsafe_allow_html=True)
        
    with col_r:
        st.session_state.custom_chart_reqs = st.text_area(
            "💡 Specify desired charts or focus areas (optional)",
            value=st.session_state.custom_chart_reqs,
            placeholder="e.g., Monthly sales trend, Customer segment breakdown, Regional profit map, Top 10 products by revenue",
            height=140,
            help="Our AI Planner will prioritize these visual requests in the generated sheets."
        )
        st.info(f"🤖 **Connected LLM:** `{settings.ollama.model}` (Ollama Local)")
        
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_run = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to Upload", use_container_width=True):
            go_to_step(1)
    with col_run:
        if st.button("🚀 Run Agentic AI Pipeline ➔", type="primary", use_container_width=True):
            progress_box = st.status("🤖 DashForge AI Agents Operating...", expanded=True)
            chart_reqs = [c.strip() for c in st.session_state.custom_chart_reqs.split(",") if c.strip()]
            
            def on_progress(event, message=None):
                if message is not None:
                    step_val = str(event)
                    msg_val = str(message)
                elif hasattr(event, "step") and hasattr(event, "message"):
                    step_val = event.step
                    msg_val = event.message
                else:
                    step_val = "status"
                    msg_val = str(event) if event else ""

                step_badges = {
                    "ingesting": "📂 INGESTION",
                    "profiling": "🔍 PROFILING",
                    "preprocessing": "🧹 PREPROCESSING",
                    "planning": "🤖 AI PLANNER (qwen3:4b)",
                    "generating_sql": "🗄️ SQL ENGINE",
                    "generating_dashboards": "📊 POWER BI & TABLEAU",
                    "packaging": "📦 PACKAGING",
                    "completed": "✅ COMPLETED",
                }
                badge = step_badges.get(str(step_val).lower(), f"⚡ {str(step_val).upper()}")
                progress_box.write(f"**{badge}** — {msg_val}")
            
            with progress_box:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    run = loop.run_until_complete(
                        orchestrator.run_pipeline(
                            file_paths=st.session_state.uploaded_file_paths,
                            target=TARGET_MAP[st.session_state.target_choice],
                            theme=THEME_OPTIONS[st.session_state.theme_label],
                            user_chart_requests=chart_reqs,
                            on_progress=on_progress,
                        )
                    )
                    loop.close()
                    st.session_state.pipeline_run = run
                    progress_box.update(label="✅ Analysis & Generation Completed!", state="complete")
                    go_to_step(3)
                except Exception as e:
                    progress_box.update(label=f"❌ Error: {e}", state="error")
                    st.error(f"Pipeline error: {str(e)}")


# =========================================================
# STEP 3: PREPROCESSING & QUALITY CHECK
# =========================================================
elif cur == 3:
    run = st.session_state.pipeline_run
    if not run:
        st.warning("Please complete Step 1 & 2 first.")
        if st.button("Go to Step 1"):
            go_to_step(1)
        st.stop()
        
    st.markdown("### 🧹 Step 3: Data Preprocessing & Quality Verification")
    st.caption("Detailed breakdown of duplicates, null counts, data types, and quality audit.")
    
    for ds in run.datasets:
        st.markdown(f"#### 📄 Dataset: `{ds.filename}` (Table: `{ds.table_name}`)")
        
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Total Rows", f"{ds.row_count:,}")
        q2.metric("Total Columns", ds.column_count)
        q3.metric("Duplicates Handled", ds.duplicate_row_count)
        q4.metric("Quality Score", f"{ds.data_quality_score:.1f}%")
        
        # Null values breakdown
        null_cols = [c for c in ds.columns if c.null_count > 0]
        if null_cols:
            st.warning(f"⚠️ Columns with missing values handled: {', '.join([f'{c.name} ({c.null_count} nulls)' for c in null_cols])}")
        else:
            st.success("✅ Zero null values detected in this dataset.")
            
        # Column profiling table
        col_data = []
        for col in ds.columns:
            col_data.append({
                "Column Name": col.name,
                "Inferred Data Type": col.dtype,
                "Null Count": col.null_count,
                "Null %": f"{col.null_pct:.1f}%",
                "Unique Values": col.unique_count,
                "Sample Values": ", ".join(str(v) for v in col.sample_values[:3]),
            })
        st.dataframe(pd.DataFrame(col_data), use_container_width=True)
        
        # Preprocessing audit logs
        st.markdown("**Applied Data Cleaning Steps:**")
        for log in run.preprocessing_logs:
            if log.dataset_id == ds.dataset_id or not log.dataset_id:
                st.markdown(f"- **[{log.step_type}]** {log.description} *(Rows affected: {log.rows_affected})*")
                
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_next = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to Options", use_container_width=True):
            go_to_step(2)
    with col_next:
        if st.button("Next: AI Dashboard Blueprint & Sheets ➔", type="primary", use_container_width=True):
            go_to_step(4)


# =========================================================
# STEP 4: DASHBOARD HEADINGS, SHEETS & VISUALS
# =========================================================
elif cur == 4:
    run = st.session_state.pipeline_run
    if not run or not run.dashboard_plan:
        st.warning("Please complete previous steps first.")
        st.stop()
        
    st.markdown("### 📊 Step 4: Suggested Dashboard Headings & Multi-Sheet Structure")
    st.caption("AI-planned executive headings, multi-sheet distribution, and visualization blueprints.")
    
    st.markdown(f"## 📋 {run.dashboard_plan.dashboard_title}")
    st.markdown(f"**Subtitle:** {run.dashboard_plan.subtitle}")
    st.info(f"**Core Business Problem:** {run.dashboard_plan.business_problem}")
    
    st.markdown("#### 📑 Planned Dashboard Sheets & Visual Layouts")
    for idx, sheet in enumerate(run.dashboard_plan.sheets, 1):
        with st.expander(f"📌 Sheet {idx}: **{sheet.title}** ({sheet.target_audience})", expanded=True):
            st.caption(sheet.description)
            
            # KPIs on this sheet
            if getattr(sheet, "kpis", None):
                st.markdown("**Top KPI Metric Cards:**")
                kpi_cols = st.columns(len(sheet.kpis))
                for i, kpi in enumerate(sheet.kpis):
                    with kpi_cols[i]:
                        st.metric(label=getattr(kpi, "title", "Metric"), value=getattr(kpi, "measure_column", "Value"))
            
            # Charts on this sheet
            st.markdown("**Sheet Visualizations:**")
            chart_cols = st.columns(2)
            for ci, chart in enumerate(sheet.charts):
                chart_type_str = chart.chart_type.value.upper() if hasattr(chart.chart_type, "value") else str(chart.chart_type).upper()
                dim_str = chart.x_column or chart.dimension or "N/A"
                meas_str = ", ".join(chart.y_columns) if chart.y_columns else (chart.measure or "N/A")
                agg_str = chart.aggregation or "SUM"
                w = getattr(chart, "width", 6)
                h = getattr(chart, "height", 4)
                with chart_cols[ci % 2]:
                    st.markdown(f"""
                    <div class="sheet-card">
                        <span class="chart-pill">{chart_type_str}</span>
                        <b>{chart.title}</b><br>
                        <span style="font-size:0.85rem;color:#94a3b8;">
                            <b>Dimension:</b> {dim_str} | 
                            <b>Measure:</b> {meas_str} ({agg_str}) | 
                            <b>Grid:</b> {w}x{h}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_next = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to Preprocessing", use_container_width=True):
            go_to_step(3)
    with col_next:
        if st.button("Next: Python Preprocessing Script ➔", type="primary", use_container_width=True):
            go_to_step(5)


# =========================================================
# STEP 5: PYTHON CODE & OUTPUT (.py)
# =========================================================
elif cur == 5:
    run = st.session_state.pipeline_run
    if not run:
        st.warning("Please complete previous steps first.")
        st.stop()
        
    st.markdown("### 🐍 Step 5: Python Preprocessing Code & Output (.py)")
    st.caption("Standalone, reproducible Python script containing the exact code used to clean, profile, and transform the dataset.")
    
    for py_artifact in run.python_artifacts:
        st.markdown(f"#### 📜 `{py_artifact.filename}`")
        st.code(py_artifact.code, language="python")
        
        st.download_button(
            label=f"⬇️ Download {py_artifact.filename}",
            data=py_artifact.code,
            file_name=py_artifact.filename,
            mime="text/x-python",
            key=f"dl_step5_{py_artifact.filename}"
        )
        
        if py_artifact.output:
            st.markdown("**Script Execution Output / Log:**")
            st.code(py_artifact.output, language="text")
            
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_next = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to Sheets Blueprint", use_container_width=True):
            go_to_step(4)
    with col_next:
        if st.button("Next: SQL Queries & Outputs ➔", type="primary", use_container_width=True):
            go_to_step(6)


# =========================================================
# STEP 6: SQL QUERIES & OUTPUTS
# =========================================================
elif cur == 6:
    run = st.session_state.pipeline_run
    if not run:
        st.warning("Please complete previous steps first.")
        st.stop()
        
    st.markdown("### 🗄️ Step 6: SQL Code & Analytical Outputs")
    st.caption("DuckDB SQL analytical queries executed for summary metrics, top dimension rollups, and time-series trends.")
    
    all_sql_text = ""
    for idx, sql_art in enumerate(run.sql_artifacts, 1):
        st.markdown(f"#### Query {idx}: {sql_art.description}")
        st.code(sql_art.sql, language="sql")
        all_sql_text += f"-- {sql_art.description}\n{sql_art.sql}\n\n"
        
        if sql_art.rows and sql_art.columns:
            df_res = pd.DataFrame(sql_art.rows, columns=sql_art.columns)
            st.dataframe(df_res, use_container_width=True)
            st.caption(f"⏱️ Executed in {sql_art.execution_time_ms:.1f}ms • {sql_art.row_count} rows returned")
        st.divider()
        
    st.download_button(
        label="⬇️ Download All SQL Queries (.sql)",
        data=all_sql_text,
        file_name="dashforge_queries.sql",
        mime="text/plain",
        key="dl_step6_sql"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_next = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to Python Script", use_container_width=True):
            go_to_step(5)
    with col_next:
        if st.button("Next: Power BI, Tableau & Final Package ➔", type="primary", use_container_width=True):
            go_to_step(7)


# =========================================================
# STEP 7: INTERACTIVE DASHBOARD, REPLICATION BLUEPRINTS & PACKAGE DOWNLOAD
# =========================================================
elif cur == 7:
    run = st.session_state.pipeline_run
    if not run:
        st.warning("Please complete previous steps first.")
        st.stop()
        
    title_slug = run.dashboard_plan.dashboard_title.replace(" ", "_") if run.dashboard_plan else "Dashboard"
    st.markdown("### 🚀 Step 7: Interactive Dashboard & BI Replication Blueprints")
    st.caption("Interact with your standalone dashboard, download it as a self-contained HTML file, or use the step-by-step blueprints to replicate it in Power BI or Tableau.")
    
    # Standalone Dashboard Banner
    if getattr(run, "dashboard_html", None):
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, rgba(37,99,235,0.18) 0%, rgba(139,92,246,0.18) 100%);border:1px solid rgba(59,130,246,0.35);border-radius:14px;padding:22px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div>
                    <h3 style="margin:0;color:#ffffff;font-size:1.3rem;">✨ Standalone Interactive Dashboard Ready</h3>
                    <p style="margin:6px 0 0 0;color:#94a3b8;font-size:0.92rem;">
                        Fully self-contained interactive dashboard with multi-sheet tabs, KPIs, and hover tooltips. Open in any browser without needing Power BI or Tableau!
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.download_button(
            label=f"⬇️ Download Standalone Interactive Dashboard ({title_slug}_dashboard.html)",
            data=run.dashboard_html,
            file_name=f"{title_slug}_dashboard.html",
            mime="text/html",
            type="primary",
            use_container_width=True,
            key="dl_standalone_html"
        )
        st.markdown("<br>", unsafe_allow_html=True)

    tab_dash, tab_pbi, tab_tbl, tab_bundle = st.tabs([
        "📊 Live Interactive Dashboard",
        "🟡 Power BI Replication Blueprint",
        "🟠 Tableau Replication Blueprint",
        "🎁 1-Click Complete Project Bundle (ZIP)"
    ])

    with tab_dash:
        st.markdown("#### 📊 Live Interactive Dashboard")
        st.caption("Interact with dynamic charts, tooltips, and KPI cards across each generated sheet:")
        
        # 1. Native Interactive Plotly Sheet Tabs
        if run.dashboard_plan and run.dashboard_plan.sheets:
            sheet_titles = [s.title for s in run.dashboard_plan.sheets]
            sheet_tabs = st.tabs([f"📄 {t}" for t in sheet_titles])
            
            for s_idx, s_tab in enumerate(sheet_tabs):
                sheet_obj = run.dashboard_plan.sheets[s_idx]
                with s_tab:
                    st.markdown(f"**{sheet_obj.title}** — *{sheet_obj.description or 'Executive view'}*")
                    
                    # KPIs
                    kpis = run.sheet_kpis.get(sheet_obj.title, [])
                    if kpis:
                        kpi_cols = st.columns(len(kpis))
                        for ki, k in enumerate(kpis):
                            with kpi_cols[ki]:
                                st.metric(
                                    label=k.get("title", "Metric"),
                                    value=k.get("value", "-"),
                                    help=k.get("subtitle", "")
                                )
                        st.markdown("<hr style='margin:12px 0;border-color:rgba(148,163,184,0.15);'>", unsafe_allow_html=True)
                    
                    # Charts Grid
                    figs_info = getattr(run, "sheet_figures", {}).get(sheet_obj.title, [])
                    if figs_info:
                        for row_i in range(0, len(figs_info), 2):
                            row_cols = st.columns(2)
                            for c_i in range(2):
                                fig_idx = row_i + c_i
                                if fig_idx < len(figs_info):
                                    with row_cols[c_i]:
                                        fig_item = figs_info[fig_idx]
                                        st.plotly_chart(
                                            fig_item["figure"],
                                            use_container_width=True,
                                            key=f"native_chart_{s_idx}_{fig_idx}"
                                        )
                    else:
                        st.info("No charts generated for this sheet.")
                        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🌐 Preview Standalone Multi-Tab HTML Dashboard (As Exported)", expanded=False):
            if getattr(run, "dashboard_html", None):
                components.html(run.dashboard_html, height=750, scrolling=True)
            else:
                st.info("Interactive dashboard HTML was not generated.")

    with tab_pbi:
        st.markdown("#### 🟡 Power BI Desktop Replication Blueprint")
        st.caption("Use these production-ready assets and follow the guide to build the dashboard in Power BI Desktop in minutes.")
        
        if run.powerbi_package:
            pbi = run.powerbi_package
            st.success(f"✅ Generated {len(pbi.dax_measures)} DAX Measures + Tabular Model Schema (model.bim) + Power Query (M) Scripts!")
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.download_button("⬇️ measures.dax", pbi.dax_script, "measures.dax", "text/plain", use_container_width=True, key="dl_pbi_dax")
            with c2:
                st.download_button("⬇️ transform.m", pbi.m_script, "transform.m", "text/plain", use_container_width=True, key="dl_pbi_m")
            with c3:
                st.download_button("⬇️ model.bim", json.dumps(pbi.model_bim_json, indent=2), "model.bim", "application/json", use_container_width=True, key="dl_pbi_bim")
            with c4:
                st.download_button("⬇️ load_powerbi.py", pbi.python_connector_script, "load_powerbi.py", "text/x-python", use_container_width=True, key="dl_pbi_py")
                
            if getattr(pbi, "replication_guide", None):
                st.markdown("---")
                st.markdown(pbi.replication_guide)
            else:
                with st.expander("🔍 View DAX Script"):
                    st.code(pbi.dax_script, language="dax")
        else:
            st.info("Power BI was not selected as target.")

    with tab_tbl:
        st.markdown("#### 🟠 Tableau Replication Blueprint")
        st.caption("Use these calculated fields and sheet blueprints to replicate the dashboard in Tableau Desktop or Tableau Public.")
        
        if run.tableau_package:
            tbl = run.tableau_package
            st.success(f"✅ Generated {len(tbl.calculated_fields)} Calculated Fields + Sheet Placement Guide!")
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Download calculated_fields.txt",
                    tbl.calculated_fields_script or "\n".join(f"{c['name']} = {c['formula']}" for c in tbl.calculated_fields),
                    "calculated_fields.txt",
                    "text/plain",
                    use_container_width=True,
                    key="dl_tbl_txt"
                )
            with c2:
                st.download_button(
                    "⬇️ Download calculated_fields.json",
                    json.dumps(tbl.calculated_fields, indent=2),
                    "calculated_fields.json",
                    "application/json",
                    use_container_width=True,
                    key="dl_tbl_json"
                )
                
            if getattr(tbl, "replication_guide", None):
                st.markdown("---")
                st.markdown(tbl.replication_guide)
            else:
                with st.expander("🔍 View Calculated Fields"):
                    for cf in tbl.calculated_fields:
                        st.markdown(f"- **{cf.get('name')}**: `{cf.get('formula')}`")
        else:
            st.info("Tableau was not selected as target.")

    with tab_bundle:
        st.markdown("#### 🎁 1-Click Complete Project Bundle (ZIP)")
        st.caption("Contains the entire folder structure: `dashboard/dashboard.html`, `data/`, `powerbi/`, `tableau/`, `python/`, `sql/`, and `README.md`.")
        
        if run.output_folder:
            zip_bytes = packaging_agent.create_zip_bundle(run.output_folder)
            folder_name = Path(run.output_folder).name
            st.download_button(
                label=f"⬇️ Download Complete Package ({folder_name}.zip)",
                data=zip_bytes,
                file_name=f"{folder_name}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="dl_final_zip"
            )
            st.info(f"📁 Local folder path on disk: `{run.output_folder}`")
        
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_space, col_reset = st.columns([1, 2, 2])
    with col_back:
        if st.button("⬅ Back to SQL Code", use_container_width=True):
            go_to_step(6)
    with col_reset:
        if st.button("🔄 Start New Dataset / Project", use_container_width=True):
            st.session_state.pipeline_run = None
            st.session_state.uploaded_file_paths = []
            go_to_step(1)
