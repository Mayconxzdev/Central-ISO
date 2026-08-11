@echo off
cd /d %~dp0\..
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
set DATABASE_URL=sqlite:///./central_iso_demo.db
set ISO_SHARE_PATH=%CD%\demo_iso
set AI_MODE=disabled
start http://127.0.0.1:8877
python -m uvicorn app.main:app --host 127.0.0.1 --port 8877
