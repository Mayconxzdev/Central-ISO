from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AutomationEvent, Certificate, PendingItem
from .rules import certificate_status, severity_for_certificate


RENEWAL_LEAD_DAYS = 90
ESCALATION_DAYS = 14


def _log_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_key: str,
    message: str,
    level: str = "info",
    metadata: str = "",
) -> AutomationEvent:
    event = AutomationEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_key=entity_key,
        message=message,
        level=level,
        details=metadata,
    )
    db.add(event)
    return event


def _pending_by_key(db: Session, rule_key: str) -> PendingItem | None:
    return db.scalar(
        select(PendingItem).where(PendingItem.rule_key == rule_key, PendingItem.resolved.is_(False))
    )


def _upsert_pending(
    db: Session,
    *,
    rule_key: str,
    kind: str,
    title: str,
    area: str,
    severity: str,
    status: str,
    description: str,
    risk: str,
    responsible_role: str,
    due_date: date | None,
    source_path: str,
    source_excerpt: str = "",
) -> PendingItem:
    existing = _pending_by_key(db, rule_key)
    if existing:
        existing.title = title
        existing.area = area
        existing.severity = severity
        existing.status = status
        existing.description = description
        existing.risk = risk
        existing.responsible_role = responsible_role
        existing.due_date = due_date
        existing.source_path = source_path
        existing.source_excerpt = source_excerpt
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return existing

    item = PendingItem(
        rule_key=rule_key,
        kind=kind,
        title=title,
        area=area,
        severity=severity,
        status=status,
        description=description,
        risk=risk,
        responsible_role=responsible_role,
        due_date=due_date,
        source_path=source_path,
        source_excerpt=source_excerpt,
    )
    db.add(item)
    return item


def run_certificate_workflow(db: Session, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    stats = {
        "certificates_checked": 0,
        "renewal_requests": 0,
        "escalations": 0,
        "auto_resolved": 0,
        "decisions_needed": 0,
    }

    for cert in db.scalars(select(Certificate)).all():
        stats["certificates_checked"] += 1
        status = certificate_status(cert.valid_until, today)
        cert.status = status
        rule_base = f"cert:{cert.number}"

        if status == "vigente":
            for suffix in ("solicitacao", "escalonamento", "decisao"):
                item = _pending_by_key(db, f"{rule_base}:{suffix}")
                if item:
                    item.resolved = True
                    item.status = "resolvido automaticamente"
                    stats["auto_resolved"] += 1
                    _log_event(
                        db,
                        event_type="certificado_resolvido",
                        entity_type="certificate",
                        entity_key=cert.number,
                        message=f"Certificado {cert.number} voltou a vigente ou permanece válido.",
                    )
            continue

        if status in {"validade não encontrada", "aguardando confirmação"}:
            _upsert_pending(
                db,
                rule_key=f"{rule_base}:decisao",
                kind="decisão:certificado",
                title=f"Confirmar validade do certificado {cert.number}",
                area="Produto Ex / Qualidade",
                severity="atenção",
                status="aguardando confirmação",
                description=(
                    f"O certificado {cert.number} foi localizado, mas a validade não pôde ser confirmada "
                    f"automaticamente com confiança suficiente."
                ),
                risk="Sem validade confirmada, o uso do componente Ex pode exigir revisão humana.",
                responsible_role="Responsável por Produto Ex / Qualidade",
                due_date=None,
                source_path=cert.source_path,
                source_excerpt=cert.notes,
            )
            stats["decisions_needed"] += 1
            continue

        days_left = (cert.valid_until - today).days if cert.valid_until else 999
        if days_left <= RENEWAL_LEAD_DAYS:
            request = _upsert_pending(
                db,
                rule_key=f"{rule_base}:solicitacao",
                kind="fluxo:certificado",
                title=f"Solicitar renovação — {cert.number}",
                area="Produto Ex / Qualidade",
                severity=severity_for_certificate(status),
                status="aguardando resposta",
                description=(
                    f"Certificado {cert.number} ({cert.supplier or 'fornecedor não identificado'}) "
                    f"com situação '{status}'. A Central ISO preparou cobrança automática ao fornecedor."
                ),
                risk="Componente Ex pode ficar irregular se a renovação não for obtida a tempo.",
                responsible_role="Responsável por Produto Ex / Qualidade",
                due_date=cert.valid_until,
                source_path=cert.source_path,
                source_excerpt=cert.notes,
            )
            already_logged = db.scalar(
                select(AutomationEvent.id)
                .where(
                    AutomationEvent.event_type == "certificado_solicitacao",
                    AutomationEvent.entity_key == cert.number,
                )
                .limit(1)
            )
            if not already_logged:
                stats["renewal_requests"] += 1
                _log_event(
                    db,
                    event_type="certificado_solicitacao",
                    entity_type="certificate",
                    entity_key=cert.number,
                    message=(
                        f"Solicitação automática registrada para {cert.supplier or 'fornecedor'} "
                        f"sobre certificado {cert.number}."
                    ),
                    metadata=cert.source_path,
                )
            _ = request

        if cert.valid_until and cert.valid_until < today - timedelta(days=ESCALATION_DAYS):
            _upsert_pending(
                db,
                rule_key=f"{rule_base}:escalonamento",
                kind="fluxo:certificado",
                title=f"Escalonamento — {cert.number} sem resposta",
                area="Produto Ex / Qualidade",
                severity="crítico",
                status="aguardando confirmação",
                description=(
                    f"O certificado {cert.number} está vencido há mais de {ESCALATION_DAYS} dias "
                    f"e não houve substituto confirmado."
                ),
                risk="Risco de uso de componente Ex com certificação irregular.",
                responsible_role="Responsável por Produto Ex / Qualidade",
                due_date=cert.valid_until,
                source_path=cert.source_path,
            )
            stats["escalations"] += 1
            _log_event(
                db,
                event_type="certificado_escalonamento",
                entity_type="certificate",
                entity_key=cert.number,
                message=f"Escalonamento automático do certificado {cert.number}.",
                level="warning",
            )

        if status == "vencido":
            _upsert_pending(
                db,
                rule_key=f"{rule_base}:decisao",
                kind="decisão:certificado",
                title=f"Decidir uso do certificado vencido {cert.number}",
                area="Produto Ex / Qualidade",
                severity="crítico",
                status="aguardando confirmação",
                description=(
                    f"Certificado {cert.number} vencido. O sistema já cobrou renovação; "
                    f"confirme se há substituto, estoque ou impacto em produção."
                ),
                risk="Decisão técnica necessária antes de liberar componente ou produto Ex.",
                responsible_role="Responsável por Produto Ex / Qualidade",
                due_date=cert.valid_until,
                source_path=cert.source_path,
                source_excerpt=cert.notes,
            )
            stats["decisions_needed"] += 1

    db.commit()
    return stats
