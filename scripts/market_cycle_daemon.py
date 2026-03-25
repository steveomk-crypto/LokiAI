#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import json
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
STOP_REASON = None


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def log(message: str) -> None:
    try:
        SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open('a', encoding='utf-8') as fh:
            fh.write(f"{iso_now()} - {message}\n")
    except Exception:
        pass


def write_heartbeat(state: str, extra: dict | None = None) -> None:
    try:
        payload = {
            'timestamp': iso_now(),
            'pid': os.getpid(),
            'state': state,
            'sleep_seconds': SLEEP_SECONDS,
        }
        if extra:
            payload.update(extra)
        SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


def cleanup(signum: int | None = None, *_: object) -> None:
    global STOP, STOP_REASON
    STOP = True
    sig_name = None
    if signum is not None:
        try:
            sig_name = signal.Signals(signum).name
        except Exception:
            sig_name = str(signum)
    STOP_REASON = sig_name or 'unknown_signal'
    log(f'received stop signal: {STOP_REASON}')
    write_heartbeat('stop_requested', {'signal': STOP_REASON})


def remove_pid() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass


def _pid_is_live_daemon(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        cmdline = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'args='],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        return bool(cmdline and 'market_cycle_daemon.py' in cmdline)
    except Exception:
        return False


def ensure_singleton() -> None:
    heartbeat_pid = None
    if HEARTBEAT_FILE.exists():
        try:
            heartbeat = json.loads(HEARTBEAT_FILE.read_text())
            heartbeat_pid = int(heartbeat.get('pid')) if heartbeat.get('pid') is not None else None
        except Exception:
            heartbeat_pid = None

    pid_candidates = []
    if PID_FILE.exists():
        try:
            pid_candidates.append(int(PID_FILE.read_text().strip()))
        except Exception:
            pass
    if heartbeat_pid:
        pid_candidates.append(heartbeat_pid)

    for existing_pid in pid_candidates:
        if _pid_is_live_daemon(existing_pid):
            PID_FILE.write_text(str(existing_pid))
            log(f'market cycle daemon already running as PID {existing_pid}')
            sys.exit(1)

    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        HEARTBEAT_FILE.unlink(missing_ok=True)
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
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    ensure_singleton()
    SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    write_heartbeat('started')
    log(f'market cycle daemon started (PID {os.getpid()})')

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
        log(f'market cycle daemon stopping ({STOP_REASON or "requested"})')
        write_heartbeat('stopping', {'signal': STOP_REASON or 'requested'})
        return 0
    finally:
        remove_pid()


if __name__ == '__main__':
    raise SystemExit(main())
