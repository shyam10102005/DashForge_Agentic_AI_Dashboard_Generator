"""
DashForge - SQL Agent
Generates SQL queries for data extraction, aggregation, and analysis.
Executes queries against DuckDB and captures results.
"""
from typing import Optional

from backend.llm_service import llm
from backend.database import db
from backend.models import SQLArtifact, DatasetProfile, SheetPlan, ChartSpec


class SQLAgent:
    """Generates and executes SQL queries for dashboard data extraction."""

    SQL_GENERATION_PROMPT = """You are a SQL expert. Generate a DuckDB-compatible SQL query for the following request.

TABLE: {table_name}
SCHEMA:
{schema}

TASK: {task}

RULES:
1. Use only columns that exist in the schema.
2. Use proper aggregation with GROUP BY when needed.
3. Add ORDER BY for readability.
4. Limit results to 1000 rows max.
5. Use CAST for type conversions if needed.
6. Return ONLY the SQL query, no explanations.
7. Use single quotes for string literals."""

    async def generate_queries_for_plan(
        self,
        profiles: list[DatasetProfile],
        plan: 'DashboardPlan'
    ) -> list[SQLArtifact]:
        """Generate SQL queries for all charts in the dashboard plan."""
        artifacts = []

        for sheet in plan.sheets:
            # Find matching profile
            profile = next((p for p in profiles if p.dataset_id == sheet.dataset_id), None)
            if not profile:
                continue

            for chart in sheet.charts:
                query = await self._generate_chart_query(chart, sheet, profile)
                if query:
                    # Execute the query
                    result = db.execute_query(profile.dataset_id, query)
                    result.description = f"{sheet.title} → {chart.title}"
                    artifacts.append(result)

        return artifacts

    async def generate_exploration_queries(self, profile: DatasetProfile) -> list[SQLArtifact]:
        """Generate standard exploration SQL queries for a dataset."""
        table = profile.table_name
        queries = []

        # 1. Row count & basic stats
        queries.append(SQLArtifact(
            description="Record Count",
            sql=f"SELECT COUNT(*) AS total_records FROM {table}",
        ))

        # 2. Distinct counts for categorical columns
        for cat_col in profile.categorical_columns[:5]:
            queries.append(SQLArtifact(
                description=f"Distinct values in {cat_col}",
                sql=f"SELECT {cat_col}, COUNT(*) AS count FROM {table} GROUP BY {cat_col} ORDER BY count DESC LIMIT 20",
            ))

        # 3. Numeric summaries
        if profile.numeric_columns:
            agg_parts = []
            for nc in profile.numeric_columns[:6]:
                agg_parts.append(f"ROUND(SUM({nc}), 2) AS total_{nc}")
                agg_parts.append(f"ROUND(AVG({nc}), 2) AS avg_{nc}")
            queries.append(SQLArtifact(
                description="Numeric Column Summaries",
                sql=f"SELECT {', '.join(agg_parts)} FROM {table}",
            ))

        # 4. Date range
        for dc in profile.date_columns[:2]:
            queries.append(SQLArtifact(
                description=f"Date range for {dc}",
                sql=f"SELECT MIN({dc}) AS earliest, MAX({dc}) AS latest, COUNT(DISTINCT {dc}) AS distinct_dates FROM {table}",
            ))

        # Execute all queries
        executed = []
        for q in queries:
            result = db.execute_query(profile.dataset_id, q.sql)
            result.description = q.description
            executed.append(result)

        return executed

    async def _generate_chart_query(
        self,
        chart: ChartSpec,
        sheet: SheetPlan,
        profile: DatasetProfile
    ) -> Optional[str]:
        """Generate a SQL query for a specific chart specification."""
        table = sheet.table_name

        # For KPI cards - simple aggregation
        if chart.chart_type.value == "kpi_card":
            if chart.y_columns:
                col = chart.y_columns[0]
                agg = chart.aggregation
                return f"SELECT {agg}({col}) AS value FROM {table}"
            else:
                return f"SELECT COUNT(*) AS value FROM {table}"

        # For table charts - raw data
        if chart.chart_type.value == "table":
            cols = [chart.x_column] + chart.y_columns if chart.x_column else chart.y_columns
            cols = [c for c in cols if c]
            if not cols:
                cols = ["*"]
            return f"SELECT {', '.join(cols)} FROM {table} LIMIT 100"

        # Build query based on chart type
        x_col = chart.x_column
        y_cols = chart.y_columns
        agg = chart.aggregation
        color_col = chart.color_column

        if not x_col and not y_cols:
            return None

        # Construct SELECT, GROUP BY, ORDER BY
        select_parts = []
        group_parts = []

        if x_col:
            select_parts.append(x_col)
            group_parts.append(x_col)

        if color_col and color_col != x_col:
            select_parts.append(color_col)
            group_parts.append(color_col)

        for yc in y_cols:
            select_parts.append(f"{agg}({yc}) AS {yc}_{agg.lower()}")

        if not select_parts:
            return None

        sql = f"SELECT {', '.join(select_parts)} FROM {table}"

        if group_parts:
            sql += f" GROUP BY {', '.join(group_parts)}"

        # ORDER BY
        if chart.sort_by:
            sql += f" ORDER BY {chart.sort_by} DESC"
        elif y_cols:
            sql += f" ORDER BY {y_cols[0]}_{agg.lower()} DESC"

        # TOP N
        if chart.top_n:
            sql += f" LIMIT {chart.top_n}"
        else:
            sql += " LIMIT 100"

        return sql

    async def generate_custom_query(
        self,
        dataset_id: str,
        table_name: str,
        question: str,
        schema: list[dict]
    ) -> SQLArtifact:
        """Generate a SQL query from a natural language question using LLM."""
        schema_text = "\n".join([
            f"  - {col['column_name']} ({col['column_type']})"
            for col in schema
        ])

        prompt = self.SQL_GENERATION_PROMPT.format(
            table_name=table_name,
            schema=schema_text,
            task=question,
        )

        response = await llm.generate(
            prompt=prompt,
            system_prompt="You are a SQL expert. Return ONLY the SQL query, nothing else.",
            temperature=0.1,
        )

        # Clean the response
        sql = response.strip()
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()

        if sql.startswith("Error:"):
            return SQLArtifact(sql=sql, success=False, error=sql, description=question)

        # Execute
        result = db.execute_query(dataset_id, sql)
        result.description = question
        return result


# Singleton
sql_agent = SQLAgent()
