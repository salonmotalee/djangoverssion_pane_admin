"""Exercise the real application in Chromium with a disposable database.

Build the frontend first. Ports 8000 and 3000 must be free. No application data
or credentials are retained; artifacts (screenshots and logs) are gitignored.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ARTIFACTS = ROOT / "e2e" / "artifacts"
VENV_PYTHON = "Scripts/python.exe" if os.name == "nt" else "bin/python"
PYTHON = next(
    (
        path
        for path in (ROOT / ".venv" / VENV_PYTHON, BACKEND / ".venv" / VENV_PYTHON)
        if path.is_file()
    ),
    BACKEND / ".venv" / VENV_PYTHON,
)
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm")


def wait_ready(url: str, process: subprocess.Popen, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Server exited ({process.returncode}); inspect {ARTIFACTS}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready: {url}; inspect {ARTIFACTS}")


def check_ports() -> None:
    for port in (8000, 3000):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(
                    f"Port {port} is occupied; stop your development server before E2E"
                )


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        # Terminate the entire npm -> node process tree on Windows.
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            import signal

            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def exercise(browser, username: str, password: str) -> int:
    """UI workflow; selectors are based on accessible Persian labels."""
    # Completed alongside the UI so the checks use the same actual labels.
    from workflows import run_workflows

    return run_workflows(browser, username, password, ARTIFACTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true", help="Exercise the combined npm development launcher")
    args = parser.parse_args()
    if not PYTHON.is_file() or not NPM:
        raise RuntimeError("Install the backend .venv and Node/npm first (see README)")
    if not args.dev and not (FRONTEND / ".next" / "BUILD_ID").is_file():
        raise RuntimeError("Run npm run build inside frontend first")
    check_ports()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in (
        "backend.log",
        "frontend.log",
        "login.png",
        "dashboard-empty.png",
        "dashboard.png",
        "customers.png",
        "dashboard-mobile.png",
        "failure.png",
        "result.json",
        "tenant-login.png",
        "tenant-dashboard.png",
        "tenant-mobile.png",
        "tenant-failure.png",
    ):
        (ARTIFACTS / name).unlink(missing_ok=True)
    servers: list[subprocess.Popen] = []
    handles = []
    with tempfile.TemporaryDirectory(prefix="madar-e2e-") as temporary:
        env = os.environ.copy()
        env.update(
            DEBUG="1",
            SECRET_KEY=secrets.token_urlsafe(48),
            DATABASE_URL="sqlite:///" + (Path(temporary) / "test.sqlite3").as_posix(),
            ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
            CSRF_TRUSTED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000",
            SESSION_COOKIE_SECURE="false",
            CSRF_COOKIE_SECURE="false",
            SECURE_SSL_REDIRECT="false",
            TRUST_PROXY_HTTPS="false",
            E2E_USERNAME="e2e.supervisor",
            E2E_PASSWORD=secrets.token_urlsafe(24),
        )
        subprocess.run(
            [str(PYTHON), "manage.py", "migrate", "--noinput"],
            cwd=BACKEND,
            env=env,
            check=True,
        )
        subprocess.run(
            [
                str(PYTHON),
                "manage.py",
                "shell",
                "-c",
                (
                    "import os; from django.contrib.auth import get_user_model; "
                    "get_user_model().objects.create_superuser(username=os.environ['E2E_USERNAME'], "
                    "password=os.environ['E2E_PASSWORD'], email='e2e@example.invalid', first_name='آزمایش')"
                ),
            ],
            cwd=BACKEND,
            env=env,
            check=True,
        )
        try:
            services = (
                (
                    "backend",
                    [
                        str(PYTHON),
                        "manage.py",
                        "runserver",
                        "127.0.0.1:8000",
                        "--noreload",
                    ],
                    BACKEND,
                ),
                (
                    "frontend",
                    [
                        str(NPM),
                        "run",
                        "start",
                        "--",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3000",
                    ],
                    FRONTEND,
                ),
            )
            if args.dev:
                services = (("frontend", [str(NPM), "run", "dev", "--", "--port", "3000"], FRONTEND),)
            for name, command, directory in services:
                handle = (ARTIFACTS / f"{name}.log").open("w", encoding="utf-8")
                handles.append(handle)
                servers.append(
                    subprocess.Popen(
                        command,
                        cwd=directory,
                        env=env,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        start_new_session=os.name != "nt",
                    )
                )
            wait_ready("http://127.0.0.1:8000/api/auth/csrf/", servers[0])
            wait_ready("http://127.0.0.1:3000/login", servers[-1])
            with sync_playwright() as playwright:
                executable = os.environ.get("E2E_BROWSER_PATH")
                browser = playwright.chromium.launch(
                    headless=True,
                    **({"executable_path": executable} if executable else {}),
                )
                try:
                    checks = exercise(browser, env["E2E_USERNAME"], env["E2E_PASSWORD"])
                    print(
                        f"E2E: {checks} workflows passed against Django + Next.js (isolated database)"
                    )
                    (ARTIFACTS / "result.json").write_text(
                        json.dumps(
                            {
                                "status": "passed",
                                "mode": "development" if args.dev else "production",
                                "workflows": checks,
                                "completed_at": datetime.now(UTC).isoformat(),
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                finally:
                    browser.close()
        finally:
            for server in reversed(servers):
                stop(server)
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    main()
