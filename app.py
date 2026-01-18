import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def _check_backend_deps(python_bin: str) -> bool:
    check_code = (
        "import importlib.util,sys;"
        "mods=['fastapi','uvicorn','dotenv','apscheduler'];"
        "missing=[m for m in mods if importlib.util.find_spec(m) is None];"
        "print('Missing modules: ' + ', '.join(missing) if missing else 'OK');"
        "sys.exit(1 if missing else 0)"
    )
    result = subprocess.run(
        [python_bin, "-c", check_code],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Backend dependencies missing. Please install requirements in your xmind env.")
        print(result.stdout.strip() or result.stderr.strip())
        return False
    return True

def _check_frontend_deps(repo_root: Path) -> bool:
    if shutil.which("npm") is None:
        print("npm not found. Please install Node.js and npm first.")
        return False
    node_modules = repo_root / "ui" / "node_modules"
    if not node_modules.exists():
        print("Frontend dependencies missing. Please run: cd ui && npm install")
        return False
    return True

def start(duration: Optional[int] = None):
    # 1. Start Backend
    print("Starting Backend (FastAPI)...")
    python_bin = os.environ.get("XMIND_PYTHON") or sys.executable
    if not _check_backend_deps(python_bin):
        return
    repo_root = Path(__file__).resolve().parent
    backend_cmd = [
        python_bin,
        str(repo_root / "src" / "server.py")
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(repo_root))

    # 2. Start Frontend
    print("Starting Frontend (Vite)...")
    if not _check_frontend_deps(repo_root):
        backend_proc.terminate()
        return
    frontend_cmd = ["npm", "run", "dev"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(repo_root / "ui"))

    print("\n" + "="*40)
    print("Academic Flow System is starting!")
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:3000")
    print("="*40)
    print("Press Ctrl+C to stop both.")

    try:
        start_time = time.time()
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("\nBackend exited unexpectedly. Check logs in _logs/server.log")
                break
            if frontend_proc.poll() is not None:
                print("\nFrontend exited unexpectedly. Check npm output and ensure dependencies are installed.")
                break
            if duration is not None and (time.time() - start_time) >= duration:
                print("\nAuto-stopping after duration...")
                break
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.terminate()
        for proc in (backend_proc, frontend_proc):
            try:
                proc.wait(timeout=5)
            except Exception:
                if proc.poll() is None:
                    proc.kill()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Academic Flow system")
    parser.add_argument("--duration", type=int, default=None, help="Auto-stop after N seconds")
    args = parser.parse_args()
    start(duration=args.duration)
