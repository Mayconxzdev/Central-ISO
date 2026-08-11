from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Certificate, Nonconformity, PendingItem
from app.seed import prepare_initial_data


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_production_does_not_seed_demo_data():
    engine = make_engine()
    with Session(engine) as db:
        result = prepare_initial_data(db, "production")
        assert result["seeded_demo"] == 0
        assert db.scalars(select(Certificate)).all() == []
        assert db.scalars(select(Nonconformity)).all() == []


def test_demo_mode_seeds_demo_data():
    engine = make_engine()
    with Session(engine) as db:
        result = prepare_initial_data(db, "demo")
        assert result["seeded_demo"] == 1
        assert db.scalar(select(Certificate.id).limit(1)) is not None
        assert db.scalar(select(Nonconformity.id).limit(1)) is not None


def test_production_removes_only_confirmed_demo_records():
    engine = make_engine()
    with Session(engine) as db:
        real_certificate = Certificate(
            number="REAL-1",
            supplier="Fornecedor real",
            valid_until=date(2099, 1, 1),
            source_path=r"\\demo-server\quality-share\certificado.pdf",
        )
        demo_certificate = Certificate(
            number="DEMO-1",
            supplier="Fornecedor demo",
            valid_until=date(2020, 1, 1),
            source_path="demo_iso/Produto Ex/demo.csv",
        )
        demo_pending = PendingItem(
            kind="regra:certificado",
            title="Demo",
            source_path="demo_iso/Produto Ex/demo.csv",
        )
        db.add_all([real_certificate, demo_certificate, demo_pending])
        db.commit()

        result = prepare_initial_data(db, "production")

        assert result["certificates"] == 1
        assert result["pending_items"] == 1
        certificates = db.scalars(select(Certificate)).all()
        assert [cert.number for cert in certificates] == ["REAL-1"]
        assert db.scalars(select(PendingItem)).all() == []
