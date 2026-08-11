from __future__ import annotations

from datetime import datetime
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Certificate, FileRecord, Nonconformity, PendingItem, ScanRun


def pending_report_html(db: Session) -> str:
    items = db.scalars(
        select(PendingItem).where(PendingItem.resolved.is_(False)).order_by(PendingItem.severity, PendingItem.id)
    ).all()
    rows = "".join(
        f"<tr><td>{escape(item.title)}</td><td>{escape(item.area)}</td><td>{escape(item.severity)}</td>"
        f"<td>{escape(item.status)}</td><td>{escape(item.responsible_role)}</td>"
        f"<td>{escape(item.source_path)}</td></tr>"
        for item in items
    )
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório de Pendências</title>
    <style>body{{font-family:Arial,sans-serif;margin:32px;color:#172033}}h1{{margin-bottom:4px}}small{{color:#667085}}
    table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{border:1px solid #dfe4ea;padding:9px;text-align:left;vertical-align:top}}th{{background:#f4f7fb}}</style></head>
    <body><h1>Central ISO — Pendências</h1><small>Gerado em {datetime.now():%d/%m/%Y %H:%M}</small>
    <p>Este relatório é uma consolidação de apoio. Decisões oficiais permanecem sob responsabilidade das funções designadas pela empresa.</p>
    <table><thead><tr><th>Pendência</th><th>Área</th><th>Prioridade</th><th>Situação</th><th>Função responsável</th><th>Origem</th></tr></thead>
    <tbody>{rows}</tbody></table></body></html>"""


def quality_summary_html(db: Session) -> str:
    pending = db.scalars(select(PendingItem).where(PendingItem.resolved.is_(False))).all()
    certificates = db.scalars(select(Certificate)).all()
    ncs = db.scalars(select(Nonconformity)).all()
    last_scan = db.scalar(select(ScanRun).order_by(ScanRun.id.desc()).limit(1))
    files = db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
    sgq_count = sum((record.category or "").lower() in {"procedimento", "instrução de trabalho", "manual", "rac", "auditoria", "certificado", "não conformidade", "competência"} for record in files)
    unread = sum(record.extraction_status in {"falha", "protegido", "sem texto — OCR necessário", "sem texto â€” OCR necessÃ¡rio"} for record in files)
    critical = [item for item in pending if item.severity in {"crítico", "crÃ­tico"}]
    awaiting = [item for item in pending if "aguard" in (item.status or "").lower()]
    expired_certs = [cert for cert in certificates if cert.status == "vencido"]
    due_certs = [cert for cert in certificates if (cert.status or "").startswith("vence em")]
    open_ncs = [nc for nc in ncs if nc.status != "encerrada"]
    ncs_waiting_effectiveness = [nc for nc in ncs if nc.status == "ação concluída" and not nc.effectiveness_verified]

    def metric(label: str, value: object, note: str = "") -> str:
        return f"<div class='metric'><small>{escape(label)}</small><strong>{escape(str(value))}</strong><span>{escape(note)}</span></div>"

    def list_rows(items: list[PendingItem]) -> str:
        if not items:
            return "<tr><td colspan='4'>Nenhum registro validado até o momento.</td></tr>"
        return "".join(
            f"<tr><td>{escape(item.title)}</td><td>{escape(item.severity)}</td><td>{escape(item.status)}</td><td>{escape(item.source_path)}</td></tr>"
            for item in items[:20]
        )

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Resumo da Qualidade</title>
    <style>body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#172033}}h1{{margin:0 0 4px}}.muted{{color:#667085}}
    .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}.metric{{border:1px solid #dfe4ea;border-radius:8px;padding:14px}}
    .metric small,.metric span{{display:block;color:#667085}}.metric strong{{display:block;font-size:28px;margin:6px 0;color:#146ef5}}
    table{{border-collapse:collapse;width:100%;margin-top:12px}}th,td{{border:1px solid #dfe4ea;padding:8px;text-align:left;vertical-align:top}}th{{background:#f4f7fb}}
    section{{margin-top:24px}}.warn{{background:#fff7e8;border:1px solid #f3d69b;border-radius:8px;padding:12px}}</style></head><body>
    <h1>Resumo da Qualidade</h1><div class="muted">Gerado em {datetime.now():%d/%m/%Y %H:%M}. Última varredura: {escape(str(last_scan.finished_at if last_scan else "não registrada"))}</div>
    <div class="warn"><strong>Fonte:</strong> inventário real da pasta ISO oficial e registros extraídos ou confirmados no aplicativo.<br>Este relatório usa apenas dados reais já inventariados ou extraídos. Categorias sem registro validado não foram preenchidas com dados fictícios.</div>
    <div class="metrics">
    {metric("Documentos acompanhados", len(files), "arquivos acessíveis")}
    {metric("Documentos SGQ identificados", sgq_count, "classificação inicial")}
    {metric("Arquivos não lidos", unread, "falha, protegido ou OCR pendente")}
    {metric("Pendências críticas", len(critical), "reais ou detectadas automaticamente")}
    </div>
    <section><h2>Certificados</h2><div class="metrics">{metric("Vencidos", len(expired_certs))}{metric("Vencendo", len(due_certs))}{metric("Registros estruturados", len(certificates))}{metric("Status", "revisão necessária" if certificates else "sem registro validado")}</div></section>
    <section><h2>Não conformidades</h2><div class="metrics">{metric("Abertas", len(open_ncs))}{metric("Aguardando eficácia", len(ncs_waiting_effectiveness))}{metric("Registros estruturados", len(ncs))}{metric("Status", "revisão necessária" if ncs else "sem registro validado")}</div></section>
    <section><h2>Principais pendências</h2><table><thead><tr><th>Item</th><th>Prioridade</th><th>Status</th><th>Fonte</th></tr></thead><tbody>{list_rows(pending)}</tbody></table></section>
    <section><h2>Fontes e limitações</h2><p>Diretórios inacessíveis e PDFs sem texto devem ser tratados antes da validação final. A Central ISO não aprova documentos nem encerra NCs automaticamente.</p></section>
    </body></html>"""
