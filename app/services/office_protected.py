from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .paths import filesystem_path


OFFICE_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".doc", ".xls"}


def protected_password() -> str:
    return os.getenv("ISO_PROTECTED_FILE_PASSWORD", "")


def is_office_encrypted(path: Path) -> bool:
    try:
        import msoffcrypto

        with open(filesystem_path(path), "rb") as stream:
            return bool(msoffcrypto.OfficeFile(stream).is_encrypted())
    except Exception:
        return False


@contextmanager
def readable_office_path(path: Path) -> Iterator[tuple[Path, str]]:
    if path.suffix.lower() not in OFFICE_EXTENSIONS:
        yield path, "nao protegido"
        return

    try:
        encrypted = is_office_encrypted(path)
    except Exception:
        encrypted = False
    if not encrypted:
        yield path, "nao protegido"
        return

    password = protected_password()
    if not password:
        yield path, "protegido, senha nao configurada"
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="central_iso_office_"))
    copied = temp_dir / path.name
    decrypted = temp_dir / f"decrypted{path.suffix.lower()}"
    try:
        import msoffcrypto
        from msoffcrypto import exceptions

        shutil.copyfile(filesystem_path(path), copied)
        with open(copied, "rb") as encrypted_stream:
            office = msoffcrypto.OfficeFile(encrypted_stream)
            try:
                office.load_key(password=password, verify_password=True)
            except exceptions.InvalidKeyError:
                yield path, "protegido, senha nao funcionou"
                return
            with open(decrypted, "wb") as output:
                office.decrypt(output, verify_integrity=True)
        yield decrypted, "protegido e lido"
    except Exception as exc:  # noqa: BLE001
        yield path, f"falha de descriptografia: {exc.__class__.__name__}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
