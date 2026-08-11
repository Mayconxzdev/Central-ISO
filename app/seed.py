from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Certificate, HumanNote, Nonconformity, PendingItem, RoleAssignment


DEMO_SOURCE_PREFIX = "demo_iso"


def is_demo_source(source_path: str | None) -> bool:
    if not source_path:
        return False
    normalized = source_path.replace("\\", "/").lower().lstrip("./")
    return normalized.startswith(DEMO_SOURCE_PREFIX)


def remove_demo_data(db: Session) -> dict[str, int]:
    demo_certificates = db.scalars(select(Certificate).where(Certificate.source_path.like("%demo_iso%"))).all()
    demo_ncs = db.scalars(select(Nonconformity).where(Nonconformity.source_path.like("%demo_iso%"))).all()
    demo_pending = db.scalars(select(PendingItem).where(PendingItem.source_path.like("%demo_iso%"))).all()
    demo_pending_ids = [item.id for item in demo_pending]
    removed = {
        "certificates": len(demo_certificates),
        "nonconformities": len(demo_ncs),
        "pending_items": len(demo_pending),
        "human_notes": 0,
        "role_assignments": 0,
    }
    if demo_pending_ids:
        notes = db.scalars(select(HumanNote).where(HumanNote.pending_item_id.in_(demo_pending_ids))).all()
        removed["human_notes"] = len(notes)
        for note in notes:
            db.delete(note)
    for item in demo_pending:
        db.delete(item)
    for cert in demo_certificates:
        db.delete(cert)
    for nc in demo_ncs:
        db.delete(nc)

    role_assignments = db.scalars(select(RoleAssignment)).all()
    removed["role_assignments"] = len(role_assignments)
    for assignment in role_assignments:
        db.delete(assignment)
    db.commit()
    return removed


def prepare_initial_data(db: Session, mode: str) -> dict[str, int]:
    if mode == "demo":
        seed_demo(db)
        return {"seeded_demo": 1}
    removed = remove_demo_data(db)
    removed["seeded_demo"] = 0
    return removed


def seed_demo(db: Session) -> None:
    if db.scalar(select(Certificate.id).limit(1)) is None:
        db.add_all(
            [
                Certificate(
                    number="CPEx DEMO-0001X",
                    supplier="FABRICANTE DEMO A",
                    component_or_product="Caixa de passagem Ex",
                    valid_until=date(2026, 2, 6),
                    use_status="uso não confirmado",
                    source_path="demo_iso/Produto Ex/Lista_de_certificados_demo.csv",
                    notes="Validade encontrada em relatório interno. Confirmar uso atual e certificado substituto.",
                ),
                Certificate(
                    number="TÜV DEMO-0002X",
                    supplier="FABRICANTE DEMO B",
                    component_or_product="Componente Ex",
                    valid_until=date(2026, 2, 6),
                    use_status="uso não confirmado",
                    source_path="demo_iso/Produto Ex/Lista_de_certificados_demo.csv",
                    notes="Exemplo de certificado vencido para demonstração do painel.",
                ),
                Certificate(
                    number="DNV DEMO-0003X",
                    supplier="FABRICANTE DEMO C",
                    component_or_product="Motor elétrico Ex",
                    valid_until=date(2025, 12, 10),
                    use_status="uso não confirmado",
                    source_path="demo_iso/Produto Ex/Lista_de_certificados_demo.csv",
                    notes="Confirmar se existe renovação e quais produtos/OPs utilizam o componente.",
                ),
                Certificate(
                    number="CPEx DEMO-0004X",
                    supplier="FABRICANTE DEMO D",
                    component_or_product="Plugues e tomadas Ex",
                    valid_until=date(2027, 11, 29),
                    status="vigente",
                    use_status="em uso",
                    source_path="demo_iso/Produto Ex/Lista_de_certificados_demo.csv",
                    notes="Certificado de produto localizado; documentação ISO do fornecedor deve ser verificada separadamente.",
                ),
            ]
        )

    if db.scalar(select(Nonconformity.id).limit(1)) is None:
        db.add_all(
            [
                Nonconformity(
                    code="NC 001/2026",
                    area="RH",
                    origin="Auditoria externa",
                    description="Evidências de treinamentos não localizadas.",
                    root_cause="Falha no arquivamento das listas de presença.",
                    action="Reprogramar treinamentos e registrar evidências.",
                    responsible_role="Responsável por RH",
                    due_date=date(2026, 4, 30),
                    status="encerrada",
                    evidence_found=True,
                    effectiveness_verified=True,
                    source_path="demo_iso/NCs/NC_001_2026.txt",
                ),
                Nonconformity(
                    code="NC 002/2026",
                    area="Compras",
                    origin="Auditoria externa",
                    description="Fornecedor crítico sem avaliação semestral e documentação incompleta.",
                    root_cause="Ausência de rotina consolidada de reavaliação.",
                    action="Aplicar avaliação e solicitar documentos faltantes.",
                    responsible_role="Responsável por Compras",
                    due_date=date(2026, 5, 30),
                    status="ação concluída",
                    evidence_found=True,
                    effectiveness_verified=False,
                    source_path="demo_iso/NCs/NC_002_2026.txt",
                ),
                Nonconformity(
                    code="NC 004/2026",
                    area="Projetos / Produção",
                    origin="Auditoria externa",
                    description="Processo de solda sem formalização completa do teste final.",
                    root_cause="Controles executados sem registro único e formal.",
                    action="Formalizar método de validação e evidência no procedimento.",
                    responsible_role="Responsável por Projetos + Qualidade",
                    due_date=date(2026, 7, 15),
                    status="em análise",
                    evidence_found=False,
                    effectiveness_verified=False,
                    source_path="demo_iso/NCs/NC_004_2026.txt",
                ),
                Nonconformity(
                    code="NC 005/2026",
                    area="Comercial",
                    origin="Auditoria externa",
                    description="Pesquisa de satisfação cliente externo inacessível pelo portal do cliente.",
                    root_cause="Dependência de acesso e retorno externo.",
                    action="Acompanhar chamado e ampliar pesquisa para outros clientes.",
                    responsible_role="Responsável Comercial",
                    due_date=date(2026, 6, 30),
                    status="em análise",
                    evidence_found=True,
                    effectiveness_verified=False,
                    source_path="demo_iso/NCs/NC_005_2026.txt",
                ),
            ]
        )

    if db.scalar(select(RoleAssignment.id).limit(1)) is None:
        db.add_all(
            [
                RoleAssignment(
                    operational_role="Gestor da Qualidade",
                    person_name="Pessoa Demo A",
                    department="Qualidade",
                    start_date=date(2025, 1, 2),
                    substitute_role="Direção designada",
                ),
                RoleAssignment(
                    operational_role="Responsável por Produto Ex",
                    person_name="Função a confirmar",
                    department="Produto Ex / Projetos",
                    start_date=date(2026, 1, 1),
                    substitute_role="Gestor da Qualidade",
                ),
                RoleAssignment(
                    operational_role="Responsável por Compras",
                    person_name="Pessoa Demo B",
                    department="Compras",
                    start_date=date(2025, 1, 1),
                    substitute_role="Comprador substituto",
                ),
            ]
        )
    db.commit()
