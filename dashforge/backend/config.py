"""
DashForge - Configuration Module
Centralized configuration management.
"""
import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class OllamaConfig(BaseModel):
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")


class AppConfig(BaseModel):
    name: str = os.getenv("APP_NAME", "DashForge")
    version: str = os.getenv("APP_VERSION", "1.0.0")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"


class FileConfig(BaseModel):
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
    max_row_count: int = int(os.getenv("MAX_ROW_COUNT", "2000000"))


class StorageConfig(BaseModel):
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "data" / "output")))
    db_dir: Path = Path(os.getenv("DB_DIR", str(BASE_DIR / "data" / "db")))

    def ensure_dirs(self):
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)


class Settings:
    def __init__(self):
        self.ollama = OllamaConfig()
        self.app = AppConfig()
        self.file = FileConfig()
        self.storage = StorageConfig()
        self.agent_timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))
        self.storage.ensure_dirs()


settings = Settings()
