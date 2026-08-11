from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Certificate, FileRecord, Nonconformity
from .certificate_extractor import ExtractedCertificate, extract_certificates_from_record
from .file_filters import is_noise_file
from .nc_extractor import ExtractedNonconformity, extract_nc_from_record


def _upsert_certificate(db: Session, extracted: ExtractedCertificate) -> tuple[Certificate, bool]:
    existing = db.scalar(select(Certificate).where(Certificate.number == extracted.number))
    if existing is None:
        cert = Certificate(
            number=extracted.number,
            supplier=extracted.supplier,
            component_or_product=extracted.component_or_product,
            valid_until=extracted.valid_until,
            source_path=extracted.source_path,
            notes=extracted.notes,
            status="aguardando confirmação",
        )
        db.add(cert)
        return cert, True

    changed = False
    if extracted.valid_until and (
        existing.valid_until is None or extracted.valid_until > existing.valid_until
    ):
        if existing.valid_until and extracted.valid_until > existing.valid_until:
            existing.replacement_certificate = extracted.number
        existing.valid_until = extracted.valid_until
        changed = True
    if extracted.supplier and not existing.supplier:
        existing.supplier = extracted.supplier
        changed = True
    if extracted.component_or_product and not existing.component_or_product:
        existing.component_or_product = extracted.component_or_product
        changed = True
    if extracted.source_path and extracted.source_path not in (existing.source_path or ""):
        existing.source_path = extracted.source_path
        changed = True
    if extracted.notes:
        existing.notes = extracted.notes
    return existing, changed


def _upsert_nonconformity(db: Session, extracted: ExtractedNonconformity) -> tuple[Nonconformity, bool]:
    existing = db.scalar(select(Nonconformity).where(Nonconformity.code == extracted.code))
    if existing is None:
        nc = Nonconformity(
            code=extracted.code,
            area=extracted.area,
            origin=extracted.origin,
            description=extracted.description,
            source_path=extracted.source_path,
            status="aberta",
        )
        db.add(nc)
        return nc, True

    changed = False
    if extracted.area and existing.area in {"", "Não identificada"}:
        existing.area = extracted.area
        changed = True
    if extracted.description and len(extracted.description) > len(existing.description or ""):
        existing.description = extracted.description
        changed = True
    if extracted.source_path and extracted.source_path != existing.source_path:
        existing.source_path = extracted.source_path
        changed = True
    return existing, changed


def sync_structured_records(db: Session) -> dict[str, int]:
    records = db.scalars(
        select(FileRecord).where(
            FileRecord.is_present.is_(True),
            FileRecord.extraction_status.notin_(["falha", "formato não suportado"]),
        )
    ).all()

    stats = {
        "files_considered": 0,
        "certificates_created": 0,
        "certificates_updated": 0,
        "ncs_created": 0,
        "ncs_updated": 0,
    }
    seen_nc_codes: set[str] = set()

    for record in records:
        if is_noise_file(record.name, record.path, record.extension):
            continue
        stats["files_considered"] += 1

        for extracted in extract_certificates_from_record(record):
            _, created = _upsert_certificate(db, extracted)
            if created:
                stats["certificates_created"] += 1
            else:
                stats["certificates_updated"] += 1

        nc = extract_nc_from_record(record)
        if nc and nc.code not in seen_nc_codes:
            seen_nc_codes.add(nc.code)
            _, created = _upsert_nonconformity(db, nc)
            if created:
                stats["ncs_created"] += 1
            else:
                stats["ncs_updated"] += 1

    db.commit()
    return stats
