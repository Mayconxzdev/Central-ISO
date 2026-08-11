from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FileRecord, PendingItem


STOPWORDS = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "para",
    "por",
    "que",
    "quais",
    "qual",
    "como",
    "com",
    "sem",
    "está",
    "estao",
    "estão",
    "um",
    "uma",
}


@dataclass
class SearchHit:
    name: str
    path: str
    category: str
    excerpt: str
    score: int


def _tokens(text: str) -> list[str]:
    values = re.findall(r"[a-zA-ZÀ-ÿ0-9_.-]{3,}", text.lower())
    return [value for value in values if value not in STOPWORDS]


def _is_searchable_source(record: FileRecord) -> bool:
    path = (record.path or "").replace("/", "\\").lower()
    name = (record.name or "").lower()
    parts = [part for part in path.split("\\") if part]
    if name.startswith("~$") or name.endswith("~") or name.endswith(".tmp"):
        return False
    if any(part in {"@recycle", "$recycle.bin", "recycle", "lixeira"} for part in parts):
        return False
    if any("arquivo morto" in part for part in parts):
        return False
    return True


def search_documents(db: Session, query: str, limit: int = 8) -> list[SearchHit]:
    tokens = _tokens(query)
    hits: list[SearchHit] = []
    for record in db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all():
        if not _is_searchable_source(record):
            continue
        haystack = f"{record.name} {record.path} {record.category} {record.extracted_text}".lower()
        score = sum(haystack.count(token) for token in tokens)
        if score <= 0:
            continue
        excerpt = record.extracted_text[:700].strip() or "Conteúdo não extraído; correspondência pelo nome/caminho."
        hits.append(SearchHit(record.name, record.path, record.category, excerpt, score))
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


def answer_question(db: Session, question: str) -> dict:
    q = question.lower()
    pending = db.scalars(select(PendingItem).where(PendingItem.resolved.is_(False))).all()
    relevant_pending = [
        item
        for item in pending
        if any(token in f"{item.title} {item.description} {item.area}".lower() for token in _tokens(question))
    ]
    hits = search_documents(db, question)

    if "certific" in q and "venc" in q:
        relevant_pending = [item for item in pending if item.kind == "regra:certificado" and "vencido" in item.title.lower()]
    elif "efic" in q or "não conform" in q or "nao conform" in q:
        relevant_pending = [item for item in pending if item.kind == "regra:nc"]
    elif "compet" in q:
        relevant_pending = [item for item in pending if item.kind == "regra:competencia"]

    if not relevant_pending and not hits:
        return {
            "answer": "Não encontrei evidência suficiente nos documentos analisados para confirmar essa informação.",
            "evidence": [],
            "sources": [],
            "confidence": "baixa",
            "confirmation_needed": ["Reformular a pergunta ou executar uma nova varredura da pasta ISO."],
            "mode": "busca documental local",
        }

    evidence = [item.title for item in relevant_pending[:6]]
    sources = []
    for item in relevant_pending[:6]:
        if item.source_path:
            sources.append(
                {"name": item.source_path.split("/")[-1].split("\\")[-1], "path": item.source_path, "excerpt": item.source_excerpt[:400]}
            )
    for hit in hits[:5]:
        if hit.path not in {source["path"] for source in sources}:
            sources.append({"name": hit.name, "path": hit.path, "excerpt": hit.excerpt[:400]})

    answer = (
        f"Foram encontradas {len(relevant_pending)} pendência(s) diretamente relacionada(s) à pergunta. "
        "A Central ISO organiza a evidência e indica o que precisa de análise, mas não substitui a aprovação técnica ou gerencial."
    )
    confirmations = []
    for item in relevant_pending[:5]:
        if item.status in {"aguardando confirmação", "aguardando revisão", "aguardando confirmação", "aguardando revisão"}:
            confirmations.append(f"Confirmar: {item.title}")
    if not confirmations:
        confirmations.append("Validar a conclusão com a função responsável antes de tomar decisão oficial.")

    return {
        "answer": answer,
        "evidence": evidence,
        "sources": sources[:8],
        "confidence": "alta" if relevant_pending and sources else "média",
        "confirmation_needed": confirmations,
        "mode": "busca documental local (IA externa desativada)",
    }
