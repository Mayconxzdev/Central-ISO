from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FileRecord
from app.services.reconciliation import reconcile_inventory


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_reconciliation_writes_required_json(tmp_path: Path):
    root = tmp_path / "iso"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    engine = make_engine()
    with Session(engine) as db:
        db.add(FileRecord(path=str(root / "a.txt"), name="a.txt", extension=".txt", sha256="", size_bytes=1))
        db.commit()
        result = reconcile_inventory(db, root, tmp_path / "logs", powershell_total=1)

    assert result["powershell_total"] == 1
    assert result["backend_total"] == 1
    assert "paths_only_in_powershell" in result
    assert "paths_only_in_backend" in result
    assert "inaccessible_directories" in result
    assert "long_path_errors" in result
    assert Path(result["output_path"]).exists()
    assert result["explanation"]
