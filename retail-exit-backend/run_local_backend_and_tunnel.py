#!/usr/bin/env python3
"""
SEC-OPS V8 — Local Backend & Cloudflare Tunnel Runner
Starts the FastAPI Uvicorn backend connected to Supabase and creates an instant,
free HTTPS/WSS public tunnel via Cloudflare Quick Tunnels for your Vercel deployment.
"""

import os
import sys

# Force UTF-8 encoding on standard streams to avoid Windows charmap errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import re
import signal
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

CLOUDFLARED_BIN = os.path.join(SCRIPT_DIR, "cloudflared.exe")

def main():
    print("=" * 80)
    print("   SEC-OPS V8 -- HYBRID LOCAL BACKEND + SUPABASE + CLOUD TUNNEL LAUNCHER")
    print("=" * 80)

    if not os.path.exists(CLOUDFLARED_BIN):
        print(f"[-] Error: cloudflared.exe not found in {SCRIPT_DIR}")
        sys.exit(1)

    print("[*] 1. Launching FastAPI backend (uvicorn on port 8000)...")
    venv_python = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe")
    python_bin = venv_python if os.path.exists(venv_python) else sys.executable

    log_path = os.path.join(SCRIPT_DIR, "backend_service.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    backend_proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for backend to be fully responsive
    import urllib.request
    import json

    print("[*] Waiting for backend to initialize and connect to Supabase...")
    backend_ready = False
    for attempt in range(40):
        if backend_proc.poll() is not None:
            print("[-] Backend failed to start. Logs from backend_service.log:")
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    print(f.read())
            except Exception:
                pass
            sys.exit(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
                if response.status == 200:
                    backend_ready = True
                    break
        except Exception:
            time.sleep(1)

    if not backend_ready:
        print("[-] Backend did not become healthy within 35 seconds.")
        backend_proc.kill()
        sys.exit(1)

    print("[+] Backend is HEALTHY on http://127.0.0.1:8000 (Connected to Supabase PostgreSQL)")

    print("[*] 2. Establishing secure Cloudflare tunnel to port 8000...")
    tunnel_proc = subprocess.Popen(
        [CLOUDFLARED_BIN, "tunnel", "--url", "http://127.0.0.1:8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read tunnel stderr until URL is discovered
    for line in iter(tunnel_proc.stderr.readline, ''):
        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            break

    if not tunnel_url:
        print("[-] Failed to retrieve public tunnel URL from Cloudflare.")
        tunnel_proc.kill()
        backend_proc.kill()
        sys.exit(1)

    wss_url = tunnel_url.replace("https://", "wss://")

    env_content = f"""# ==============================================================================
# SEC-OPS V8 — VERCEL FRONTEND ENVIRONMENT CONFIGURATION (LIVE TUNNEL)
# ==============================================================================
BACKEND_API_URL="{tunnel_url}"
NEXT_PUBLIC_API_URL="{tunnel_url}"
NEXT_PUBLIC_API_BASE_URL="{tunnel_url}"
NEXT_PUBLIC_WS_URL="{wss_url}"
NEXT_PUBLIC_SUPABASE_URL="https://xbxwwqhgyxofkvfnkdlz.supabase.co"
DATABASE_URL="postgresql://postgres:Kunnal%40%23123@db.xbxwwqhgyxofkvfnkdlz.supabase.co:5432/postgres"
NODE_ENV="production"
"""

    env_output_file = os.path.join(os.path.dirname(SCRIPT_DIR), "vercel_env_ready.txt")
    try:
        with open(env_output_file, "w", encoding="utf-8") as f:
            f.write(env_content)
    except Exception:
        pass

    print("\n" + "=" * 80)
    print("SUCCESS! YOUR LOCAL BACKEND IS NOW ONLINE & REACHABLE BY VERCEL")
    print("=" * 80)
    print(f"  * Public HTTPS URL : {tunnel_url}")
    print(f"  * Public WSS URL   : {wss_url}")
    print(f"  * Local API Docs   : http://127.0.0.1:8000/docs")
    print(f"  * Database         : Supabase PostgreSQL (xbxwwqhgyxofkvfnkdlz)")
    print(f"  * Saved File       : {env_output_file}")
    print("=" * 80)
    print("\nCOPY AND PASTE THIS EXACT BLOCK INTO VERCEL PROJECT ENVIRONMENT VARIABLES:")
    print("-" * 80)
    print(env_content.strip())
    print("-" * 80)
    print("\n[!] Keep this window OPEN while testing your Vercel deployment.")
    print("[!] Press Ctrl+C at any time to gracefully stop the backend and tunnel.\n")

    def handle_shutdown(signum, frame):
        print("\n[*] Shutting down backend and tunnel...")
        try:
            tunnel_proc.terminate()
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        tunnel_proc.wait()
    except KeyboardInterrupt:
        handle_shutdown(None, None)

if __name__ == "__main__":
    main()

