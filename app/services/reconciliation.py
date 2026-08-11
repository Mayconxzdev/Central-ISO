from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FileRecord
from .inventory import classify_inventory_error


def reconcile_inventory(db: Session, root: Path, output_dir: Path, powershell_total: int | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    backend_paths = set(db.scalars(select(FileRecord.path).where(FileRecord.is_present.is_(True))).all())
    backend_total = len(backend_paths)
    enumerated = set()
    inaccessible_directories: list[dict] = []
    transient_errors: list[dict] = []
    long_path_errors: list[str] = []
    ignored_entries: list[dict] = []

    def on_error(exc: OSError) -> None:
        item = {"path": getattr(exc, "filename", ""), "error": classify_inventory_error(exc)}
        inaccessible_directories.append(item)
        if item["error"] == "caminho longo":
            long_path_errors.append(item["path"])
        else:
            transient_errors.append(item)

    for dirpath, _, filenames in os.walk(root, onerror=on_error):
        for filename in filenames:
            path = str(Path(dirpath) / filename)
            enumerated.add(path)
            if filename.lower().endswith(".lnk"):
                ignored_entries.append({"path": path, "reason": "atalho"})
            if len(path) >= 240:
                long_path_errors.append(path)

    only_in_scan = sorted(enumerated - backend_paths)[:200]
    only_in_backend = sorted(backend_paths - enumerated)[:200]
    scan_total = len(enumerated)
    powershell_value = powershell_total if powershell_total is not None else scan_total
    explanation = (
        f"PowerShell informou {powershell_value} arquivo(s); o backend possui {backend_total} arquivo(s) presentes. "
        f"A enumeração de diagnóstico encontrou {scan_total} arquivo(s), {len(inaccessible_directories)} diretório(s) inacessível(is) "
        f"e {len(ignored_entries)} atalho(s). Diferenças podem vir de permissões, caminhos longos, atalhos, arquivos alterados durante a leitura ou métodos de enumeração distintos."
    )
    result = {
        "method": "python_os_walk_vs_backend_db",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "powershell_total": powershell_value,
        "backend_total": backend_total,
        "paths_only_in_powershell": only_in_scan,
        "paths_only_in_backend": only_in_backend,
        "inaccessible_directories": inaccessible_directories[:500],
        "transient_errors": transient_errors[:500],
        "long_path_errors": long_path_errors[:500],
        "ignored_entries": ignored_entries[:500],
        "explanation": explanation,
    }
    output = output_dir / f"inventory_reconciliation_{datetime.now():%Y%m%d_%H%M%S}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["output_path"] = str(output)
    return result
