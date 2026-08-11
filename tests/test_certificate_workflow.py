from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AutomationEvent, Certificate, FileRecord, PendingItem
from app.services.certificate_workflow import run_certificate_workflow
from app.services.rules import apply_rules
from app.services.structured_sync import sync_structured_records


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_certificate_workflow_creates_renewal_and_decision():
    engine = make_engine()
    with Session(engine) as db:
        db.add(
            Certificate(
                number="CPEx DEMO-0001X",
                supplier="FABRICANTE DEMO A",
                component_or_product="Painel elétrico Ex",
                valid_until=date(2026, 2, 6),
                source_path=r"\\demo-server\quality-share\CERTIFICADO\04 - PAINEL ELÉTRICO FABRICANTE DEMO A - CPEx DEMO-0001X Rev 00 - 06-02-2026.pdf",
            )
        )
        db.commit()
        stats = run_certificate_workflow(db, today=date(2026, 6, 22))
        assert stats["renewal_requests"] >= 1
        assert stats["decisions_needed"] >= 1
        pending = db.scalars(select(PendingItem).where(PendingItem.resolved.is_(False))).all()
        assert any(item.kind == "fluxo:certificado" for item in pending)
        assert any(item.kind == "decisão:certificado" for item in pending)
        events = db.scalars(select(AutomationEvent)).all()
        assert any(event.event_type == "certificado_solicitacao" for event in events)


def test_structured_sync_from_scanned_certificate_file():
    engine = make_engine()
    with Session(engine) as db:
        db.add(
            FileRecord(
                path=r"\\demo-server\quality-share\Produto Ex\04 - PAINEL ELÉTRICO FABRICANTE DEMO A - CPEx DEMO-0001X Rev 00 - 06-02-2026.pdf",
                name="04 - PAINEL ELÉTRICO FABRICANTE DEMO A - CPEx DEMO-0001X Rev 00 - 06-02-2026.pdf",
                extension=".pdf",
                size_bytes=1000,
                sha256="abc123",
                category="certificado",
                extraction_status="lido",
                extracted_text="Certificado CPEx DEMO-0001X validade 06-02-2026 fabricante FABRICANTE DEMO A",
            )
        )
        db.commit()
        stats = sync_structured_records(db)
        assert stats["certificates_created"] == 1
        cert = db.scalar(select(Certificate))
        assert cert.number == "CPEx DEMO-0001X"
        apply_rules(db)
        pending = db.scalars(select(PendingItem)).all()
        assert len(pending) >= 1


def test_rules_do_not_flood_on_unreadable_non_priority_files():
    engine = make_engine()
    with Session(engine) as db:
        for index in range(40):
            db.add(
                FileRecord(
                    path=rf"\\demo-server\quality-share\temp\arquivo_{index}.pdf",
                    name=f"arquivo_{index}.pdf",
                    extension=".pdf",
                    size_bytes=100,
                    sha256=f"hash-{index}",
                    category="documento",
                    extraction_status="sem texto — OCR necessário",
                    extracted_text="",
                )
            )
        db.commit()
        apply_rules(db)
        pending = db.scalars(select(PendingItem)).all()
        assert len(pending) <= 25
