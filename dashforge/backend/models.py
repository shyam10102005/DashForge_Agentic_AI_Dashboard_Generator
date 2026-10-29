"""
DashForge - Pydantic Models
Structured data models for the full pipeline.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# =============================================
# Enums
# =============================================

class OutputTarget(str, Enum):
    POWERBI = "powerbi"
    TABLEAU = "tableau"
    BOTH = "both"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    PROFILING = "profiling"
    PREPROCESSING = "preprocessing"
    PLANNING = "planning"
    GENERATING_SQL = "generating_sql"
    GENERATING_DASHBOARDS = "generating_dashboards"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"


class ChartType(str, Enum):
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    WATERFALL = "waterfall"
    COMBO = "combo"
    KPI_CARD = "kpi_card"
    TABLE = "table"
    MAP = "map"


class ThemePreset(str, Enum):
    CORPORATE_BLUE = "corporate_blue"
    MODERN_DARK = "modern_dark"
    MIDNIGHT_DARK = "modern_dark"
    EMERALD_GROWTH = "earth_tones"
    SUNSET_CRIMSON = "vibrant"
    NORDIC_FROST = "minimal_light"
    VIBRANT_TECH = "vibrant"
    VIBRANT = "vibrant"
    MINIMAL_LIGHT = "minimal_light"
    EARTH_TONES = "earth_tones"
    CUSTOM = "custom"


THEME_PALETTES: dict[str, list[str]] = {
    ThemePreset.CORPORATE_BLUE: ["#2196F3", "#1976D2", "#0D47A1", "#42A5F5", "#90CAF9", "#64B5F6", "#1E88E5", "#BBDEFB"],
    "corporate_blue": ["#2196F3", "#1976D2", "#0D47A1", "#42A5F5", "#90CAF9", "#64B5F6", "#1E88E5", "#BBDEFB"],
    ThemePreset.MODERN_DARK: ["#00D4FF", "#7C4DFF", "#FF6B6B", "#4ECDC4", "#FFE66D", "#A8E6CF", "#38BDF8", "#F472B6"],
    "modern_dark": ["#00D4FF", "#7C4DFF", "#FF6B6B", "#4ECDC4", "#FFE66D", "#A8E6CF", "#38BDF8", "#F472B6"],
    ThemePreset.VIBRANT: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#E11D48", "#10B981"],
    "vibrant": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#E11D48", "#10B981"],
    ThemePreset.MINIMAL_LIGHT: ["#546E7A", "#78909C", "#90A4AE", "#B0BEC5", "#37474F", "#455A64", "#64748B", "#94A3B8"],
    "minimal_light": ["#546E7A", "#78909C", "#90A4AE", "#B0BEC5", "#37474F", "#455A64", "#64748B", "#94A3B8"],
    ThemePreset.EARTH_TONES: ["#2E7D32", "#388E3C", "#4CAF50", "#81C784", "#A5D6A7", "#1B5E20", "#10B981", "#059669"],
    "earth_tones": ["#2E7D32", "#388E3C", "#4CAF50", "#81C784", "#A5D6A7", "#1B5E20", "#10B981", "#059669"],
    "custom": ["#38BDF8", "#818CF8", "#C084FC", "#F472B6", "#34D399", "#FBBF24", "#60A5FA", "#A78BFA"],
}



# =============================================
# Column & Profile Models
# =============================================

class ColumnProfile(BaseModel):
    """Profiling info for a single column."""
    name: str
    dtype: str
    non_null_count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    sample_values: list[str] = Field(default_factory=list)
    is_numeric: bool = False
    is_date: bool = False
    is_categorical: bool = False
    min_val: Optional[str] = None
    max_val: Optional[str] = None
    mean_val: Optional[float] = None
    std_val: Optional[float] = None
    semantic_role: Optional[str] = None  # "revenue", "quantity", "date_order", etc.


class DatasetProfile(BaseModel):
    """Complete profile for a single dataset/table."""
    dataset_id: str
    filename: str
    table_name: str = "dataset"
    row_count: int = 0
    column_count: int = 0
    duplicate_row_count: int = 0
    columns: list[ColumnProfile] = Field(default_factory=list)
    data_quality_score: float = 0.0  # 0-100
    numeric_columns: list[str] = Field(default_factory=list)
    date_columns: list[str] = Field(default_factory=list)
    categorical_columns: list[str] = Field(default_factory=list)
    id_columns: list[str] = Field(default_factory=list)
    profiled_at: datetime = Field(default_factory=datetime.now)


class PreprocessingLog(BaseModel):
    """Log of all preprocessing steps applied."""
    step: str = "cleaning"  # e.g. "remove_duplicates", "fill_nulls", "type_cast"
    step_type: str = "Data Cleaning"
    description: str = ""
    dataset_id: str = ""
    rows_before: int = 0
    rows_after: int = 0
    rows_affected: int = 0
    columns_affected: list[str] = Field(default_factory=list)
    before_value: Optional[str] = None
    after_value: Optional[str] = None


# =============================================
# Dashboard Planning Models
# =============================================

class ChartSpec(BaseModel):
    """Specification for a single chart/visual on a dashboard sheet."""
    chart_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    chart_type: ChartType = ChartType.BAR
    title: str = ""
    description: str = ""
    x_column: Optional[str] = None
    y_columns: list[str] = Field(default_factory=list)
    color_column: Optional[str] = None
    aggregation: str = "SUM"  # SUM, COUNT, AVG, MIN, MAX
    filters: list[str] = Field(default_factory=list)
    sort_by: Optional[str] = None
    top_n: Optional[int] = None
    width: int = 6
    height: int = 4
    dimension: Optional[str] = None
    measure: Optional[str] = None
    format_string: str = "#,##0"


class SheetPlan(BaseModel):
    """Plan for a single dashboard sheet/page."""
    sheet_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    target_audience: str = "Leadership & Analysts"
    sheet_order: int = 1
    dataset_id: str = ""  # Which dataset this sheet uses
    table_name: str = "dataset"
    charts: list[ChartSpec] = Field(default_factory=list)
    kpis: list[Any] = Field(default_factory=list)


class DashboardPlan(BaseModel):
    """Complete dashboard blueprint with multiple sheets."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    dashboard_title: str = "Dashboard"
    subtitle: str = "Executive Analytical Report"
    business_problem: str = "Provide holistic visibility into performance KPIs, regional trends, and category distribution."
    theme: ThemePreset = ThemePreset.CORPORATE_BLUE
    custom_colors: list[str] = Field(default_factory=list)
    sheets: list[SheetPlan] = Field(default_factory=list)
    target: OutputTarget = OutputTarget.BOTH

    @property
    def theme_colors(self) -> list[str]:
        if self.custom_colors:
            return self.custom_colors
        return THEME_PALETTES.get(self.theme, THEME_PALETTES["corporate_blue"])


