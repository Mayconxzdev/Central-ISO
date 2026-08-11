from __future__ import annotations

from pathlib import PurePath


TEMP_SUFFIXES = ("~", ".tmp", ".temp", ".dwl", ".dwl2", ".crdownload", ".part")
BACKUP_MARKERS = (".bak", ".backup", ".old", ".bkp")


def normalize_extension(filename: str) -> str:
    name = PurePath(str(filename).strip()).name.strip()
    if not name:
        return "sem extensao"
    lower = name.lower()
    if lower in {".", ".."}:
        return "sem extensao"
    if lower.startswith(".") and lower.count(".") == 1:
        return "sem extensao"
    if lower.endswith("."):
        return "nome terminado em ponto"
    if lower.endswith(TEMP_SUFFIXES):
        return "temporario"
    if any(marker in lower for marker in BACKUP_MARKERS):
        return "backup"

    suffix = PurePath(lower).suffix.strip()
    if not suffix:
        return "sem extensao"
    if len(suffix) > 16:
        return "extensao invalida"
    if any(ch in suffix for ch in ("\\", "/", ":", "*", "?", '"', "<", ">", "|", " ", "[", "]")):
        return "extensao invalida"
    if suffix[1:].isdigit():
        return "extensao invalida"
    return suffix


def extension_category(extension: str) -> str:
    ext = extension.lower().strip()
    if ext == ".pdf":
        return "pdf"
    if ext in {".doc", ".docx"}:
        return "word"
    if ext in {".xls", ".xlsx", ".xlsm"}:
        return "excel"
    if ext == ".csv":
        return "csv"
    if ext in {".txt", ".md", ".log"}:
        return "txt"
    if ext == ".odt":
        return "odt"
    if ext == ".rtf":
        return "rtf"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"}:
        return "imagens"
    if ext in {".dwg", ".dxf", ".odg", ".step", ".stp", ".iges", ".igs", ".sldprt", ".sldasm"}:
        return "CAD/engenharia"
    if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "compactados"
    if ext in {".exe", ".dll", ".msi", ".bat", ".cmd", ".ps1", ".lnk"}:
        return "executaveis/sistema"
    if ext == "temporario":
        return "temporarios"
    if ext == "backup":
        return "backup"
    if ext in {"sem extensao", "nome terminado em ponto"}:
        return "sem extensao"
    if ext == "extensao invalida":
        return "extensao invalida"
    return "outros"
