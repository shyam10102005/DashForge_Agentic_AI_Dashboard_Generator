"""
DashForge - Code Generator Agent
Generates Python preprocessing code and SQL scripts as exportable artifacts.
"""
from backend.models import (
    DatasetProfile, PreprocessingLog, SQLArtifact,
    PythonCodeArtifact, DashboardPlan
)


class CodeGeneratorAgent:
    """Generates Python and SQL code artifacts for the output package."""

    def generate_preprocessing_script(
        self,
        profiles: list[DatasetProfile],
        logs: list[PreprocessingLog],
    ) -> PythonCodeArtifact:
        """Generate a Python script that reproduces all preprocessing steps."""
        lines = [
            '"""',
            "DashForge - Data Preprocessing Script",
            "Auto-generated Python code to reproduce all cleaning & transformation steps.",
            '"""',
            "import pandas as pd",
            "import numpy as np",
            "import os",
            "",
            "# =============================================",
            "# Configuration",
            "# =============================================",
            "",
        ]

        for i, profile in enumerate(profiles):
            lines.extend([
                f"# Dataset {i+1}: {profile.filename}",
                f"FILE_{i} = r'{profile.filename}'  # Update with actual file path",
                "",
            ])

        lines.extend([
            "# =============================================",
            "# Load Datasets",
            "# =============================================",
            "",
        ])

        for i, profile in enumerate(profiles):
            ext = profile.filename.rsplit(".", 1)[-1].lower() if "." in profile.filename else "csv"
            if ext in ("xlsx", "xls"):
                lines.append(f"df_{profile.table_name} = pd.read_excel(FILE_{i})")
            else:
                lines.append(f"df_{profile.table_name} = pd.read_csv(FILE_{i})")
            lines.append(f'print(f"Loaded {{FILE_{i}}}: {{df_{profile.table_name}.shape[0]}} rows, {{df_{profile.table_name}.shape[1]}} columns")')
            lines.append("")

        lines.extend([
            "# =============================================",
            "# Data Profiling",
            "# =============================================",
            "",
        ])

        for profile in profiles:
            tbl = profile.table_name
            lines.extend([
                f"# --- Profile: {profile.filename} ---",
                f"print(f'\\n=== {profile.filename} ===')",
                f"print(f'Shape: {{df_{tbl}.shape}}')",
                f"print(f'Duplicates: {{df_{tbl}.duplicated().sum()}}')",
                f"print(f'\\nNull counts:')",
                f"print(df_{tbl}.isnull().sum())",
                f"print(f'\\nData types:')",
                f"print(df_{tbl}.dtypes)",
                f"print(f'\\nDescriptive statistics:')",
                f"print(df_{tbl}.describe())",
                "",
            ])

        lines.extend([
            "# =============================================",
            "# Preprocessing Steps",
            "# =============================================",
            "",
        ])

        if logs:
            for log in logs:
                lines.append(f"# Step: {log.step}")
                lines.append(f"# {log.description}")

                if log.step == "remove_duplicates":
                    lines.extend([
                        f"# Affected rows: {log.rows_affected}",
                        "for name, df in [" + ", ".join(
                            f'("{p.table_name}", df_{p.table_name})' for p in profiles
                        ) + "]:",
                        "    before = len(df)",
                        "    df = df.drop_duplicates()",
                        "    after = len(df)",
                        '    print(f"  {name}: Removed {before - after} duplicates")',
                        "",
                    ])
                elif log.step == "fill_null_median":
                    cols = log.columns_affected
                    for col in cols:
                        lines.extend([
                            f"# Fill nulls in '{col}' with median",
                            "for name, df in [" + ", ".join(
                                f'("{p.table_name}", df_{p.table_name})' for p in profiles
                            ) + "]:",
                            f'    if "{col}" in df.columns:',
                            f'        median_val = df["{col}"].median()',
                            f'        df["{col}"] = df["{col}"].fillna(median_val)',
                            f'        print(f"  {{name}}: Filled nulls in {col} with median {{median_val:.2f}}")',
                            "",
                        ])
                elif log.step == "fill_null_mode":
                    cols = log.columns_affected
                    for col in cols:
                        lines.extend([
                            f"# Fill nulls in '{col}' with mode",
                            "for name, df in [" + ", ".join(
                                f'("{p.table_name}", df_{p.table_name})' for p in profiles
                            ) + "]:",
                            f'    if "{col}" in df.columns:',
                            f'        mode_val = df["{col}"].mode()',
                            f'        fill_val = mode_val.iloc[0] if len(mode_val) > 0 else "Unknown"',
                            f'        df["{col}"] = df["{col}"].fillna(fill_val)',
                            f'        print(f"  {{name}}: Filled nulls in {col} with mode {{fill_val}}")',
                            "",
                        ])
                elif log.step == "drop_high_null_column":
                    cols = log.columns_affected
                    for col in cols:
                        lines.extend([
                            f"# Drop column '{col}' (too many nulls)",
                            "for name, df in [" + ", ".join(
                                f'("{p.table_name}", df_{p.table_name})' for p in profiles
                            ) + "]:",
                            f'    if "{col}" in df.columns:',
                            f'        df = df.drop(columns=["{col}"])',
                            f'        print(f"  {{name}}: Dropped column {col}")',
                            "",
                        ])
                elif log.step == "type_cast_date":
                    cols = log.columns_affected
                    for col in cols:
                        lines.extend([
                            f"# Convert '{col}' to datetime",
                            "for name, df in [" + ", ".join(
                                f'("{p.table_name}", df_{p.table_name})' for p in profiles
                            ) + "]:",
                            f'    if "{col}" in df.columns:',
                            f'        df["{col}"] = pd.to_datetime(df["{col}"], errors="coerce")',
                            f'        print(f"  {{name}}: Converted {col} to datetime")',
                            "",
                        ])
                elif log.step == "strip_whitespace":
                    cols = log.columns_affected
                    for col in cols:
                        lines.extend([
                            f"# Strip whitespace from '{col}'",
                            "for name, df in [" + ", ".join(
                                f'("{p.table_name}", df_{p.table_name})' for p in profiles
                            ) + "]:",
                            f'    if "{col}" in df.columns and df["{col}"].dtype == object:',
                            f'        df["{col}"] = df["{col}"].str.strip()',
                            "",
                        ])
                else:
                    lines.append(f"# (Custom step: {log.step})")
                    lines.append("")
        else:
            lines.append("# No preprocessing steps were needed - data was clean!")
            lines.append("")

        lines.extend([
            "# =============================================",
            "# Save Cleaned Datasets",
            "# =============================================",
            "",
            "output_dir = 'cleaned_data'",
            "os.makedirs(output_dir, exist_ok=True)",
            "",
        ])

        for profile in profiles:
            tbl = profile.table_name
            lines.extend([
                f"df_{tbl}.to_csv(os.path.join(output_dir, '{tbl}_cleaned.csv'), index=False)",
                f'print(f"Saved cleaned {tbl}: {{df_{tbl}.shape}}")',
                "",
            ])

        lines.append('print("\\n✅ Preprocessing complete!")')

        code = "\n".join(lines)

        # Generate output summary
        output_lines = []
        for profile in profiles:
            output_lines.append(f"Dataset: {profile.filename}")
            output_lines.append(f"  Rows: {profile.row_count:,} | Cols: {profile.column_count}")
            output_lines.append(f"  Quality Score: {profile.data_quality_score}%")
            output_lines.append(f"  Duplicates: {profile.duplicate_row_count}")
        output_lines.append(f"\nPreprocessing Steps Applied: {len(logs)}")
        for log in logs:
            output_lines.append(f"  - {log.step}: {log.description}")

        return PythonCodeArtifact(
            filename="preprocessing.py",
            description="Data preprocessing and cleaning script",
            code=code,
            output="\n".join(output_lines),
        )

    def generate_sql_script(
        self,
        profiles: list[DatasetProfile],
        sql_artifacts: list[SQLArtifact],
        plan: DashboardPlan,
    ) -> PythonCodeArtifact:
        """Generate a SQL script file with all executed queries."""
        lines = [
            "-- =============================================",
            f"-- DashForge SQL Queries",
            f"-- Dashboard: {plan.dashboard_title}",
            "-- =============================================",
            "",
        ]

        # Table info
        for profile in profiles:
            lines.extend([
                f"-- Table: {profile.table_name}",
                f"-- Source: {profile.filename}",
                f"-- Rows: {profile.row_count:,} | Columns: {profile.column_count}",
                "",
            ])

        lines.append("-- =============================================")
        lines.append("-- Queries")
        lines.append("-- =============================================")
        lines.append("")

        for i, artifact in enumerate(sql_artifacts):
            lines.extend([
                f"-- Query {i+1}: {artifact.description}",
                f"-- Status: {'✅ Success' if artifact.success else '❌ Failed'}",
                f"-- Rows returned: {artifact.row_count}",
                f"-- Execution time: {artifact.execution_time_ms:.1f}ms",
                artifact.sql + ";",
                "",
            ])

            if artifact.success and artifact.rows:
                lines.append(f"-- Results preview ({min(5, len(artifact.rows))} of {artifact.row_count} rows):")
                lines.append(f"-- Columns: {', '.join(artifact.columns)}")
                for row in artifact.rows[:5]:
                    lines.append(f"--   {row}")
                lines.append("")

            if artifact.error:
                lines.append(f"-- Error: {artifact.error}")
                lines.append("")

        sql_code = "\n".join(lines)

        # Output summary
        success_count = sum(1 for a in sql_artifacts if a.success)
        output = f"Total Queries: {len(sql_artifacts)}\nSuccessful: {success_count}\nFailed: {len(sql_artifacts) - success_count}"

        return PythonCodeArtifact(
            filename="queries.sql",
            description="All SQL queries used for dashboard data extraction",
            code=sql_code,
            output=output,
        )


# Singleton
codegen_agent = CodeGeneratorAgent()
