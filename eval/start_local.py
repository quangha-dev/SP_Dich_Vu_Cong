"""Start the local frontend and backend as detached Windows processes."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = REPO_ROOT / "codebase" / "frontend"
VITE_ENTRY = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
PID_FILE = EVAL_DIR / "local-processes.json"


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.25)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def clean_environment() -> dict[str, str]:
    # Windows variables are case-insensitive. Normalizing avoids Path/PATH
    # duplicate-key failures seen in PowerShell Start-Process.
    return {key.upper(): value for key, value in os.environ.items()}


def spawn(command: list[str], cwd: Path, log_name: str, extra_env: dict[str, str] | None = None) -> int:
    environment = clean_environment()
    environment.update(extra_env or {})
    log_path = EVAL_DIR / log_name
    log_handle = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=(
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            ),
        )
    finally:
        log_handle.close()
    return process.pid


def main() -> None:
    node = shutil.which("node.exe") or shutil.which("node") or r"D:\DEV\Kit\Node.js\node.exe"
    if not Path(node).is_file():
        raise SystemExit("node_not_found")
    if not VITE_ENTRY.is_file():
        raise SystemExit("vite_not_installed")

    processes: dict[str, dict[str, int | str]] = {}
    if port_open(8000):
        processes["backend"] = {"pid": 0, "port": 8000, "status": "already_running"}
    else:
        pid = spawn(
            [sys.executable, "-m", "uvicorn", "local_backend:app", "--host", "127.0.0.1", "--port", "8000"],
            EVAL_DIR,
            "local-backend.log",
        )
        processes["backend"] = {"pid": pid, "port": 8000, "status": "started"}

    if port_open(5173):
        processes["frontend"] = {"pid": 0, "port": 5173, "status": "already_running"}
    else:
        pid = spawn(
            [node, str(VITE_ENTRY), "--host", "127.0.0.1", "--port", "5173"],
            FRONTEND_DIR,
            "local-frontend.log",
            {"VITE_API_BASE_URL": "http://localhost:8000/api"},
        )
        processes["frontend"] = {"pid": pid, "port": 5173, "status": "started"}

    PID_FILE.write_text(json.dumps(processes, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(processes, indent=2))


if __name__ == "__main__":
    main()
