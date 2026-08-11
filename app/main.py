from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, ensure_schema, get_db
from .models import AutomationEvent, Certificate, FileRecord, HumanNote, Nonconformity, PendingItem, ScanRun
from .schemas import AssistantQuery, NoteCreate, PendingItemOut, StatusUpdate
from .seed import prepare_initial_data
from .services.assistant import answer_question, search_documents
from .services.inventory import get_extension_report, get_inventory_summary, run_inventory
from .services.hash_progress import pause_hashing, read_checkpoint, resume_hashing, run_progressive_hash
from .services.reports import pending_report_html, quality_summary_html
from .services.reconciliation import reconcile_inventory
from .services.sample_review import extract_sample, select_real_sample
from .services.rules import apply_rules
from .services.scanner import scan_directory
from .services.structured_sync import sync_structured_records
from .services.certificate_workflow import run_certificate_workflow


def _run_automation_pipeline(db: Session) -> dict:
    sync_stats = sync_structured_records(db)
    workflow_stats = run_certificate_workflow(db)
    apply_rules(db)
    return {"sync": sync_stats, "workflow": workflow_stats}


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema()
    with SessionLocal() as db:
        prepare_initial_data(db, settings.app_data_mode)
        if db.scalar(select(ScanRun.id).limit(1)) is None:
            scan_directory(db, settings.iso_share_path, mode="full")
        _run_automation_pipeline(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0-piloto",
    description="Piloto read-only para leitura, organização e acompanhamento documental de um SGQ.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8877", "http://localhost:8877", "tauri://localhost", "https://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/v1/system/operator")
def system_operator() -> dict:
    try:
        import getpass
        import socket
        username = getpass.getuser()
        computer = socket.gethostname()
        domain = os.environ.get("USERDOMAIN", "")
        if settings.app_data_mode == "demo":
            return {
                "username": "demo",
                "domain": "LOCAL",
                "computer_name": "DEMO",
                "display": "Operador Demo",
            }
        display = f"{domain}\\{username}" if domain else username
        return {
            "username": username,
            "domain": domain or "LOCAL",
            "computer_name": computer,
            "display": display,
        }
    except Exception as e:
        raise HTTPException(500, f"Não foi possível identificar operador: {e}")


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)) -> dict:
    last_scan = db.scalar(select(ScanRun).order_by(ScanRun.id.desc()).limit(1))
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.3.0-public-demo",
        "environment": settings.environment,
        "data_mode": settings.app_data_mode,
        "maintenance_mode": settings.maintenance_mode,
        "ai_mode": settings.ai_mode,
        "iso_share": {
            "path": "./demo_iso" if settings.app_data_mode == "demo" else str(settings.iso_share_path),
            "accessible": settings.iso_share_path.exists() and settings.iso_share_path.is_dir(),
            "read_only_policy": True,
        },
        "last_scan": {
            "id": last_scan.id,
            "status": last_scan.status,
            "finished_at": last_scan.finished_at,
        } if last_scan else None,
    }


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    open_items = db.scalars(select(PendingItem).where(PendingItem.resolved.is_(False))).all()
    decisions = [item for item in open_items if item.kind.startswith("decisão:") or item.severity == "crítico"]
    tracking = [item for item in open_items if item.kind.startswith("fluxo:")]
    rule_items = [item for item in open_items if item.kind.startswith("regra:")]
    auto_resolved = db.scalar(
        select(func.count(PendingItem.id)).where(PendingItem.status == "resolvido automaticamente")
    ) or 0
    certificates = db.scalar(select(func.count(Certificate.id))) or 0
    ncs = db.scalar(select(func.count(Nonconformity.id))) or 0
    files_total = db.scalar(select(func.count(FileRecord.id)).where(FileRecord.is_present.is_(True))) or 0
    files_analyzed = db.scalar(
        select(func.count(FileRecord.id)).where(
            FileRecord.is_present.is_(True),
            FileRecord.extraction_status.like("lido%"),
        )
    ) or 0
    last_scan = db.scalar(select(ScanRun).order_by(ScanRun.id.desc()).limit(1))
    critical = sum(item.severity == "crítico" for item in open_items)
    attention = sum(item.severity == "atenção" for item in open_items)
    awaiting = sum("aguard" in item.status for item in open_items)
    if critical:
        overall = "Situação crítica"
    elif decisions:
        overall = "Atenção necessária"
    else:
        overall = "Tudo sob controle"
    return {
        "needs_attention": len(decisions),
        "decisions_needed": len(decisions),
        "automatic_tracking": len(tracking) + len(rule_items),
        "auto_resolved": auto_resolved,
        "overall_status": overall,
        "due_soon": attention,
        "awaiting_confirmation": awaiting,
        "in_order": len(tracking) + len(rule_items),
        "documents_tracked": files_total,
        "documents_analyzed": files_analyzed,
        "certificates_tracked": certificates,
        "ncs_tracked": ncs,
        "files_with_warnings": files_total - files_analyzed,
        "last_updated": last_scan.finished_at.isoformat() if last_scan and last_scan.finished_at else None,
        "share_accessible": settings.iso_share_path.exists() and settings.iso_share_path.is_dir(),
        "ai_operational": settings.ai_mode != "disabled",
    }


