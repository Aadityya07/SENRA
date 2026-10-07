@echo off
REM Launch SENRA: FastAPI backend (port 8000) + React frontend (port 5173).
cd /d "%~dp0"

start "SENRA backend" cmd /k "backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"
start "SENRA frontend" cmd /k "cd frontend && npm run dev"

echo Waiting for the servers to start...
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
