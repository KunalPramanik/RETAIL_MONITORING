@echo off
title SEC-OPS V8 Local Backend + Supabase Tunnel
cd /d "%~dp0"

echo ==============================================================================
echo Starting SEC-OPS V8 Local Backend and Cloudflare Tunnel for Vercel...
echo ==============================================================================

taskkill /F /IM cloudflared.exe >nul 2>&1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_local_backend_and_tunnel.py
) else (
    python run_local_backend_and_tunnel.py
)

pause
