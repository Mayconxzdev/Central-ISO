from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FileRecord
from .extractors import extract_text
from .file_types import extension_category


SUPPORTED_SAMPLE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".csv", ".odt"}

SAMPLE_TARGETS = [
    ("Manual da Qualidade", ("manual-da-qualidade", "mq-")),
    ("Política da Qualidade", ("politica-e-objetivos", "política da qualidade", "politica da qualidade")),
    ("procedimento PQ", ("pq-", "procedimento")),
    ("instrução de trabalho", ("it-", "instru")),
    ("registro RQ em Excel", ("rq-", ".xlsx", ".xlsm")),
    ("lista mestra", ("lista mestra", "lista-mestra")),
    ("certificado ISO", ("certificado iso", "iso 9001")),
    ("certificado Ex", ("cpex", "certificado", "ex")),
    ("não conformidade", ("rq-tnc", "nao conform", "não conform")),
    ("plano de ação", ("plano de acao", "plano-de-acao", "ação")),
    ("RAC", ("rq-rac", "analise critica", "análise crítica")),
    ("auditoria", ("auditoria",)),
    ("fornecedor", ("fornecedor",)),
    ("treinamento ou competência", ("treinamento", "competencia", "competência")),
    ("calibração", ("calibra",)),
    ("indicador", ("indicador", "meta")),
    ("Produto Ex", ("produto ex", "cpex", "atmosferas explosivas")),
    ("arquivo protegido", ("protegido",)),
    ("possível duplicado", ("(2)", "copia", "cópia")),
    ("documento complexo", (".pdf", ".xlsm", ".xlsx")),
]


def sample_store_path(local_data_dir: Path) -> Path:
    path = local_data_dir / "runtime" / "sample_review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _match(record: FileRecord, needles: tuple[str, ...]) -> bool:
    haystack = f"{record.name} {record.path} {record.extension} {record.category}".lower()
    return all(needle.lower() in haystack for needle in needles[:1]) or any(needle.lower() in haystack for needle in needles)


def _usable_sample(record: FileRecord) -> bool:
    name = record.name.lower()
    if name.startswith("~$"):
        return False
    if record.extension not in SUPPORTED_SAMPLE_EXTENSIONS:
        return False
    if extension_category(record.extension) in {"temporarios", "backup", "executaveis/sistema"}:
        return False
    return True


def select_real_sample(db: Session, local_data_dir: Path, limit: int = 20) -> dict:
    rows = [
        record
        for record in db.scalars(select(FileRecord).where(FileRecord.is_present.is_(True))).all()
        if _usable_sample(record)
    ]
    selected: list[dict] = []
    used_paths: set[str] = set()
    for category, needles in SAMPLE_TARGETS:
        match = next((record for record in rows if record.path not in used_paths and _match(record, needles)), None)
        if match is None:
            continue
        used_paths.add(match.path)
        selected.append(
            {
                "category": category,
                "file_id": match.id,
                "name": match.name,
                "path": match.path,
                "extension": match.extension,
                "size_bytes": match.size_bytes,
                "status": "selected",
            }
        )
        if len(selected) >= limit:
            break
    payload = {"generated_at": datetime.now().isoformat(timespec="seconds"), "items": selected}
    sample_store_path(local_data_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def extract_sample(local_data_dir: Path) -> dict:
    path = sample_store_path(local_data_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("items", []):
        text, status = extract_text(Path(item["path"]))
        item["extraction_status"] = status
        item["text_chars"] = len(text)
        item["pages_detected"] = len(re.findall(r"\[P.gina ", text))
        item["sheets_detected"] = len(re.findall(r"\[Aba: ", text))
        item["codes_detected"] = sorted(set(re.findall(r"\b(?:PQ|RQ|IT|NC|CPEx)[-_/ ]?[A-Za-z0-9.]+", text, flags=re.I)))[:20]
        item["confidence"] = "media" if status.startswith("lido") or status == "protegido e lido" else "baixa"
        item["review"] = {"correct": None, "notes": "", "confirmed_by": "", "confirmed_at": ""}
    payload["extracted_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
