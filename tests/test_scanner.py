from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FileRecord
from app.services.scanner import scan_directory


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_scan_is_idempotent(tmp_path: Path):
    (tmp_path / "documento.txt").write_text("certificado de demonstração", encoding="utf-8")
    engine = make_engine()
    with Session(engine) as db:
        first = scan_directory(db, tmp_path, mode="full")
        second = scan_directory(db, tmp_path, mode="incremental")
        assert first.files_found == 1
        assert second.files_found == 1
        assert len(db.scalars(select(FileRecord)).all()) == 1
        record = db.scalar(select(FileRecord))
        assert record.extraction_status == "lido"
