from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Certificate, FileRecord, Nonconformity, PendingItem
from .file_filters import is_noise_file, is_priority_document

DOCUMENT_ALERT_LIMIT = 25
DUPLICATE_ALERT_LIMIT = 10
NC_STATUSES_NEEDING_ROOT_CAUSE = {"em análise", "ação concluída", "aguardando eficácia"}


def certificate_status(valid_until: date | None, today: date | None = None) -> str:
    today = today or date.today()
    if valid_until is None:
        return "validade não encontrada"
    delta = (valid_until - today).days
    if delta < 0:
        return "vencido"
    if delta <= 30:
        return "vence em 30 dias"
    if delta <= 60:
        return "vence em 60 dias"
    if delta <= 90:
        return "vence em 90 dias"
    if delta <= 180:
        return "vence em 180 dias"
    return "vigente"


def severity_for_certificate(status: str) -> str:
    if status == "vencido":
        return "crítico"
    if status.startswith("vence em"):
        return "atenção"
    if status in {"validade não encontrada", "aguardando confirmação"}:
        return "atenção"
    return "informativo"


def _upsert_rule_item(db: Session, *, rule_key: str, **fields) -> PendingItem:
    existing = db.scalar(
        select(PendingItem).where(PendingItem.rule_key == rule_key, PendingItem.resolved.is_(False))
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return existing
    item = PendingItem(rule_key=rule_key, **fields)
    db.add(item)
    return item


def _remove_stale_rule_items(db: Session, active_keys: set[str]) -> None:
    machine_items = db.scalars(
        select(PendingItem).where(PendingItem.kind.like("regra:%"), PendingItem.resolved.is_(False))
    ).all()
    for item in machine_items:
        if item.rule_key and item.rule_key not in active_keys:
            db.delete(item)


def apply_rules(db: Session) -> list[PendingItem]:
    active_keys: set[str] = set()
    created: list[PendingItem] = []

    for cert in db.scalars(select(Certificate)).all():
        status = certificate_status(cert.valid_until)
        cert.status = status
        if status != "vigente":
            rule_key = f"regra:certificado:{cert.number}"
            active_keys.add(rule_key)
            item = _upsert_rule_item(
                db,
                rule_key=rule_key,
                kind="regra:certificado",
                title=f"Certificado {cert.number} — {status}",
                area="Produto Ex / Qualidade",
                severity=severity_for_certificate(status),
                status="aguardando confirmação" if status == "vencido" else status,
                description=(
                    f"Foi localizado o certificado {cert.number}, fornecedor {cert.supplier}, "
                    f"com situação calculada como '{status}'."
                ),
                risk=(
                    "A validade exige análise, mas o sistema não conclui sozinho que o produto está irregular. "
                    "É necessário confirmar uso atual, estoque, lote, data de fabricação e eventual certificado substituto."
                ),
                responsible_role="Responsável por Produto Ex / Qualidade",
                due_date=cert.valid_until,
                source_path=cert.source_path,
                source_excerpt=cert.notes,
            )
            created.append(item)

    today = date.today()
    for nc in db.scalars(select(Nonconformity)).all():
        reasons: list[str] = []
        severity = "atenção"
        if not nc.responsible_role:
            reasons.append("sem função responsável")
        if nc.due_date and nc.due_date < today and nc.status != "encerrada":
            reasons.append("prazo vencido")
            severity = "crítico"
        if nc.status == "ação concluída" and not nc.effectiveness_verified:
            reasons.append("ação concluída, mas eficácia não verificada")
            severity = "crítico"
        if nc.status == "encerrada" and not nc.effectiveness_verified:
            reasons.append("encerrada sem eficácia registrada")
            severity = "crítico"
        if not nc.root_cause and nc.status in NC_STATUSES_NEEDING_ROOT_CAUSE:
            reasons.append("causa raiz não registrada")
        if reasons:
            rule_key = f"regra:nc:{nc.code}"
            active_keys.add(rule_key)
            item = _upsert_rule_item(
                db,
                rule_key=rule_key,
                kind="regra:nc",
                title=f"{nc.code}: " + "; ".join(reasons),
                area=nc.area,
                severity=severity,
                status="em análise" if nc.status != "encerrada" else "aguardando revisão",
                description=nc.description,
                risk="Uma ação executada não equivale ao encerramento da NC. É preciso evidência e verificação de eficácia.",
                responsible_role=nc.responsible_role or "Função responsável ainda não definida",
                due_date=nc.due_date,
                source_path=nc.source_path,
                source_excerpt=f"Causa: {nc.root_cause}\nAção: {nc.action}",
            )
            created.append(item)

    files = db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
    hashes: dict[str, list[FileRecord]] = {}
    document_alerts = 0
    duplicate_alerts = 0

    for record in files:
        if is_noise_file(record.name, record.path, record.extension):
            continue
        if record.sha256:
            hashes.setdefault(record.sha256, []).append(record)

        if record.extraction_status in {"protegido", "falha", "sem texto — OCR necessário"}:
            if not is_priority_document(record.category, record.path, record.name):
                continue
            if document_alerts >= DOCUMENT_ALERT_LIMIT:
                continue
            rule_key = f"regra:documento:{record.id}"
            active_keys.add(rule_key)
            item = _upsert_rule_item(
                db,
                rule_key=rule_key,
                kind="regra:documento",
                title=f"Documento prioritário não lido por completo: {record.name}",
                area="Documentos",
                severity="atenção",
                status="aguardando confirmação",
                description=f"Status de leitura: {record.extraction_status}.",
                risk="O conteúdo pode conter informação relevante que não entrou no diagnóstico automático.",
                responsible_role="Gestor da Qualidade / TI",
                source_path=record.path,
                source_excerpt=record.last_error or "",
            )
            created.append(item)
            document_alerts += 1

        if (
            record.name.lower().find("rq-mac") >= 0
            and len(record.extracted_text.strip()) < 250
            and record.extraction_status.startswith("lido")
        ):
            rule_key = f"regra:competencia:{record.id}"
            active_keys.add(rule_key)
            item = _upsert_rule_item(
                db,
                rule_key=rule_key,
                kind="regra:competencia",
                title="Matriz de competências possivelmente vazia",
                area="Pessoas e Competências",
                severity="crítico",
                status="aguardando confirmação",
                description="O arquivo associado à matriz de competências possui pouco ou nenhum conteúdo preenchido.",
                risk="A empresa pode não conseguir demonstrar competências necessárias por função e evidências de capacitação.",
                responsible_role="Responsável por RH + Gestor da Qualidade",
                source_path=record.path,
                source_excerpt=record.extracted_text[:500],
            )
            created.append(item)

    for same_hash in hashes.values():
        if len(same_hash) <= 1:
            continue
        if duplicate_alerts >= DUPLICATE_ALERT_LIMIT:
            break
        if any(is_noise_file(item.name, item.path, item.extension) for item in same_hash):
            continue
        if not any(is_priority_document(item.category, item.path, item.name) for item in same_hash):
            continue
        names = ", ".join(item.name for item in same_hash[:5])
        rule_key = f"regra:duplicado:{same_hash[0].sha256[:16]}"
        active_keys.add(rule_key)
        item = _upsert_rule_item(
            db,
            rule_key=rule_key,
            kind="regra:documento",
            title="Arquivos prioritários com conteúdo idêntico encontrados",
            area="Documentos",
            severity="atenção",
            status="aguardando confirmação",
            description=f"Arquivos: {names}",
            risk="Pode haver cópia sem atualização real, versão conflitante ou uso indevido de documento duplicado.",
            responsible_role="Gestor da Qualidade",
            source_path=same_hash[0].path,
            source_excerpt=f"Hash igual: {same_hash[0].sha256}",
        )
        created.append(item)
        duplicate_alerts += 1

    _remove_stale_rule_items(db, active_keys)
    db.commit()
    return created
