@echo off
title SEC-OPS V8 Backend Server (Port 8000)
cd /d "%~dp0"

echo ==============================================================================
echo Starting SEC-OPS V8 Backend on http://127.0.0.1:8000
echo Connecting to Supabase PostgreSQL...
echo ==============================================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
)

pause
