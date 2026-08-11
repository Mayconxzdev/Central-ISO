from __future__ import annotations

from pathlib import PurePath

from .file_types import extension_category


NOISE_PATH_MARKERS = (
    "@recycle",
    "arquivo morto",
    "lixeira",
    "$recycle.bin",
    "/temp/",
    "\\temp\\",
    "/tmp/",
    "\\tmp\\",
)

NOISE_NAME_PREFIXES = ("~$", "~lock")
NOISE_NAME_SUFFIXES = (".dwl", ".dwl2", ".tmp", ".temp", ".crdownload", ".part")

PRIORITY_CATEGORIES = {
    "certificado",
    "não conformidade",
    "calibração",
    "competência",
    "fornecedor",
    "procedimento",
    "instrução de trabalho",
    "manual",
    "rac",
    "auditoria",
    "treinamento",
}


def is_noise_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if any(marker in normalized for marker in NOISE_PATH_MARKERS):
        return True
    name = PurePath(path).name.lower()
    if name.startswith(NOISE_NAME_PREFIXES):
        return True
    if name.endswith(NOISE_NAME_SUFFIXES):
        return True
    return False


def is_noise_file(name: str, path: str, extension: str) -> bool:
    if is_noise_path(path):
        return True
    if extension_category(extension) in {"temporarios", "backup", "executaveis/sistema"}:
        return True
    lower = name.lower()
    if lower.startswith("~$") or lower.startswith("~lock"):
        return True
    return False


def is_priority_document(category: str, path: str, name: str) -> bool:
    if is_noise_path(path):
        return False
    if (category or "").lower() in PRIORITY_CATEGORIES:
        return True
    haystack = f"{path} {name}".lower()
    return any(
        needle in haystack
        for needle in ("rq-tnc", "cpex", "certificado", "calibra", "rq-mac", "rq-gic", "rq-gcm")
    )
