from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.services.inventory import run_inventory
from app.services.scanner import scan_directory
from app.database import Base, SessionLocal, engine
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch):
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ISO_SOURCE_PATH", str(Path("./demo_iso").resolve()))
    Base.metadata.create_all(bind=engine)
    yield
    os.close(db_fd)
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass


def test_scanner_does_not_write_to_source(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha", encoding="utf-8")
    (src / "b.txt").write_text("beta", encoding="utf-8")

    with SessionLocal() as db:
        scan_directory(db, src, mode="full")

    assert (src / "a.txt").exists()
    assert set(p.name for p in src.iterdir()) == {"a.txt", "b.txt"}


def test_inventory_reads_without_extraction(tmp_path: Path):
    from sqlalchemy import text

    src = tmp_path / "src"
    src.mkdir()
    (src / "r.txt").write_text("alice", encoding="utf-8")
    (src / "s.txt").write_text("bob", encoding="utf-8")

    with SessionLocal() as db:
        run_inventory(db, src, batch_size=10)

    with SessionLocal() as db:
        rows = db.execute(text("SELECT name, extraction_status FROM files WHERE is_present = 1")).all()
        names = {r[0] for r in rows}
        assert names == {"r.txt", "s.txt"}
        for r in rows:
            assert r[1] == "pendente"


def test_api_inventory_endpoints_are_accessible():
    resp = client.get("/api/v1/inventory/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files" in data


def test_path_traversal_blocked():
    resp = client.get("/api/v1/evidence", params={"path": "../../etc/passwd"})
    assert resp.status_code in (403, 400, 404)
