from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from .scanner import _now
from .paths import filesystem_path
from .file_types import extension_category, normalize_extension
from ..models import FileRecord, ScanRun

UTC = timezone.utc


def _chunked(iterable: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def classify_inventory_error(exc: BaseException) -> str:
    winerror = getattr(exc, "winerror", None)
    if winerror == 206:
        return "caminho longo"
    if isinstance(exc, PermissionError):
        return "acesso negado"
    if isinstance(exc, FileNotFoundError):
        return "arquivo inacessivel"
    if isinstance(exc, TimeoutError):
        return "timeout"

    message = str(exc).lower()
    if "network" in message or "rede" in message or "unreachable" in message:
        return "falha de rede"
    if "path too long" in message or ("caminho" in message and "longo" in message):
        return "caminho longo"
    if "being used" in message or "em uso" in message:
        return "arquivo em uso"
    if "invalid" in message or "invalido" in message:
        return "nome invalido"
    return "erro desconhecido"


def run_inventory(db: Session, root: Path, batch_size: int = 250) -> ScanRun:
    run = ScanRun(mode="inventory", status="running", message=f"Inventario de metadados em {root}")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        if not root.exists() or not root.is_dir():
            run.status = "failed"
            run.message = f"Pasta indisponivel: {root}"
            run.finished_at = _now()
            db.commit()
            return run

        all_paths: list[str] = []
        walk_errors = 0

        def on_walk_error(exc: OSError) -> None:
            nonlocal walk_errors
            walk_errors += 1

        for dirpath, _, filenames in os.walk(root, onerror=on_walk_error):
            for filename in filenames:
                all_paths.append(str(Path(dirpath) / filename))

        run.files_found = len(all_paths)
        run.files_failed = walk_errors
        db.commit()

        processed = 0
        failed = walk_errors
        for batch in _chunked(all_paths, batch_size):
            for path_str in batch:
                path = Path(path_str)
                try:
                    stat = os.stat(filesystem_path(path_str))
                    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                    existing = db.scalar(select(FileRecord).where(FileRecord.path == path_str))
                    if existing is None:
                        existing = FileRecord(
                            path=path_str,
                            name=path.name,
                            extension=normalize_extension(path.name),
                            size_bytes=stat.st_size,
                            sha256="",
                            modified_at=modified_at,
                            extraction_status="pendente",
                            extracted_text="",
                        )
                        db.add(existing)
                    else:
                        existing.name = path.name
                        existing.extension = normalize_extension(path.name)
                        existing.size_bytes = stat.st_size
                        existing.modified_at = modified_at
                        existing.is_present = True
                        existing.last_error = None
                        if existing.extraction_status == "falha" and not existing.extracted_text:
                            existing.extraction_status = "pendente"
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    error_kind = classify_inventory_error(exc)
                    existing = db.scalar(select(FileRecord).where(FileRecord.path == path_str))
                    if existing is None:
                        existing = FileRecord(
                            path=path_str,
                            name=path.name,
                            extension=normalize_extension(path.name),
                            size_bytes=0,
                            sha256="",
                            extraction_status="falha",
                            extracted_text="",
                        )
                        db.add(existing)
                    existing.extraction_status = "falha"
                    existing.last_error = f"{error_kind}: {exc}"
                    existing.last_scanned_at = _now()
            db.commit()

        known_paths = set(all_paths)
        for record in db.scalars(select(FileRecord)).all():
            if record.path not in known_paths:
                record.is_present = False

        db.commit()

        run.files_processed = processed
        run.files_failed = failed
        run.status = "completed_with_warnings" if failed else "completed"
        run.message = "Inventario de metadados concluido. Nenhum hash foi recalculado nesta etapa."

    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.message = f"Inventario falhou: {exc}"

    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run


def get_inventory_summary(db: Session, root: Path) -> dict:
    rows = db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
    total_files = len(rows)
    by_ext: dict[str, int] = {}
    by_category: dict[str, int] = {}
    total_size = 0
    for r in rows:
        extension = r.extension or "(sem extensao)"
        by_ext[extension] = by_ext.get(extension, 0) + 1
        category = extension_category(extension)
        by_category[category] = by_category.get(category, 0) + 1
        total_size += r.size_bytes or 0
    errors = db.scalars(
        select(FileRecord).where(FileRecord.is_present.is_(True), FileRecord.extraction_status == "falha")
    ).all()
    duplicates: dict[str, list[str]] = {}
    for r in rows:
        if r.sha256:
            duplicates.setdefault(r.sha256, []).append(r.path)
    dup_groups = {h: ps for h, ps in duplicates.items() if len(ps) > 1}
    return {
        "path": str(root),
        "total_files": total_files,
        "by_extension": by_ext,
        "by_type_category": by_category,
        "total_size_bytes": total_size,
        "errors_count": len(errors),
        "duplicates_count": len(dup_groups),
    }


def get_extension_report(db: Session, limit: int = 100) -> dict:
    rows = db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
    grouped: dict[str, dict] = {}
    for record in rows:
        ext = record.extension or "sem extensao"
        item = grouped.setdefault(
            ext,
            {
                "extension": ext,
                "category": extension_category(ext),
                "count": 0,
                "examples": [],
                "folders": [],
            },
        )
        item["count"] += 1
        if len(item["examples"]) < 3:
            item["examples"].append(record.name)
        folder = str(Path(record.path).parent)
        if folder not in item["folders"] and len(item["folders"]) < 3:
            item["folders"].append(folder)
    values = sorted(grouped.values(), key=lambda item: (-item["count"], item["extension"]))
    return {
        "top": values[:limit],
        "rare": [item for item in values if item["count"] <= 2][:limit],
        "total_types": len(values),
    }
