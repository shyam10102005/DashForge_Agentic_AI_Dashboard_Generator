"""
DashForge - Profiler Agent
Profiles datasets: schema analysis, null/duplicate detection, type inference,
semantic role detection, and data quality scoring.
"""
import pandas as pd
import numpy as np
from typing import Optional

from backend.database import db
from backend.models import DatasetProfile, ColumnProfile, PreprocessingLog


class ProfilerAgent:
    """Profiles and preprocesses datasets."""

    async def profile(self, dataset_id: str, table_name: str = "dataset", filename: str = "") -> DatasetProfile:
        """Generate a comprehensive data profile for a table."""
        df = db.get_dataframe(dataset_id, table_name)

        columns = []
        numeric_cols = []
        date_cols = []
        categorical_cols = []
        id_cols = []

        for col_name in df.columns:
            series = df[col_name]
            dtype_str = str(series.dtype)

            # Null analysis
            non_null = int(series.count())
            null_count = int(series.isna().sum())
            null_pct = round((null_count / len(df)) * 100, 2) if len(df) > 0 else 0.0
            unique_count = int(series.nunique())

            # Type detection
            is_numeric = pd.api.types.is_numeric_dtype(series)
            is_date = False

            # Try date detection for object columns (fast pre-check)
            if not is_numeric and series.dtype == object:
                col_lower = col_name.lower()
                is_candidate = any(k in col_lower for k in ["date", "time", "year", "month", "day", "created", "updated"])
                sample_non_null = series.dropna().head(10)
                if not is_candidate and len(sample_non_null) > 0:
                    # Check if sample strings look like dates (e.g. 2024-01-01, 01/01/2024)
                    sample_str = str(sample_non_null.iloc[0]).strip()
                    is_candidate = bool(len(sample_str) >= 8 and any(sep in sample_str for sep in ["-", "/", "."]) and any(ch.isdigit() for ch in sample_str))

                if is_candidate:
                    try:
                        parsed = pd.to_datetime(sample_non_null, errors="coerce", format="mixed")
                        if parsed.notna().sum() > len(sample_non_null) * 0.7:
                            is_date = True
                    except Exception:
                        pass

            is_categorical = (
                not is_numeric and not is_date
                and unique_count <= max(50, len(df) * 0.3)
            )

            # Stats for numeric columns
            min_val = max_val = mean_val = std_val = None
            if is_numeric:
                min_val = str(series.min()) if not series.isna().all() else None
                max_val = str(series.max()) if not series.isna().all() else None
                mean_val = float(series.mean()) if not series.isna().all() else None
                std_val = float(series.std()) if not series.isna().all() else None
                numeric_cols.append(col_name)
            elif is_date:
                date_cols.append(col_name)
            elif is_categorical:
                categorical_cols.append(col_name)

            # Sample values
            non_null_vals = series.dropna().head(5).astype(str).tolist()

            # Semantic role detection
            semantic_role = self._detect_semantic_role(col_name, is_numeric, is_date, unique_count, len(df))

            if semantic_role == "id":
                id_cols.append(col_name)

            columns.append(ColumnProfile(
                name=col_name,
                dtype=dtype_str,
                non_null_count=non_null,
                null_count=null_count,
                null_pct=null_pct,
                unique_count=unique_count,
                sample_values=non_null_vals,
                is_numeric=is_numeric,
                is_date=is_date,
                is_categorical=is_categorical,
                min_val=min_val,
                max_val=max_val,
                mean_val=mean_val,
                std_val=std_val,
                semantic_role=semantic_role,
            ))

        # Duplicate detection
        duplicate_count = int(df.duplicated().sum())

        # Data quality score
        quality_score = self._compute_quality_score(df, columns)

        return DatasetProfile(
            dataset_id=dataset_id,
            filename=filename,
            table_name=table_name,
            row_count=len(df),
            column_count=len(df.columns),
            duplicate_row_count=duplicate_count,
            columns=columns,
            data_quality_score=quality_score,
            numeric_columns=numeric_cols,
            date_columns=date_cols,
            categorical_columns=categorical_cols,
            id_columns=id_cols,
        )

    async def preprocess(self, dataset_id: str, table_name: str = "dataset") -> list[PreprocessingLog]:
        """Run automated data preprocessing and return a log of all changes."""
        df = db.get_dataframe(dataset_id, table_name)
        logs = []

        # 1. Remove exact duplicate rows
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            df = df.drop_duplicates()
            logs.append(PreprocessingLog(
                step="remove_duplicates",
                description=f"Removed {dup_count} exact duplicate rows",
                rows_affected=dup_count,
            ))

        # 2. Handle null values
        for col in df.columns:
            null_count = int(df[col].isna().sum())
            if null_count == 0:
                continue

            null_pct = null_count / len(df) * 100

            if null_pct > 70:
                # Too many nulls – drop the column
                df = df.drop(columns=[col])
                logs.append(PreprocessingLog(
                    step="drop_high_null_column",
                    description=f"Dropped column '{col}' with {null_pct:.1f}% null values",
                    rows_affected=null_count,
                    columns_affected=[col],
                ))
            elif pd.api.types.is_numeric_dtype(df[col]):
                # Fill numeric nulls with median
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logs.append(PreprocessingLog(
                    step="fill_null_median",
                    description=f"Filled {null_count} nulls in '{col}' with median ({median_val:.2f})",
                    rows_affected=null_count,
                    columns_affected=[col],
                    after_value=str(round(median_val, 2)),
                ))
            else:
                # Fill categorical nulls with mode or "Unknown"
                mode_val = df[col].mode()
                fill_val = mode_val.iloc[0] if len(mode_val) > 0 else "Unknown"
                df[col] = df[col].fillna(fill_val)
                logs.append(PreprocessingLog(
                    step="fill_null_mode",
                    description=f"Filled {null_count} nulls in '{col}' with mode ('{fill_val}')",
                    rows_affected=null_count,
                    columns_affected=[col],
                    after_value=str(fill_val),
                ))

        # 3. Type casting - attempt to convert date-like object columns (fast pre-filtered)
        for col in df.select_dtypes(include=["object"]).columns:
            col_lower = col.lower()
            is_date_candidate = any(k in col_lower for k in ["date", "time", "year", "month", "day", "created", "updated"])
            sample_non_null = df[col].dropna().head(10)
            if not is_date_candidate and len(sample_non_null) > 0:
                s_val = str(sample_non_null.iloc[0]).strip()
                is_date_candidate = bool(len(s_val) >= 8 and any(sep in s_val for sep in ["-", "/", "."]) and any(ch.isdigit() for ch in s_val))

            if is_date_candidate:
                try:
                    parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                    if parsed.notna().sum() > len(df) * 0.7:
                        df[col] = parsed
                        logs.append(PreprocessingLog(
                            step="type_cast_date",
                            description=f"Converted '{col}' from string to datetime",
                            columns_affected=[col],
                        ))
                except Exception:
                    pass

        # 4. Strip whitespace from string columns
        for col in df.select_dtypes(include=["object"]).columns:
            original = df[col].copy()
            df[col] = df[col].str.strip()
            changed = (original != df[col]).sum()
            if changed > 0:
                logs.append(PreprocessingLog(
                    step="strip_whitespace",
                    description=f"Stripped leading/trailing whitespace from '{col}'",
                    rows_affected=int(changed),
                    columns_affected=[col],
                ))

        # Reload the cleaned DataFrame into DuckDB
        db.load_dataframe(dataset_id, df, table_name)

        return logs

    def _detect_semantic_role(
        self, col_name: str, is_numeric: bool, is_date: bool,
        unique_count: int, row_count: int
    ) -> Optional[str]:
        """Detect the semantic role of a column based on its name and properties."""
        name_lower = col_name.lower()

        # ID columns
        if name_lower in ("id", "uuid", "key") or name_lower.endswith("_id"):
            return "id"
        if is_numeric and unique_count == row_count:
            return "id"

        # Date columns
        if is_date or any(kw in name_lower for kw in ("date", "time", "timestamp", "created", "updated")):
            return "date"

        # Revenue / Sales
        if any(kw in name_lower for kw in ("revenue", "sales", "amount", "total", "price", "cost")):
            return "revenue"

        # Quantity
        if any(kw in name_lower for kw in ("quantity", "qty", "count", "units", "volume")):
            return "quantity"

        # Profit / Margin
        if any(kw in name_lower for kw in ("profit", "margin", "gain", "loss")):
            return "profit"

        # Discount
        if any(kw in name_lower for kw in ("discount", "rebate")):
            return "discount"

        # Category
        if any(kw in name_lower for kw in ("category", "type", "class", "segment", "group", "region", "state", "country", "city")):
            return "category"

        # Name
        if any(kw in name_lower for kw in ("name", "title", "label", "description", "product", "customer", "employee")):
            return "name"

        return None

    def _compute_quality_score(self, df: pd.DataFrame, columns: list[ColumnProfile]) -> float:
        """Compute a data quality score from 0-100."""
        if len(df) == 0 or len(columns) == 0:
            return 0.0

        total_cells = len(df) * len(columns)
        total_nulls = sum(c.null_count for c in columns)
        completeness = (1 - total_nulls / total_cells) * 100 if total_cells > 0 else 100

        dup_penalty = min(30, (df.duplicated().sum() / len(df)) * 100) if len(df) > 0 else 0

        score = completeness - dup_penalty
        return round(max(0, min(100, score)), 1)


# Singleton
profiler_agent = ProfilerAgent()
