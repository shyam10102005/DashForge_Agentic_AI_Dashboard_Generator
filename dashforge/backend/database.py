"""
DashForge - Database Manager
Handles multi-dataset DuckDB analytics and SQL execution.
"""
import hashlib
import time
import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional
from backend.config import settings
from backend.models import SQLArtifact


class DatabaseManager:
    """Manages DuckDB connections for analytical data and query execution."""

    def __init__(self):
        self._connections: dict[str, duckdb.DuckDBPyConnection] = {}
        self._table_names: dict[str, list[str]] = {}  # dataset_id -> list of table names
        self._dataframes: dict[str, pd.DataFrame] = {}  # table_key -> DataFrame

    def load_dataframe(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        table_name: str = "dataset"
    ) -> str:
        """Load a DataFrame into DuckDB as a named table.

        Args:
            dataset_id: Unique identifier for the dataset group.
            df: Pandas DataFrame to load.
            table_name: Table name in DuckDB.

        Returns:
            The table name used.
        """
        # Clean column names
        df.columns = [
            col.strip().replace(" ", "_").replace(".", "_").replace("-", "_").replace("(", "").replace(")", "")
            for col in df.columns
        ]

        if dataset_id not in self._connections:
            self._connections[dataset_id] = duckdb.connect()
            self._table_names[dataset_id] = []

        conn = self._connections[dataset_id]

        # Drop existing table if exists
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        except Exception:
            pass

        conn.register("df_temp", df)
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_temp")
        conn.unregister("df_temp")

        if table_name not in self._table_names[dataset_id]:
            self._table_names[dataset_id].append(table_name)

        self._dataframes[f"{dataset_id}_{table_name}"] = df

        return table_name

    def get_schema(self, dataset_id: str, table_name: str = "dataset") -> list[dict]:
        """Get the schema of a loaded table."""
        conn = self._get_connection(dataset_id)
        result = conn.execute(f"DESCRIBE {table_name}").fetchall()
        return [
            {"column_name": row[0], "column_type": row[1]}
            for row in result
        ]

    def execute_query(self, dataset_id: str, query: str) -> SQLArtifact:
        """Execute a read-only SQL query safely."""
        conn = self._get_connection(dataset_id)

        # Security: Block dangerous SQL
        query_upper = query.upper().strip()
        blocked = [
            "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
            "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
            "ATTACH", "DETACH", "COPY", "INSTALL", "LOAD"
        ]
        for kw in blocked:
            if kw in query_upper.split():
                return SQLArtifact(
                    sql=query,
                    success=False,
                    error=f"Blocked: '{kw}' statements are not permitted."
                )

        start_time = time.time()
        try:
            result = conn.execute(query)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            if len(rows) > 10000:
                rows = rows[:10000]
            exec_ms = (time.time() - start_time) * 1000

            return SQLArtifact(
                sql=query,
                success=True,
                columns=columns,
                rows=[list(row) for row in rows],
                row_count=len(rows),
                execution_time_ms=round(exec_ms, 2)
            )
        except Exception as e:
            exec_ms = (time.time() - start_time) * 1000
            return SQLArtifact(
                sql=query,
                success=False,
                error=str(e),
                execution_time_ms=round(exec_ms, 2)
            )

    def get_sample_data(self, dataset_id: str, table_name: str = "dataset", limit: int = 10) -> dict:
        """Get sample rows from a table."""
        conn = self._get_connection(dataset_id)
        result = conn.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return {"columns": columns, "rows": [list(row) for row in rows]}

    def get_dataframe(self, dataset_id: str, table_name: str = "dataset") -> pd.DataFrame:
        """Get the full dataset as a DataFrame."""
        key = f"{dataset_id}_{table_name}"
        if key in self._dataframes:
            return self._dataframes[key].copy()
        conn = self._get_connection(dataset_id)
        return conn.execute(f"SELECT * FROM {table_name}").fetchdf()

    def get_table_names(self, dataset_id: str) -> list[str]:
        """Get all table names for a dataset group."""
        return self._table_names.get(dataset_id, [])

    def close(self, dataset_id: str):
        """Close a dataset connection."""
        if dataset_id in self._connections:
            self._connections[dataset_id].close()
            del self._connections[dataset_id]
            # Clean up table names and dataframes
            tables = self._table_names.pop(dataset_id, [])
            for t in tables:
                self._dataframes.pop(f"{dataset_id}_{t}", None)

    def compute_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_connection(self, dataset_id: str) -> duckdb.DuckDBPyConnection:
        if dataset_id not in self._connections:
            raise ValueError(f"Dataset '{dataset_id}' not loaded.")
        return self._connections[dataset_id]


# Singleton
db = DatabaseManager()
