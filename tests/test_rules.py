from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Certificate, Nonconformity, PendingItem
from app.services.rules import apply_rules, certificate_status


def make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_certificate_status_boundaries():
    today = date(2026, 6, 19)
    assert certificate_status(date(2026, 6, 18), today) == "vencido"
    assert certificate_status(date(2026, 7, 10), today) == "vence em 30 dias"
    assert certificate_status(date(2026, 8, 10), today) == "vence em 60 dias"
    assert certificate_status(date(2027, 1, 1), today) == "vigente"


def test_nc_action_completed_without_effectiveness_creates_critical_pending():
    engine = make_engine()
    with Session(engine) as db:
        db.add(
            Nonconformity(
                code="NC TESTE",
                area="Compras",
                status="ação concluída",
                effectiveness_verified=False,
                responsible_role="Responsável por Compras",
                description="Teste",
                due_date=date(2099, 1, 1),
            )
        )
        db.commit()
        apply_rules(db)
        pending = db.scalars(select(PendingItem)).all()
        assert any("eficácia não verificada" in item.title for item in pending)
        assert any(item.severity == "crítico" for item in pending)


def test_expired_certificate_does_not_declare_product_nonconforming():
    engine = make_engine()
    with Session(engine) as db:
        db.add(
            Certificate(
                number="CERT-1",
                supplier="Fornecedor",
                component_or_product="Componente Ex",
                valid_until=date(2020, 1, 1),
            )
        )
        db.commit()
        apply_rules(db)
        item = db.scalar(select(PendingItem).where(PendingItem.kind == "regra:certificado"))
        assert item is not None
        assert "não conclui sozinho" in item.risk
        assert item.status == "aguardando confirmação"
