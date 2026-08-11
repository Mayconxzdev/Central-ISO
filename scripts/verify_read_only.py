from pathlib import Path
import os
import sys

root = Path(os.environ.get("ISO_SHARE_PATH", "./demo_iso")).resolve()
probe = root / "__central_iso_write_probe__.tmp"
try:
    probe.write_text("probe", encoding="utf-8")
except PermissionError:
    print(f"OK: {root} está somente leitura para o processo.")
    sys.exit(0)
except OSError as exc:
    print(f"OK/AVISO: escrita bloqueada por erro do sistema: {exc}")
    sys.exit(0)
else:
    probe.unlink(missing_ok=True)
    print(f"FALHA: {root} permite escrita. Em produção, monte o compartilhamento com :ro e use conta apenas leitora.")
    sys.exit(1)
