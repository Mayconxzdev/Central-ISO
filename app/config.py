from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Central ISO"
    app_data_mode: str = os.getenv("APP_DATA_MODE", "demo")
    maintenance_mode: bool = os.getenv("APP_MAINTENANCE_MODE", "false").lower() in {"1", "true", "yes", "on"}
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./central_iso_demo.db")
    ai_mode: str = os.getenv("AI_MODE", "disabled")
    external_document_parsing: str = os.getenv("EXTERNAL_DOCUMENT_PARSING", "disabled")
    external_multimodal_provider: str = os.getenv("EXTERNAL_MULTIMODAL_PROVIDER", "disabled")
    external_multimodal_model: str = os.getenv("EXTERNAL_MULTIMODAL_MODEL", "")
    protected_file_password: str = os.getenv("ISO_PROTECTED_FILE_PASSWORD", "")
    hash_mode: str = os.getenv("HASH_MODE", "progressive")
    hash_batch_size: int = int(os.getenv("HASH_BATCH_SIZE", "25"))
    hash_max_concurrency: int = int(os.getenv("HASH_MAX_CONCURRENCY", "2"))
    hash_large_file_mb: int = int(os.getenv("HASH_LARGE_FILE_MB", "500"))
    hash_delay_ms: int = int(os.getenv("HASH_DELAY_MS", "250"))
    environment: str = os.getenv("APP_ENV", "development")
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8877"))
    local_data_dir: Path = Path(
        os.getenv("CENTRAL_ISO_LOCAL_DIR", str(Path.home() / "AppData" / "Local" / "CentralISO"))
    )

    @property
    def iso_share_path(self) -> Path:
        configured = os.getenv("ISO_SOURCE_PATH", os.getenv("ISO_SHARE_PATH"))
        if configured:
            return Path(configured).resolve()
        if self.app_data_mode == "demo":
            return Path("./demo_iso").resolve()
        return Path(r"\\demo-server\quality-share").resolve()


settings = Settings()
