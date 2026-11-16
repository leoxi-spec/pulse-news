#!/usr/bin/env python3
"""Install Pulse as a macOS login service.

The installed Chrome app talks to http://localhost:8787. When that Python
process is not running, the app can only show its offline screen. This tool
registers a per-user LaunchAgent so the server starts at login and is
restarted if it crashes.

    python3 tools/install_launch_agent.py
    python3 tools/install_launch_agent.py --uninstall

Only the current user is touched. No administrator password is needed.
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LABEL = "com.pulse.studentnews"
HOST = "127.0.0.1"
PORT = 8787
ROOT = Path(__file__).resolve().parent.parent
PYTHON = Path(sys.executable).resolve()
SUPPORT = Path.home() / "Library" / "Application Support" / "Pulse"
LOGS = Path.home() / "Library" / "Logs" / "Pulse"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LAUNCHER = SUPPORT / "pulse-server.sh"
LSOF = shutil.which("lsof") or "/usr/sbin/lsof"


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


def _uid() -> int:
    return os.getuid()


def _bootout() -> None:
    _run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"])


def _listener_pid() -> int | None:
    if not Path(LSOF).exists():
        return None
    result = _run([LSOF, "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t"])
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def _is_our_server(pid: int) -> bool:
    """Only stop a listener that is clearly this checkout's run.py."""
    result = _run([LSOF, "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    cwd = ""
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            cwd = line[1:]
    if not cwd:
        return False
    try:
        if Path(cwd).resolve() != ROOT.resolve():
            return False
    except OSError:
        return False
    command = _run(["ps", "-p", str(pid), "-o", "command="]).stdout
    return "run.py" in command


def _stop_our_server() -> None:
    pid = _listener_pid()
    if pid is None:
        return
    if not _is_our_server(pid):
        raise SystemExit(
            f"Port {PORT} is already used by another program (pid {pid}). "
            "Stop it first, then run this installer again."
        )
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if _listener_pid() is None:
            return
        time.sleep(0.25)
    os.kill(pid, signal.SIGKILL)
    time.sleep(0.5)


def _launcher_text() -> str:
    root = shlex.quote(str(ROOT))
    python = shlex.quote(str(PYTHON))
    return f"""#!/bin/sh
# Pulse — Student News local server. Installed by tools/install_launch_agent.py.
set -u
if {shlex.quote(LSOF)} -nP -iTCP:{PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
  # A server is already listening. Exit successfully so KeepAlive does not spin.
  exit 0
fi
cd {root} || exit 1
exec {python} {shlex.quote(str(ROOT / 'run.py'))} --host {HOST} --port {PORT}
"""


def _plist_payload() -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/sh", str(LAUNCHER)],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        # Restart after a crash, but do not fight an existing healthy server.
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "ProcessType": "Interactive",
        "StandardOutPath": str(LOGS / "server.log"),
        "StandardErrorPath": str(LOGS / "server.log"),
        "EnvironmentVariables": {
            "PATH": f"{PYTHON.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONUNBUFFERED": "1",
        },
    }


def _wait_healthy(timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/health", timeout=3) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)
    return False


def install() -> None:
    SUPPORT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)

    _bootout()
    _stop_our_server()

    LAUNCHER.write_text(_launcher_text(), encoding="utf-8")
    LAUNCHER.chmod(0o755)
    PLIST.write_bytes(plistlib.dumps(_plist_payload(), fmt=plistlib.FMT_XML))

    result = _run(["launchctl", "bootstrap", f"gui/{_uid()}", str(PLIST)])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "launchctl bootstrap failed")
    _run(["launchctl", "enable", f"gui/{_uid()}/{LABEL}"])
    _run(["launchctl", "kickstart", "-k", f"gui/{_uid()}/{LABEL}"])

    if not _wait_healthy():
        tail = ""
        log = LOGS / "server.log"
        if log.exists():
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
        raise SystemExit(f"Pulse was installed but did not answer on port {PORT}.\n{tail}")

    print(f"Pulse starts at login and restarts after a crash.")
    print(f"  service  {LABEL}")
    print(f"  server   http://{HOST}:{PORT}")
    print(f"  log      {LOGS / 'server.log'}")


def uninstall() -> None:
    _bootout()
    _stop_our_server()
    for path in (PLIST, LAUNCHER):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    print("Pulse login service removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Pulse as a macOS login service")
    parser.add_argument("--uninstall", action="store_true", help="remove the login service")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("This installer is for macOS. Use systemd on Linux.")
    uninstall() if args.uninstall else install()


if __name__ == "__main__":
    main()