@app.get("/api/v1/dashboard/executive")
def dashboard_executive(db: Session = Depends(get_db)) -> dict:
    summary = dashboard_summary(db)
    priorities = dashboard_priorities(db, limit=8)
    recent_events = db.scalars(
        select(AutomationEvent).order_by(AutomationEvent.id.desc()).limit(10)
    ).all()
    return {
        "summary": summary,
        "decisions": [item for item in priorities if item.kind.startswith("decisão:") or item.severity == "crítico"],
        "tracking": [item for item in priorities if item.kind.startswith(("fluxo:", "regra:"))],
        "recent_automation": [
            {
                "event_type": event.event_type,
                "entity_key": event.entity_key,
                "message": event.message,
                "level": event.level,
                "created_at": event.created_at,
            }
            for event in recent_events
        ],
        "brief": (
            f"A Central ISO está acompanhando {summary['automatic_tracking']} situações. "
            f"{summary['decisions_needed']} precisam da sua decisão."
        ),
    }


@app.get("/api/v1/dashboard/priorities", response_model=list[PendingItemOut])
def dashboard_priorities(db: Session = Depends(get_db), limit: int = Query(6, ge=1, le=30)):
    severity_order = {"crítico": 0, "atenção": 1, "informativo": 2}
    items = db.scalars(select(PendingItem).where(PendingItem.resolved.is_(False))).all()
    items.sort(key=lambda item: (severity_order.get(item.severity, 9), item.due_date or date.max, item.id))
    return items[:limit]


@app.get("/api/v1/pending-items", response_model=list[PendingItemOut])
def pending_items(
    db: Session = Depends(get_db),
    severity: str | None = None,
    kind: str | None = None,
    status: str | None = None,
):
    stmt = select(PendingItem).where(PendingItem.resolved.is_(False))
    if severity:
        stmt = stmt.where(PendingItem.severity == severity)
    if kind:
        stmt = stmt.where(PendingItem.kind == kind)
    if status:
        stmt = stmt.where(PendingItem.status == status)
    return db.scalars(stmt.order_by(PendingItem.id.desc())).all()


@app.get("/api/v1/pending-items/{item_id}", response_model=PendingItemOut)
def pending_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(PendingItem, item_id)
    if not item:
        raise HTTPException(404, "Pendência não encontrada")
    return item


@app.post("/api/v1/pending-items/{item_id}/notes")
def add_note(item_id: int, payload: NoteCreate, db: Session = Depends(get_db)) -> dict:
    item = db.get(PendingItem, item_id)
    if not item:
        raise HTTPException(404, "Pendência não encontrada")
    note = HumanNote(pending_item_id=item_id, author=payload.author, note=payload.note)
    db.add(note)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "message": "Observação adicionada somente à Central ISO."}


