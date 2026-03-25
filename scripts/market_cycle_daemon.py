#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_LOG_DIR = ROOT / 'system_logs'
LOG_FILE = SYSTEM_LOG_DIR / 'market_loop_cron.log'
PID_FILE = SYSTEM_LOG_DIR / 'market_cycle_daemon.pid'
HEARTBEAT_FILE = SYSTEM_LOG_DIR / 'market_cycle_heartbeat.json'
RUNNER = ROOT / 'scripts' / 'run_core_cycle.sh'
SLEEP_SECONDS = 30
STOP = False


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def log(message: str) -> None:
    SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('a', encoding='utf-8') as fh:
        fh.write(f"{iso_now()} - {message}\n")


def write_heartbeat(state: str, extra: dict | None = None) -> None:
    payload = {
        'timestamp': iso_now(),
        'pid': os.getpid(),
        'state': state,
        'sleep_seconds': SLEEP_SECONDS,
    }
    if extra:
        payload.update(extra)
    HEARTBEAT_FILE.write_text(__import__('json').dumps(payload, indent=2))


def cleanup(*_: object) -> None:
    global STOP
    STOP = True


def remove_pid() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass


def ensure_singleton() -> None:
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text().strip())
            cmdline = subprocess.run(
                ['ps', '-p', str(existing_pid), '-o', 'args='],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if cmdline and 'market_cycle_daemon.py' in cmdline:
                log(f'market cycle daemon already running as PID {existing_pid}')
                sys.exit(1)
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass


def run_cycle() -> int:
    log('invoking run_core_cycle.sh')
    write_heartbeat('running_cycle')
    result = subprocess.run(['bash', str(RUNNER)], cwd=ROOT, check=False)
    return result.returncode


def main() -> int:
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    ensure_singleton()
    SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    log(f'market cycle daemon started (PID {os.getpid()})')
    write_heartbeat('started')

    try:
        while not STOP:
            rc = run_cycle()
            if rc != 0:
                log(f'core cycle exited with status {rc}')
                write_heartbeat('cycle_failed', {'exit_code': rc})
            else:
                log(f'cycle finished, sleeping {SLEEP_SECONDS}s')
                write_heartbeat('sleeping')
            for _ in range(SLEEP_SECONDS):
                if STOP:
                    break
                time.sleep(1)
        log('market cycle daemon stopping')
        write_heartbeat('stopping')
        return 0
    finally:
        remove_pid()


if __name__ == '__main__':
    raise SystemExit(main())
