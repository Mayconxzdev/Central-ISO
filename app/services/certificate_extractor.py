from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..models import FileRecord

CERT_NUMBER_PATTERN = re.compile(
    r"\b((?:CPEx|IECEx|T[ÜU]V|DNV|INMETRO|UL|ATEX)\s*[\d.A-Za-z\-]+X?)\b",
    re.IGNORECASE,
)
DATE_PATTERNS = (
    re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b"),
    re.compile(r"\b(\d{4})[/-](\d{2})[/-](\d{2})\b"),
)
VALIDITY_HINTS = (
    "validade",
    "valid until",
    "válido até",
    "valido ate",
    "expiry",
    "vencimento",
)


@dataclass(frozen=True)
class ExtractedCertificate:
    number: str
    supplier: str
    component_or_product: str
    valid_until: date | None
    source_path: str
    notes: str
    confidence: str


def _parse_date(day: str, month: str, year: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_date_from_text(text: str) -> date | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        if len(groups[0]) == 4:
            year, month, day = groups
        else:
            day, month, year = groups
        parsed = _parse_date(day, month, year)
        if parsed and parsed.year >= 2000:
            return parsed
    return None


def normalize_cert_number(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    upper = cleaned.upper()
    upper = upper.replace("TUV", "TÜV")
    if upper.startswith("CPEX"):
        return "CPEx" + cleaned[4:].upper()
    if upper.startswith(("IECEX", "INMETRO", "ATEX", "UL")):
        return upper
    return cleaned


def extract_from_filename(name: str, path: str) -> ExtractedCertificate | None:
    number_match = CERT_NUMBER_PATTERN.search(name)
    if not number_match:
        return None
    number = normalize_cert_number(number_match.group(1))
    valid_until = parse_date_from_text(name)
    supplier = ""
    component = ""
    parts = re.split(r"\s*-\s*", Path(name).stem)
    for part in parts:
        upper = part.upper()
        if number.replace(" ", "") in upper.replace(" ", ""):
            continue
        if re.search(r"\bREV\b", upper):
            continue
        if not supplier and len(part.strip()) >= 3:
            supplier = part.strip()
        elif not component and len(part.strip()) >= 3:
            component = part.strip()
    if not component and len(parts) >= 2:
        component = parts[-2].strip() if parts[-2].strip() else parts[0].strip()
    return ExtractedCertificate(
        number=number,
        supplier=supplier,
        component_or_product=component,
        valid_until=valid_until,
        source_path=path,
        notes=f"Detectado automaticamente em {name}.",
        confidence="alta" if valid_until else "media",
    )


def extract_from_pdf_text(name: str, path: str, text: str) -> ExtractedCertificate | None:
    number_match = CERT_NUMBER_PATTERN.search(f"{name} {text[:4000]}")
    if not number_match:
        return None
    number = normalize_cert_number(number_match.group(1))
    valid_until = None
    for line in text.splitlines():
        lower = line.lower()
        if any(hint in lower for hint in VALIDITY_HINTS):
            valid_until = parse_date_from_text(line) or valid_until
    if valid_until is None:
        valid_until = parse_date_from_text(name) or parse_date_from_text(text[:2000])
    supplier = ""
    for line in text.splitlines()[:40]:
        lower = line.lower()
        if any(key in lower for key in ("fabricante", "manufacturer", "titular", "holder")):
            supplier = line.split(":", 1)[-1].strip()[:255] or supplier
    return ExtractedCertificate(
        number=number,
        supplier=supplier,
        component_or_product=Path(name).stem[:255],
        valid_until=valid_until,
        source_path=path,
        notes="Extraído do conteúdo do certificado.",
        confidence="alta" if valid_until else "media",
    )


def extract_from_csv_text(path: str, text: str) -> list[ExtractedCertificate]:
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return []
    normalized_fields = {name.lower().strip(): name for name in reader.fieldnames if name}
    number_key = next((normalized_fields[k] for k in normalized_fields if "num" in k or "cert" in k), None)
    supplier_key = next((normalized_fields[k] for k in normalized_fields if "forn" in k or "fabri" in k), None)
    component_key = next((normalized_fields[k] for k in normalized_fields if "comp" in k or "prod" in k), None)
    validity_key = next((normalized_fields[k] for k in normalized_fields if "valid" in k or "venc" in k), None)
    if not number_key:
        return []

    extracted: list[ExtractedCertificate] = []
    for row in reader:
        number_raw = (row.get(number_key) or "").strip()
        if not number_raw:
            continue
        number = normalize_cert_number(number_raw)
        valid_until = parse_date_from_text(row.get(validity_key or "") or "")
        extracted.append(
            ExtractedCertificate(
                number=number,
                supplier=(row.get(supplier_key or "") or "").strip(),
                component_or_product=(row.get(component_key or "") or "").strip(),
                valid_until=valid_until,
                source_path=path,
                notes=f"Importado de lista tabular em {datetime.now():%d/%m/%Y}.",
                confidence="alta" if valid_until else "media",
            )
        )
    return extracted


def extract_certificates_from_record(record: FileRecord) -> list[ExtractedCertificate]:
    name = record.name
    path = record.path
    haystack = f"{name} {path}".lower()
    is_cert_context = record.category == "certificado" or any(
        needle in haystack for needle in ("cpex", "certificado", "produto ex", "iecex", "tuv", "dnv")
    )
    if not is_cert_context:
        return []

    if record.extension == ".csv":
        return extract_from_csv_text(path, record.extracted_text)

    from_filename = extract_from_filename(name, path)
    if from_filename:
        results = [from_filename]
    else:
        results = []

    if record.extension == ".pdf" and record.extracted_text and len(record.extracted_text) > 80:
        from_text = extract_from_pdf_text(name, path, record.extracted_text)
        if from_text and all(item.number != from_text.number for item in results):
            results.append(from_text)

    return results
