from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FileRecord
from .scanner import _now, sha256_file


@dataclass
class HashCheckpoint:
    status: str = "idle"
    processed: int = 0
    total: int = 0
    errors: int = 0
    deferred: int = 0
    bytes_read: int = 0
    message: str = ""


def checkpoint_path(local_data_dir: Path) -> Path:
    path = local_data_dir / "runtime" / "hash_checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_checkpoint(local_data_dir: Path) -> HashCheckpoint:
    path = checkpoint_path(local_data_dir)
    if not path.exists():
        return HashCheckpoint()
    try:
        return HashCheckpoint(**json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return HashCheckpoint(status="error", message="Checkpoint invalido")


def write_checkpoint(local_data_dir: Path, checkpoint: HashCheckpoint) -> None:
    checkpoint_path(local_data_dir).write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")


def pause_hashing(local_data_dir: Path) -> HashCheckpoint:
    checkpoint = read_checkpoint(local_data_dir)
    checkpoint.status = "paused"
    checkpoint.message = "Pausado pelo operador."
    write_checkpoint(local_data_dir, checkpoint)
    return checkpoint


def resume_hashing(local_data_dir: Path) -> HashCheckpoint:
    checkpoint = read_checkpoint(local_data_dir)
    checkpoint.status = "idle"
    checkpoint.message = "Pronto para retomar."
    write_checkpoint(local_data_dir, checkpoint)
    return checkpoint


def candidate_files(db: Session, large_file_bytes: int) -> list[FileRecord]:
    rows = db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
    by_size: dict[int, list[FileRecord]] = {}
    for record in rows:
        if record.size_bytes and record.size_bytes <= large_file_bytes:
            by_size.setdefault(record.size_bytes, []).append(record)
    candidates: list[FileRecord] = []
    for same_size in by_size.values():
        if len(same_size) > 1:
            candidates.extend(record for record in same_size if not record.sha256)
    return sorted(candidates, key=lambda record: (record.size_bytes, record.path))


def run_progressive_hash(
    db: Session,
    local_data_dir: Path,
    batch_size: int = 25,
    large_file_mb: int = 500,
    delay_ms: int = 250,
) -> dict:
    checkpoint = read_checkpoint(local_data_dir)
    if checkpoint.status == "paused":
        return asdict(checkpoint)

    large_file_bytes = large_file_mb * 1024 * 1024
    candidates = candidate_files(db, large_file_bytes)
    checkpoint = HashCheckpoint(status="running", total=len(candidates), message="Hash progressivo em execucao.")
    write_checkpoint(local_data_dir, checkpoint)

    for record in candidates[:batch_size]:
        checkpoint = read_checkpoint(local_data_dir)
        if checkpoint.status in {"paused", "cancelled"}:
            write_checkpoint(local_data_dir, checkpoint)
            return asdict(checkpoint)
        try:
            record.sha256 = sha256_file(Path(record.path))
            record.last_scanned_at = _now()
            checkpoint.processed += 1
            checkpoint.bytes_read += record.size_bytes or 0
        except Exception as exc:  # noqa: BLE001
            record.extraction_status = "falha"
            record.last_error = f"hash: {exc}"
            checkpoint.errors += 1
        db.commit()
        write_checkpoint(local_data_dir, checkpoint)
        if delay_ms:
            time.sleep(delay_ms / 1000)

    remaining = max(len(candidates) - checkpoint.processed, 0)
    checkpoint.status = "completed" if remaining == 0 else "partial"
    checkpoint.message = "Hash progressivo concluido." if remaining == 0 else f"{remaining} candidato(s) restantes."
    write_checkpoint(local_data_dir, checkpoint)
    return asdict(checkpoint)