# =============================================
# SQL & Code Artifacts
# =============================================

class SQLArtifact(BaseModel):
    """A generated SQL query and its result."""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    sql: str
    success: bool = True
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class PythonCodeArtifact(BaseModel):
    """Generated Python preprocessing/analysis code."""
    filename: str
    description: str
    code: str
    output: str = ""


class DAXMeasure(BaseModel):
    """A single DAX measure definition."""
    name: str
    expression: str
    format_string: str = "#,##0.00"
    description: str = ""


class PowerQueryStep(BaseModel):
    """A Power Query M transformation step."""
    step_name: str
    m_code: str
    description: str = ""


# =============================================
# Export / Output Artifacts
# =============================================

class PowerBIPackage(BaseModel):
    """All Power BI assets for the dashboard."""
    model_config = {"protected_namespaces": ()}

    dax_measures: list[DAXMeasure] = Field(default_factory=list)
    power_query_steps: list[PowerQueryStep] = Field(default_factory=list)
    model_bim_json: dict = Field(default_factory=dict)
    python_connector_script: str = ""
    dax_script: str = ""
    m_script: str = ""
    replication_guide: str = ""
    pbit_bytes: Optional[bytes] = None
    pbix_filename: str = "Dashboard.pbit"


class TableauPackage(BaseModel):
    """All Tableau assets for the dashboard."""
    calculated_fields: list[dict] = Field(default_factory=list)
    calculated_fields_script: str = ""
    datasource_info: dict = Field(default_factory=dict)
    replication_guide: str = ""
    twb_xml: str = ""  # Deprecated
    tds_xml: str = ""  # Deprecated


# =============================================
# Pipeline Run (Top-Level)
# =============================================

class PipelineEvent(BaseModel):
    """Record of a pipeline step execution."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    step: str
    status: str = "running"  # running, success, failure, skipped
    message: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


class PipelineRun(BaseModel):
    """Complete pipeline run capturing all inputs, intermediate artifacts, and outputs."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: PipelineStatus = PipelineStatus.PENDING
    target: OutputTarget = OutputTarget.BOTH
    theme: ThemePreset = ThemePreset.CORPORATE_BLUE
    custom_colors: list[str] = Field(default_factory=list)

    # Datasets
    datasets: list[DatasetProfile] = Field(default_factory=list)

    # Preprocessing
    preprocessing_logs: list[PreprocessingLog] = Field(default_factory=list)

    # Dashboard plan
    dashboard_plan: Optional[DashboardPlan] = None

    # Live & Standalone Dashboard
    dashboard_html: str = ""
    sheet_kpis: dict = Field(default_factory=dict)
    sheet_figures: dict = Field(default_factory=dict)

    # SQL artifacts
    sql_artifacts: list[SQLArtifact] = Field(default_factory=list)

    # Python code
    python_artifacts: list[PythonCodeArtifact] = Field(default_factory=list)

    # Power BI package
    powerbi_package: Optional[PowerBIPackage] = None

    # Tableau package
    tableau_package: Optional[TableauPackage] = None

    # Events / audit trail
    events: list[PipelineEvent] = Field(default_factory=list)

    # Output folder path
    output_folder: Optional[str] = None

    # Timestamps
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
