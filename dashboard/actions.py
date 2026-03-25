from __future__ import annotations

import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

from .runtime_registry import COMPONENTS
from .data import read_runtime_controls
from .modes import get_modes, set_mode
from scripts.x_actions import generate_draft, inspect_x, post_latest_queue, queue_latest_draft
from scripts.telegram_lanes import load_telegram_lanes


def run_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_script(script_name: str) -> Tuple[bool, str]:
    root = run_root()
    script = root / 'scripts' / script_name
    if not script.exists():
        return False, f'Missing script: {script_name}'
    result = subprocess.run(['bash', str(script)], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or f'Failed to run {script_name}').strip()
        return False, message
    output = (result.stdout or '').strip()
    return True, output.splitlines()[0].strip() if output else f'Started {script_name}'


def open_path(path: Path) -> Tuple[bool, str]:
    path.mkdir(parents=True, exist_ok=True) if path.suffix == '' else path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(['xdg-open', str(path)])
        return True, f'Opened {path}'
    except Exception:
        return True, f'Path: {path}'


def run_background_command(command: str, pid_file: str, log_file: str, detached: bool = False) -> Tuple[bool, str]:
    root = run_root()
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(pid_file).parent.mkdir(parents=True, exist_ok=True)
    launcher = 'nohup bash -lc' if not detached else 'nohup setsid bash -lc'
    wrapped = f"{launcher} {command!r} >> {log_file!r} 2>&1 < /dev/null & echo $! > {pid_file!r}"
    result = subprocess.run(['bash', '-lc', wrapped], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or 'Failed to start background command').strip()
    return True, f'Started background job ({Path(pid_file).name})'


def _is_recent_iso(value: str | None, max_age_seconds: int) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() <= max_age_seconds
    except Exception:
        return False


def stop_pid(pid_file: str) -> Tuple[bool, str]:
    path = Path(pid_file)
    if not path.exists():
        return False, 'PID file not found'
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        return True, f'Stopped PID {pid}'
    except ProcessLookupError:
        return True, 'Process already exited'
    except Exception as exc:
        return False, str(exc)


def perform_component_action(component_id: str, action: str) -> Tuple[bool, str]:
    runtime = read_runtime_controls()
    root = run_root()
    comp = COMPONENTS.get(component_id)
    mode_components = {'market_broadcaster', 'telegram_sender', 'x_autoposter', 'performance_analyzer', 'sol_shadow_logger'}

    if not comp:
        return False, f'{component_id} control not wired yet'

    if component_id in mode_components and action in {'enable', 'disable'}:
        enabled = action == 'enable'
        set_mode(component_id, enabled)
        return True, f"{comp.name} {'enabled' if enabled else 'disabled'}"

    if action == 'start' and component_id != 'main_loop' and runtime.get(component_id, {}).get('controls_blocked'):
        return False, f"Blocked by dependencies: {runtime[component_id].get('blocked_reason')}"

    if component_id == 'main_loop':
        if action == 'start':
            loop_entry = runtime.get('main_loop', {})
            pid_file = root / 'system_logs' / 'market_cycle_daemon.pid'
            log_file = root / 'system_logs' / 'market_loop_cron.log'
            cycle_recent = _is_recent_iso(loop_entry.get('last_success_at') or (loop_entry.get('log_meta') or {}).get('updated_at'), 90)
            stale_loop = bool(pid_file.exists()) and not cycle_recent
            if stale_loop:
                try:
                    pid = int(pid_file.read_text().strip())
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                except Exception:
                    pass
                try:
                    pid_file.unlink(missing_ok=True)
                except Exception:
                    pass

            ok1, msg1 = run_background_command(
                'python3 ./scripts/market_cycle_daemon.py',
                str(pid_file),
                str(log_file),
                detached=True,
            )
            ok2, msg2 = run_background_command(
                './scripts/output_cycle_daemon.sh',
                str(root / 'system_logs' / 'output_cycle.pid'),
                str(root / 'system_logs' / 'output_cycle.log'),
            )
            ok3, msg3 = run_background_command(
                './scripts/telegram_summary_daemon.sh',
                str(root / 'system_logs' / 'telegram_summary.pid'),
                str(root / 'system_logs' / 'telegram_summary.log'),
            )
            stale_note = ' (restarted stale loop daemon)' if stale_loop else ''
            return (ok1 and ok2 and ok3), f"core: {msg1}{stale_note} | outputs: {msg2} | telegram: {msg3}"
        if action == 'run_cycle':
            return run_script('run_core_cycle.sh')
        if action == 'stop':
            msgs = []
            ok = True
            for cid in ['main_loop', 'output_cycle', 'telegram_summary_cycle']:
                pid_file = runtime.get(cid, {}).get('pid_file')
                if pid_file:
                    stopped, msg = stop_pid(str(pid_file))
                    ok = ok and stopped
                    msgs.append(f"{cid}: {msg}")
            return ok, ' | '.join(msgs) if msgs else 'No automation daemons found'
        return open_path(comp.inspect_target or root / 'system_logs' / 'market_loop_cron.log')

    if component_id == 'paper_trader_v2' and action == 'flatten':
        return run_script('flatten_paper_trader.sh')

    if component_id == 'position_manager' and action == 'start':
        return run_script('run_market_cycle.sh')

    if component_id == 'x_autoposter' and action == 'draft':
        result = generate_draft('build_in_public')
        return True, f"{result['message']} ({Path(result['draft_path']).name})"

    if component_id == 'x_autoposter' and action == 'queue':
        result = queue_latest_draft()
        return True, f"{result['message']} ({Path(result['queue_path']).name})"

    if component_id == 'x_autoposter' and action == 'post_now':
        result = post_latest_queue()
        return True, f"{result['message']} [{result.get('mode')}]"

    if component_id == 'x_autoposter' and action == 'inspect':
        result = inspect_x()
        return True, f"X state: mode={result['state'].get('mode')} drafts={len(result.get('recentDrafts') or [])} queue={len(result.get('recentQueue') or [])}"

    if component_id == 'telegram_sender' and action == 'test_lanes':
        lanes = load_telegram_lanes().get('lanes') or {}
        enabled = [name for name, cfg in lanes.items() if isinstance(cfg, dict) and cfg.get('enabled')]
        return True, f"Telegram lanes ready: {', '.join(enabled) if enabled else 'none'}"

    if component_id == 'telegram_sender' and action == 'run_social':
        return run_script('run_telegram_social_draft.sh')

    if component_id == 'performance_analyzer' and action == 'run_outputs':
        return run_script('run_performance_analyzer.sh')

    if component_id == 'operator_dashboard':
        if action == 'start' and comp.start_script:
            return run_script(comp.start_script)
        if action == 'stop' and runtime.get(component_id, {}).get('pid_file'):
            return stop_pid(str(runtime[component_id]['pid_file']))
        return True, 'Operator dashboard is this page'

    if component_id == 'stream_dashboard':
        if action == 'start' and comp.start_script:
            return run_script(comp.start_script)
        if action == 'stop' and runtime.get(component_id, {}).get('pid_file'):
            return stop_pid(str(runtime[component_id]['pid_file']))
        return True, 'Open http://127.0.0.1:8501'

    if action == 'start' and comp.start_script:
        return run_script(comp.start_script)
    if action == 'stop' and runtime.get(component_id, {}).get('pid_file'):
        return stop_pid(str(runtime[component_id]['pid_file']))
    if action == 'inspect':
        return open_path(comp.inspect_target or comp.log_path or root)

    return False, f'{component_id} action {action} not wired yet'
