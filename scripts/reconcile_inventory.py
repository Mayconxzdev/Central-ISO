from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.services.reconciliation import reconcile_inventory


if __name__ == "__main__":
    with SessionLocal() as db:
        result = reconcile_inventory(db, settings.iso_share_path, Path("logs"), powershell_total=86380)
    print(result["output_path"])
