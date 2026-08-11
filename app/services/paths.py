from __future__ import annotations

import os
from pathlib import Path


def filesystem_path(path: Path | str) -> str:
    """Return a Windows-safe path for local filesystem calls without changing stored evidence paths."""
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value.lstrip("\\")
    if len(value) >= 240:
        return "\\\\?\\" + value
    return value