@app.post("/api/v1/pending-items/{item_id}/status")
def update_pending_status(item_id: int, payload: StatusUpdate, db: Session = Depends(get_db)) -> dict:
    item = db.get(PendingItem, item_id)
    if not item:
        raise HTTPException(404, "Pendência não encontrada")
    allowed = {"aguardando confirmação", "em análise", "aguardando revisão", "não se aplica", "resolvido no painel"}
    if payload.status not in allowed:
        raise HTTPException(422, f"Status permitido no piloto: {sorted(allowed)}")
    item.status = payload.status
    item.resolved = payload.status in {"não se aplica", "resolvido no painel"}
    item.updated_at = datetime.now(timezone.utc)
    db.add(HumanNote(pending_item_id=item_id, author="Sistema", note=f"Status: {payload.status}. Justificativa: {payload.justification}"))
    db.commit()
    return {
        "message": "Status interno atualizado. Isso não altera nem encerra o registro oficial do SGQ.",
        "status": item.status,
    }


@app.get("/api/v1/certificates")
def certificates(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Certificate).order_by(Certificate.valid_until.asc().nulls_last())).all()
    return [
        {
            "id": row.id,
            "number": row.number,
            "supplier": row.supplier,
            "component_or_product": row.component_or_product,
            "valid_until": row.valid_until,
            "status": row.status,
            "use_status": row.use_status,
            "source_path": row.source_path,
            "notes": row.notes,
            "replacement_certificate": row.replacement_certificate,
        }
        for row in rows
    ]


@app.get("/api/v1/nonconformities")
def nonconformities(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Nonconformity).order_by(Nonconformity.code)).all()
    return [
        {
            "id": row.id,
            "code": row.code,
            "area": row.area,
            "origin": row.origin,
            "description": row.description,
            "root_cause": row.root_cause,
            "action": row.action,
            "responsible_role": row.responsible_role,
            "due_date": row.due_date,
            "status": row.status,
            "evidence_found": row.evidence_found,
            "effectiveness_verified": row.effectiveness_verified,
            "source_path": row.source_path,
        }
        for row in rows
    ]


def _document_payload(row: FileRecord) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "path": row.path,
        "category": row.category,
        "extension": row.extension,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "status": row.extraction_status,
        "modified_at": row.modified_at,
        "last_error": row.last_error,
        "excerpt": row.extracted_text[:450],
    }


