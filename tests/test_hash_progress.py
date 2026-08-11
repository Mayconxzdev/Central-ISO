from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FileRecord
from app.services.hash_progress import pause_hashing, resume_hashing, run_progressive_hash


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def add_file(db: Session, path: Path):
    stat = path.stat()
    db.add(
        FileRecord(
            path=str(path),
            name=path.name,
            extension=path.suffix.lower(),
            size_bytes=stat.st_size,
            sha256="",
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            extraction_status="pendente",
        )
    )


def test_progressive_hash_only_hashes_duplicate_size_candidates(tmp_path: Path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"
    a.write_text("same", encoding="utf-8")
    b.write_text("copy", encoding="utf-8")
    c.write_text("unique-size", encoding="utf-8")
    engine = make_engine()
    with Session(engine) as db:
        for path in (a, b, c):
            add_file(db, path)
        db.commit()

        result = run_progressive_hash(db, tmp_path, batch_size=25, large_file_mb=1, delay_ms=0)
        rows = db.scalars(select(FileRecord).order_by(FileRecord.name)).all()

    assert result["processed"] == 2
    assert rows[0].sha256
    assert rows[1].sha256
    assert rows[2].sha256 == ""


def test_hash_pause_and_resume_checkpoint(tmp_path: Path):
    paused = pause_hashing(tmp_path)
    assert paused.status == "paused"
    resumed = resume_hashing(tmp_path)
    assert resumed.status == "idle"
