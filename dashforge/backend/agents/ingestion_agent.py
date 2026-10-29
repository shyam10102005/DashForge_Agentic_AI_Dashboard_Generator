"""
DashForge - Ingestion Agent
Handles multi-format dataset ingestion: CSV, XLSX, XLS, ZIP archives.
Extracts, identifies, and loads all tabular files into DuckDB.
"""
import os
import uuid
import zipfile
import shutil
import pandas as pd
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.database import db


class IngestionAgent:
    """Ingests datasets from various file formats (CSV, XLSX, ZIP)."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".tsv"}

    async def ingest(self, file_path: str, original_filename: str) -> list[dict]:
        """Ingest a file or archive and return list of loaded datasets.

        Args:
            file_path: Path to uploaded file.
            original_filename: Original filename from the upload.

        Returns:
            List of dicts with keys: dataset_id, filename, table_name, row_count, column_count
        """
        ext = Path(original_filename).suffix.lower()
        results = []

        if ext == ".zip":
            results = await self._ingest_zip(file_path, original_filename)
        elif ext in self.SUPPORTED_EXTENSIONS:
            result = await self._ingest_single_file(file_path, original_filename)
            results.append(result)
        else:
            raise ValueError(
                f"Unsupported file format: '{ext}'. "
                f"Supported: {', '.join(self.SUPPORTED_EXTENSIONS | {'.zip'})}"
            )

        return results

    async def _ingest_single_file(
        self,
        file_path: str,
        filename: str,
        dataset_id: str = None,
        table_name: str = None
    ) -> dict:
        """Load a single CSV/XLSX file into DuckDB."""
        if dataset_id is None:
            dataset_id = str(uuid.uuid4())[:12]

        ext = Path(filename).suffix.lower()
        stem = Path(filename).stem

        # Clean table name
        if table_name is None:
            table_name = self._clean_table_name(stem)

        # Read into DataFrame
        df = self._read_file(file_path, ext)

        # Load into DuckDB
        db.load_dataframe(dataset_id, df, table_name)

        return {
            "dataset_id": dataset_id,
            "filename": filename,
            "table_name": table_name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "file_path": file_path,
        }

    async def _ingest_zip(self, zip_path: str, original_filename: str) -> list[dict]:
        """Extract and ingest all supported files from a ZIP archive."""
        extract_dir = Path(settings.storage.upload_dir) / f"extracted_{uuid.uuid4().hex[:8]}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        results = []
        dataset_id = str(uuid.uuid4())[:12]  # Shared dataset_id for all files in the archive

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # Walk extracted directory for supported files
            for root, dirs, files in os.walk(extract_dir):
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    ext = fpath.suffix.lower()

                    if ext in self.SUPPORTED_EXTENSIONS and not fname.startswith("__"):
                        table_name = self._clean_table_name(fpath.stem)

                        # Copy to uploads dir
                        dest_path = Path(settings.storage.upload_dir) / f"{dataset_id}_{fname}"
                        shutil.copy2(str(fpath), str(dest_path))

                        result = await self._ingest_single_file(
                            str(dest_path), fname, dataset_id=dataset_id, table_name=table_name
                        )
                        results.append(result)

        finally:
            # Clean up extraction directory
            shutil.rmtree(extract_dir, ignore_errors=True)

        if not results:
            raise ValueError("ZIP archive contains no supported data files (CSV, XLSX, XLS, TSV).")

        return results

    def _read_file(self, file_path: str, ext: str) -> pd.DataFrame:
        """Read a file into a Pandas DataFrame based on extension."""
        if ext == ".csv":
            # Try multiple encodings
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            return pd.read_csv(file_path, encoding="utf-8", errors="replace")
        elif ext == ".tsv":
            return pd.read_csv(file_path, sep="\t")
        elif ext in (".xlsx", ".xls"):
            # Read all sheets into a single DataFrame or return the first
            xls = pd.ExcelFile(file_path)
            if len(xls.sheet_names) == 1:
                return pd.read_excel(file_path, sheet_name=0)
            else:
                # For multi-sheet Excel, concatenate or return first
                # We'll handle multi-sheet at the ingestion level
                return pd.read_excel(file_path, sheet_name=0)
        else:
            raise ValueError(f"Cannot read file with extension: {ext}")

    async def ingest_excel_sheets(
        self,
        file_path: str,
        original_filename: str,
        dataset_id: str = None
    ) -> list[dict]:
        """Ingest all sheets from a multi-sheet Excel file as separate tables."""
        if dataset_id is None:
            dataset_id = str(uuid.uuid4())[:12]

        xls = pd.ExcelFile(file_path)
        results = []

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if df.empty:
                continue

            table_name = self._clean_table_name(sheet_name)
            db.load_dataframe(dataset_id, df, table_name)

            results.append({
                "dataset_id": dataset_id,
                "filename": f"{original_filename} [{sheet_name}]",
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "file_path": file_path,
            })

        return results

    @staticmethod
    def _clean_table_name(name: str) -> str:
        """Sanitize a string into a valid SQL table name."""
        cleaned = name.strip().lower()
        cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in cleaned)
        # Ensure doesn't start with number
        if cleaned and cleaned[0].isdigit():
            cleaned = "t_" + cleaned
        # Avoid SQL reserved words
        reserved = {"select", "from", "where", "table", "index", "group", "order", "by", "insert", "update", "delete"}
        if cleaned in reserved:
            cleaned = "tbl_" + cleaned
        return cleaned or "dataset"


# Singleton
ingestion_agent = IngestionAgent()