@app.get("/api/v1/documents")
def documents(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("modified_at"),
    sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
    q: str | None = None,
    extension: str | None = None,
    folder: str | None = None,
    status: str | None = None,
    accessible: bool | None = None,
    duplicate: bool | None = None,
    error: bool | None = None,
) -> dict:
    stmt = select(FileRecord).where(FileRecord.is_present.is_(True))
    query_text = search or q
    if query_text:
        like = f"%{query_text}%"
        stmt = stmt.where(
            FileRecord.name.like(like)
            | FileRecord.path.like(like)
            | FileRecord.category.like(like)
            | FileRecord.extracted_text.like(like)
        )
    if extension:
        stmt = stmt.where(FileRecord.extension == extension)
    if folder:
        stmt = stmt.where(FileRecord.path.like(f"%{folder}%"))
    if status:
        stmt = stmt.where(FileRecord.extraction_status == status)
    if accessible is not None:
        stmt = stmt.where(FileRecord.extraction_status != "falha" if accessible else FileRecord.extraction_status == "falha")
    if error is not None:
        stmt = stmt.where(FileRecord.extraction_status == "falha" if error else FileRecord.extraction_status != "falha")
    if duplicate is not None:
        duplicate_hashes = (
            select(FileRecord.sha256)
            .where(FileRecord.is_present.is_(True), FileRecord.sha256 != "")
            .group_by(FileRecord.sha256)
            .having(func.count(FileRecord.id) > 1)
        )
        stmt = stmt.where(FileRecord.sha256.in_(duplicate_hashes) if duplicate else ~FileRecord.sha256.in_(duplicate_hashes))

    total_items = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    sort_columns = {
        "name": FileRecord.name,
        "extension": FileRecord.extension,
        "size_bytes": FileRecord.size_bytes,
        "modified_at": FileRecord.modified_at,
        "status": FileRecord.extraction_status,
        "category": FileRecord.category,
    }
    sort_column = sort_columns.get(sort_by, FileRecord.modified_at)
    order = sort_column.asc() if sort_direction == "asc" else sort_column.desc()
    rows = db.scalars(stmt.order_by(order, FileRecord.id.asc()).offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = max((total_items + page_size - 1) // page_size, 1)
    return {
        "items": [_document_payload(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


@app.get("/api/v1/evidence")
def serve_evidence(
    path: str = Query(min_length=1, max_length=4096),
    db: Session = Depends(get_db),
):
    """
    Retorna um arquivo de evidência da pasta ISO de forma segura (somente leitura).
    Apenas arquivos registrados no banco podem ser acessados.
    """
    try:
        requested = (settings.iso_share_path / path).resolve()
    except Exception:
        raise HTTPException(400, "Caminho inválido")

    iso_root = settings.iso_share_path.resolve()
    try:
        requested.relative_to(iso_root)
    except ValueError:
        raise HTTPException(403, "Acesso negado: caminho fora da pasta ISO")

    if not requested.exists() or not requested.is_file():
        raise HTTPException(404, "Arquivo não encontrado")

    record = db.scalar(select(FileRecord).where(FileRecord.path == str(requested)))
    if record is None:
        raise HTTPException(403, "Arquivo não registrado na Central ISO")

    return FileResponse(
        path=requested,
        filename=record.name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{record.name}"'},
    )


@app.get("/api/v1/search")
def search(q: str = Query(min_length=2), db: Session = Depends(get_db)) -> list[dict]:
    return [hit.__dict__ for hit in search_documents(db, q)]


@app.post("/api/v1/assistant/query")
def assistant_query(payload: AssistantQuery = Body(...), db: Session = Depends(get_db)) -> dict:
    return answer_question(db, payload.question)


@app.post("/api/v1/scans")
def start_scan(mode: str = Query("incremental", pattern="^(incremental|full)$"), db: Session = Depends(get_db)) -> dict:
    run = scan_directory(db, settings.iso_share_path, mode=mode)
    pipeline = {}
    if run.status != "failed":
        pipeline = _run_automation_pipeline(db)
    return {
        "id": run.id,
        "status": run.status,
        "files_found": run.files_found,
        "files_processed": run.files_processed,
        "files_failed": run.files_failed,
        "message": run.message,
        "automation": pipeline,
    }


@app.post("/api/v1/automation/run")
def run_automation(db: Session = Depends(get_db)) -> dict:
    return _run_automation_pipeline(db)


@app.get("/api/v1/scans")
def scans(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ScanRun).order_by(ScanRun.id.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "mode": row.mode,
            "status": row.status,
            "files_found": row.files_found,
            "files_processed": row.files_processed,
            "files_failed": row.files_failed,
            "message": row.message,
        }
        for row in rows
    ]


@app.get("/api/v1/reports/pending.html", response_class=HTMLResponse)
def pending_report(db: Session = Depends(get_db)) -> str:
    return pending_report_html(db)


@app.get("/api/v1/reports/quality-summary.html", response_class=HTMLResponse)
def quality_summary_report(db: Session = Depends(get_db)) -> str:
    return quality_summary_html(db)


@app.post("/api/v1/inventory/run")
def run_inventory_endpoint(db: Session = Depends(get_db)) -> dict:
    run = run_inventory(db, settings.iso_share_path)
    return {
        "id": run.id,
        "status": run.status,
        "files_found": run.files_found,
        "files_processed": run.files_processed,
        "files_failed": run.files_failed,
        "message": run.message,
    }


@app.get("/api/v1/inventory/summary")
def inventory_summary(db: Session = Depends(get_db)) -> dict:
    return get_inventory_summary(db, settings.iso_share_path)


@app.get("/api/v1/inventory/extensions")
def inventory_extensions(db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=500)) -> dict:
    return get_extension_report(db, limit=limit)


@app.get("/api/v1/inventory/files")
def inventory_files(
    db: Session = Depends(get_db),
    ext: str | None = None,
    folder: str | None = None,
    accessible: bool | None = None,
    size_min: int | None = None,
    size_max: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    stmt = select(FileRecord).where(FileRecord.is_present.is_(True))
    if ext:
        stmt = stmt.where(FileRecord.extension == ext)
    if folder:
        stmt = stmt.where(FileRecord.path.like(f"%{folder}%"))
    rows = db.scalars(stmt.order_by(FileRecord.modified_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "path": r.path,
            "extension": r.extension,
            "size_bytes": r.size_bytes,
            "modified_at": r.modified_at,
            "status": r.extraction_status,
        }
        for r in rows
    ]


@app.get("/api/v1/inventory/errors")
def inventory_errors(db: Session = Depends(get_db), limit: int = Query(200, ge=1, le=1000)) -> list[dict]:
    rows = db.scalars(
        select(FileRecord)
        .where(FileRecord.is_present.is_(True), FileRecord.extraction_status == "falha")
        .order_by(FileRecord.last_scanned_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "path": r.path,
            "extension": r.extension,
            "size_bytes": r.size_bytes,
            "error": r.last_error,
            "last_scanned_at": r.last_scanned_at,
        }
        for r in rows
    ]


@app.get("/api/v1/inventory/duplicates")
def inventory_duplicates(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(FileRecord).where(FileRecord.is_present.is_(True), FileRecord.sha256 != "")
    ).all()
    by_hash: dict[str, list[dict]] = {}
    for r in rows:
        by_hash.setdefault(r.sha256, []).append(
            {
                "id": r.id,
                "name": r.name,
                "path": r.path,
                "size_bytes": r.size_bytes,
                "modified_at": r.modified_at,
            }
        )
    groups = [{"hash": h, "count": len(items), "files": items} for h, items in by_hash.items() if len(items) > 1]
    groups.sort(key=lambda g: (-g["count"], g["files"][0]["name"]))
    return groups


@app.get("/api/v1/inventory/runs/{run_id}")
def inventory_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(ScanRun, run_id)
    if not run:
        raise HTTPException(404, "Execução não encontrada")
    return {
        "id": run.id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "mode": run.mode,
        "status": run.status,
        "files_found": run.files_found,
        "files_processed": run.files_processed,
        "files_failed": run.files_failed,
        "message": run.message,
    }


@app.get("/api/v1/hash/status")
def hash_status() -> dict:
    return read_checkpoint(settings.local_data_dir).__dict__


@app.post("/api/v1/hash/run")
def hash_run(db: Session = Depends(get_db)) -> dict:
    if settings.hash_mode == "disabled":
        return {"status": "disabled", "message": "Hash progressivo desativado."}
    return run_progressive_hash(
        db,
        settings.local_data_dir,
        batch_size=settings.hash_batch_size,
        large_file_mb=settings.hash_large_file_mb,
        delay_ms=settings.hash_delay_ms,
    )


@app.post("/api/v1/hash/pause")
def hash_pause() -> dict:
    return pause_hashing(settings.local_data_dir).__dict__


@app.post("/api/v1/hash/resume")
def hash_resume() -> dict:
    return resume_hashing(settings.local_data_dir).__dict__


@app.post("/api/v1/inventory/reconcile")
def inventory_reconcile(db: Session = Depends(get_db)) -> dict:
    return reconcile_inventory(db, settings.iso_share_path, Path("logs"), powershell_total=86380)


@app.post("/api/v1/sample/select")
def sample_select(db: Session = Depends(get_db)) -> dict:
    return select_real_sample(db, settings.local_data_dir)


@app.post("/api/v1/sample/extract")
def sample_extract() -> dict:
    return extract_sample(settings.local_data_dir)
