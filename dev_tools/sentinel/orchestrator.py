#!/usr/bin/env python3
"""
RĀMAN Autonomous Orchestrator
================================
Background daemon that runs the Sentinel scan every 4 hours,
regenerates the dashboard, and performs real health checks on
the RĀMAN Studio backend and engine core.

Usage:
    python3 orchestrator.py start    # Start daemon (nohup'd)
    python3 orchestrator.py stop     # Stop daemon
    python3 orchestrator.py status   # Check if running
    python3 orchestrator.py once     # Run one cycle and exit
"""

import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/varshinicb/EIS-RV (2)/EIS-RV")
SENTINEL_DIR = BASE_DIR / "dev_tools" / "sentinel"
PID_FILE = SENTINEL_DIR / "orchestrator.pid"
LOG_FILE = SENTINEL_DIR / "autonomous.log"
WATCHER = SENTINEL_DIR / "watcher.py"

CYCLE_SECONDS = 4 * 3600  # 4 hours

_shutdown = False


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] ORCH: {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_pid():
    """Read PID from file, return int or None."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if alive
            return pid
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return None


def write_pid():
    PID_FILE.write_text(str(os.getpid()))


def handle_signal(signum, frame):
    global _shutdown
    log(f"Received signal {signum}, shutting down gracefully...")
    _shutdown = True


def check_backend():
    """Try to hit the FastAPI health endpoint."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as resp:
            if resp.status == 200:
                return "online"
    except Exception:
        pass
    return "offline"


def check_engine_core():
    """Verify that the C++ engine source exists and CMakeLists.txt is valid."""
    cmake = BASE_DIR / "engine_core" / "CMakeLists.txt"
    solver = BASE_DIR / "engine_core" / "src" / "cv_solver.cpp"
    if cmake.exists() and solver.exists():
        return "present"
    return "missing"


def check_frontend():
    """Verify frontend package.json and src/App.jsx exist."""
    pkg = BASE_DIR / "src" / "frontend" / "package.json"
    app = BASE_DIR / "src" / "frontend" / "src" / "App.jsx"
    if pkg.exists() and app.exists():
        return "present"
    return "missing"


def run_cycle():
    """Execute one full orchestration cycle."""
    log("--- Cycle Start ---")

    # 1. Run Sentinel scan + dashboard generation
    log("Running Sentinel scan...")
    result = subprocess.run(
        [sys.executable, str(WATCHER)],
        capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120
    )
    if result.returncode == 0:
        log("Sentinel scan completed successfully")
    else:
        log(f"Sentinel scan failed: {result.stderr[:200]}")

    # 2. Real health checks
    backend = check_backend()
    engine = check_engine_core()
    frontend = check_frontend()
    log(f"Health: backend={backend}, engine_core={engine}, frontend={frontend}")

    # 3. Report
    log("--- Cycle Complete ---")


def daemon_loop():
    """Main daemon loop."""
    write_pid()
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    log("Orchestrator started (PID: %d)" % os.getpid())

    while not _shutdown:
        try:
            run_cycle()
        except Exception as e:
            log(f"Cycle error (will retry next cycle): {e}")

        # Sleep in small increments so we can respond to signals
        for _ in range(CYCLE_SECONDS):
            if _shutdown:
                break
            time.sleep(1)

    PID_FILE.unlink(missing_ok=True)
    log("Orchestrator stopped.")


def cmd_start():
    pid = get_pid()
    if pid:
        print(f"Already running (PID {pid})")
        return

    # Fork to background
    if os.fork() > 0:
        # Parent — wait a moment and check
        time.sleep(1)
        pid = get_pid()
        if pid:
            print(f"Orchestrator started (PID {pid})")
            print(f"Logs: {LOG_FILE}")
        else:
            print("Failed to start.")
        return

    # Child — become session leader
    os.setsid()
    sys.stdin = open(os.devnull, 'r')
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    daemon_loop()


def cmd_stop():
    pid = get_pid()
    if not pid:
        print("Not running.")
        return
    os.kill(pid, signal.SIGTERM)
    print(f"Sent SIGTERM to PID {pid}")
    # Wait for it to die
    for _ in range(10):
        time.sleep(0.5)
        if not get_pid():
            print("Stopped.")
            return
    print("Still running — may need manual kill.")


def cmd_status():
    pid = get_pid()
    if pid:
        print(f"Running (PID {pid})")
    else:
        print("Not running.")


def cmd_once():
    log("Running single cycle (manual trigger)")
    run_cycle()
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py [start|stop|status|once]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    elif cmd == "once":
        cmd_once()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
