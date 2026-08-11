from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FileRecord, ScanRun
from .extractors import extract_text
from .file_types import normalize_extension
from .paths import filesystem_path

UTC = timezone.utc
SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".odt", ".txt", ".csv", ".md", ".log"}


def _now() -> datetime:
    return datetime.now(UTC)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(filesystem_path(path), "rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def classify(path: Path, text: str = "") -> str:
    haystack = f"{path.as_posix()} {text[:2500]}".lower()
    mapping = [
        (("rq-tnc", "não conformidade", "nao conformidade"), "não conformidade"),
        (("certificado", "cpex", "dnv ", "tüv", "tuv ", "dsg"), "certificado"),
        (("auditoria", "rq-rai", "rq-pra"), "auditoria"),
        (("rq-rac", "análise crítica", "analise critica"), "RAC"),
        (("rq-mac", "matriz de competências", "matriz de competencias"), "competência"),
        (("treinamento", "curso", "lista de presença"), "treinamento"),
        (("fornecedor", "rq-gcm", "rq-caf"), "fornecedor"),
        (("calibra", "rq-gic", "instrumento"), "calibração"),
        (("pq-", "procedimento"), "procedimento"),
        (("it-", "instrução de trabalho", "instrucao de trabalho"), "instrução de trabalho"),
        (("manual", "mq-"), "manual"),
    ]
    for needles, category in mapping:
        if any(needle in haystack for needle in needles):
            return category
    return "documento"


def scan_directory(db: Session, root: Path, mode: str = "incremental") -> ScanRun:
    run = ScanRun(mode=mode, status="running", message=f"Varredura em {root}")
    db.add(run)
    db.commit()
    db.refresh(run)

    if not root.exists() or not root.is_dir():
        run.status = "failed"
        run.message = f"Pasta indisponível: {root}"
        run.finished_at = _now()
        db.commit()
        return run

    found_paths: set[str] = set()
    files_found = files_processed = files_failed = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        files_found += 1
        resolved = str(path.resolve())
        found_paths.add(resolved)
        try:
            stat = os.stat(filesystem_path(path))
            digest = sha256_file(path)
            existing = db.scalar(select(FileRecord).where(FileRecord.path == resolved))
            should_extract = existing is None or existing.sha256 != digest or mode == "full"
            if existing is None:
                existing = FileRecord(
                    path=resolved,
                    name=path.name,
                    extension=normalize_extension(path.name),
                    size_bytes=stat.st_size,
                    sha256=digest,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
                db.add(existing)
            else:
                existing.name = path.name
                existing.extension = normalize_extension(path.name)
                existing.size_bytes = stat.st_size
                existing.sha256 = digest
                existing.modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                existing.is_present = True

            if should_extract:
                text, status = extract_text(path)
                existing.extracted_text = text if not text.startswith("ERRO:") else ""
                existing.extraction_status = status
                existing.last_error = text if text.startswith("ERRO:") else None
                existing.category = classify(path, existing.extracted_text)
                files_processed += 1
                if status in {"falha", "protegido", "formato não suportado"}:
                    files_failed += 1
            existing.last_scanned_at = _now()
            db.flush()
        except Exception as exc:  # noqa: BLE001
            files_failed += 1
            db.rollback()
            existing = db.scalar(select(FileRecord).where(FileRecord.path == resolved))
            if existing:
                existing.extraction_status = "falha"
                existing.last_error = str(exc)
                existing.last_scanned_at = _now()
                db.commit()

    for record in db.scalars(select(FileRecord)).all():
        if record.path not in found_paths:
            record.is_present = False

    run.files_found = files_found
    run.files_processed = files_processed
    run.files_failed = files_failed
    run.status = "completed_with_warnings" if files_failed else "completed"
    run.message = "Varredura concluída. Nenhum arquivo oficial foi alterado."
    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run
