"""Start the local growthOS services after checking the database migration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"


def responds(url: str, marker: bytes) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200 and marker in response.read(200_000)
    except (OSError, urllib.error.URLError):
        return False


def start(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    output = (RUNTIME / f"{name}.log").open("ab")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        env=env,
    )
    output.close()
    (RUNTIME / f"{name}.pid.json").write_text(
        json.dumps({"pid": process.pid, "started": time.time()}), encoding="utf-8"
    )
    print(f"{name}: starting (PID {process.pid})")
    return process


def main() -> int:
    RUNTIME.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(RUNTIME / "uv-cache"))
    backend = "http://127.0.0.1:8000/health"
    frontend = "http://localhost:3000"

    def backend_ready() -> bool:
        return responds(backend, b'"database":"ok"')

    def frontend_ready() -> bool:
        return responds(frontend, b"growthOS")

    uv = "uv"
    started = []
    if not backend_ready():
        result = subprocess.run(
            [uv, "run", "python", "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            check=False,
            env=env,
        )
        if result.returncode:
            print("Database migration failed; backend was not started.", file=sys.stderr)
            return result.returncode
        started.append(
            start(
                "backend",
                [
                    uv,
                    "run",
                    "python",
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                ROOT / "backend",
                env,
            )
        )
    else:
        print("backend: already responding")
    if not frontend_ready():
        npm = "npm.cmd" if os.name == "nt" else "npm"
        started.append(start("frontend", [npm, "run", "dev"], ROOT / "frontend", env))
    else:
        print("frontend: already responding")
    for _ in range(60):
        if backend_ready() and frontend_ready():
            webbrowser.open(frontend)
            print("growthOS ready at", frontend)
            return 0
        for process in started:
            if process.poll() is not None:
                print("A service exited during startup. Check .runtime logs.", file=sys.stderr)
                return 1
        time.sleep(1)
    print("Services did not respond. Check .runtime logs.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
