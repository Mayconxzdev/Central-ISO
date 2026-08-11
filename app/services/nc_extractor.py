from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..models import FileRecord

NC_CODE_PATTERN = re.compile(
    r"\b(?:RQ[- ]?TNC|NC)\s*[_\s-]*(\d{1,4})[/_\s-]*(\d{4})\b",
    re.IGNORECASE,
)
NC_FILE_PATTERN = re.compile(
    r"\bNC[_\s-]*(\d{1,4})[_\s-]*(\d{4})\b",
    re.IGNORECASE,
)
NC_FOLDER_PATTERN = re.compile(
    r"RQ[- ]?TNC[_\s-]*(\d{1,4})[-_](\d{4})[_\s-]*([^\\/]+)",
    re.IGNORECASE,
)
AREA_HINTS = {
    "gerencia": "Gerência",
    "compras": "Compras",
    "producao": "Produção",
    "projetos": "Projetos",
    "comercial": "Comercial",
    "rh": "RH",
    "qualidade": "Qualidade",
    "engenharia": "Engenharia",
}


@dataclass(frozen=True)
class ExtractedNonconformity:
    code: str
    area: str
    origin: str
    description: str
    due_date: date | None
    source_path: str
    confidence: str


def _code_from_match(prefix_num: str, year: str) -> str:
    return f"NC {int(prefix_num):03d}/{year}"


def extract_nc_from_path(path: str) -> ExtractedNonconformity | None:
    folder_match = NC_FOLDER_PATTERN.search(path.replace("\\", "/"))
    if folder_match:
        code = _code_from_match(folder_match.group(1), folder_match.group(2))
        area_raw = folder_match.group(3).replace("_", " ").replace("-", " ").strip()
        area_key = area_raw.lower().split()[0] if area_raw else ""
        area = AREA_HINTS.get(area_key, area_raw.title() or "Não identificada")
        return ExtractedNonconformity(
            code=code,
            area=area,
            origin="Registro RQ-TNC",
            description=f"Não conformidade localizada em {Path(path).parent.name}.",
            due_date=None,
            source_path=path,
            confidence="alta",
        )

    file_match = NC_FILE_PATTERN.search(Path(path).name)
    if file_match:
        code = _code_from_match(file_match.group(1), file_match.group(2))
        return ExtractedNonconformity(
            code=code,
            area="Não identificada",
            origin="Registro de NC",
            description=f"Arquivo {Path(path).name} associado à não conformidade {code}.",
            due_date=None,
            source_path=path,
            confidence="alta",
        )

    code_match = NC_CODE_PATTERN.search(path)
    if code_match:
        code = _code_from_match(code_match.group(1), code_match.group(2))
        return ExtractedNonconformity(
            code=code,
            area="Não identificada",
            origin="Documento ISO",
            description=f"Referência {code} encontrada em {Path(path).name}.",
            due_date=None,
            source_path=path,
            confidence="media",
        )
    return None


def extract_nc_from_record(record: FileRecord) -> ExtractedNonconformity | None:
    haystack = f"{record.name} {record.path} {record.extracted_text[:1500]}".lower()
    if (
        record.category != "não conformidade"
        and "rq-tnc" not in haystack
        and "não conform" not in haystack
        and "nao conform" not in haystack
        and not NC_FILE_PATTERN.search(record.name)
    ):
        return None

    from_path = extract_nc_from_path(record.path)
    if from_path:
        description = from_path.description
        if record.extracted_text and len(record.extracted_text) > 40:
            first_lines = " ".join(record.extracted_text.splitlines()[:5])[:400]
            description = first_lines or description
        return ExtractedNonconformity(
            code=from_path.code,
            area=from_path.area,
            origin=from_path.origin,
            description=description,
            due_date=from_path.due_date,
            source_path=record.path,
            confidence=from_path.confidence,
        )

    code_match = NC_CODE_PATTERN.search(record.extracted_text[:3000])
    if code_match:
        code = _code_from_match(code_match.group(1), code_match.group(2))
        return ExtractedNonconformity(
            code=code,
            area="Não identificada",
            origin="Conteúdo do documento",
            description=record.extracted_text[:500],
            due_date=None,
            source_path=record.path,
            confidence="media",
        )
    return None
