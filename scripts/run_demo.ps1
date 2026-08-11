$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./central_iso_demo.db"
$env:ISO_SHARE_PATH = (Resolve-Path ".\demo_iso").Path
$env:AI_MODE = "disabled"
Start-Process "http://127.0.0.1:8877"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8877
