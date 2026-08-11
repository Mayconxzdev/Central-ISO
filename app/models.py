from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow_naive() -> datetime:
    """UTC sem tzinfo para colunas DateTime legadas/portáveis."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    extension: Mapped[str] = mapped_column(String(32), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="desconhecido", index=True)
    extraction_status: Mapped[str] = mapped_column(String(50), default="pendente", index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scanned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    is_present: Mapped[bool] = mapped_column(Boolean, default=True)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    supplier: Mapped[str] = mapped_column(String(255), index=True)
    component_or_product: Mapped[str] = mapped_column(String(255), default="")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="aguardando confirmação", index=True)
    use_status: Mapped[str] = mapped_column(String(80), default="uso não confirmado")
    source_path: Mapped[str] = mapped_column(String(2048), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    replacement_certificate: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Nonconformity(Base):
    __tablename__ = "nonconformities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    area: Mapped[str] = mapped_column(String(128), index=True)
    origin: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    responsible_role: Mapped[str] = mapped_column(String(255), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(80), default="aberta", index=True)
    evidence_found: Mapped[bool] = mapped_column(Boolean, default=False)
    effectiveness_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source_path: Mapped[str] = mapped_column(String(2048), default="")


class PendingItem(Base):
    __tablename__ = "pending_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    area: Mapped[str] = mapped_column(String(128), default="")
    severity: Mapped[str] = mapped_column(String(30), default="atenção", index=True)
    status: Mapped[str] = mapped_column(String(80), default="aguardando confirmação", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    risk: Mapped[str] = mapped_column(Text, default="")
    responsible_role: Mapped[str] = mapped_column(String(255), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_path: Mapped[str] = mapped_column(String(2048), default="")
    source_excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class HumanNote(Base):
    __tablename__ = "human_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pending_item_id: Mapped[int] = mapped_column(ForeignKey("pending_items.id"), index=True)
    author: Mapped[str] = mapped_column(String(255), default="Usuário")
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    pending_item: Mapped[PendingItem] = relationship()


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mode: Mapped[str] = mapped_column(String(50), default="incremental")
    status: Mapped[str] = mapped_column(String(50), default="running")
    files_found: Mapped[int] = mapped_column(Integer, default=0)
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    files_failed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (UniqueConstraint("operational_role", "person_name", "start_date", name="uq_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operational_role: Mapped[str] = mapped_column(String(255), index=True)
    person_name: Mapped[str] = mapped_column(String(255), index=True)
    department: Mapped[str] = mapped_column(String(128), default="")
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    substitute_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AutomationEvent(Base):
    __tablename__ = "automation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), default="")
    entity_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(30), default="info")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
