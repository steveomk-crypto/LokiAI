from __future__ import annotations

from datetime import datetime, timezone
import os
import signal
import subprocess
from pathlib import Path

from nicegui import ui

from .actions import perform_component_action
from .data import compute_dashboard_state, read_runtime_controls, _safe_iso_to_dt
from .runtime_registry import components_by_category


def _fmt_ts(value: str | None) -> str:
    if not value:
        return '–'
    return value.replace('T', ' ').replace('+00:00', ' UTC')


def _fmt_num(value, digits: int = 2) -> str:
    try:
        return f'{float(value):,.{digits}f}'
    except Exception:
        return '–'


def _status_class(level: str) -> str:
    return {
        'healthy': 'status-healthy',
        'warning': 'status-warning',
        'danger': 'status-danger',
        'info': 'status-info',
        'locked': 'status-muted',
        'pending': 'status-warning',
        'ready later': 'status-info',
    }.get(level, 'status-info')


def _stale_state_label(seconds: float | None, warn_at: int) -> tuple[str, str]:
    if seconds is None:
        return 'unknown', 'status-warning'
    if seconds > warn_at:
        return f'stale • {int(seconds)}s', 'status-warning'
    return f'fresh • {int(seconds)}s', 'status-healthy'


def _panel(title: str, subtitle: str | None = None, extra_classes: str = ''):
    card = ui.card().classes(f'glass-panel w-full h-full {extra_classes}'.strip())
    with card:
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-0'):
                ui.label(title).classes('panel-title')
                if subtitle:
                    ui.label(subtitle).classes('panel-subtitle')
    return card


def _telemetry_row(left: str, right: str, right_class: str = '') -> None:
    with ui.row().classes('w-full justify-between items-center telemetry-row'):
        ui.label(left).classes('telemetry-key')
        ui.label(right).classes(f'telemetry-value {right_class}'.strip())


def _pill(text: str, level: str = 'info') -> None:
    ui.label(text).classes(f'status-pill {_status_class(level)}')


LAST_ACTION_RESULT = {'message': 'No recent actions'}
COMPONENT_ACTION_RESULTS: dict[str, str] = {}


def _format_meta_time(value: str | None) -> str:
    dt = _safe_iso_to_dt(value)
    if not dt:
        return '–'
    return dt.astimezone().strftime('%H:%M:%S')


def _control_action(group: str, action: str) -> None:
    ok, msg = perform_component_action(group, action)
    result_text = f'{group} {action}: {msg}'
    LAST_ACTION_RESULT['message'] = result_text
    COMPONENT_ACTION_RESULTS[group] = result_text
    ui.notify(msg, type='positive' if ok else 'negative')
    operator_view.refresh()


@ui.refreshable
def operator_view():
    state = compute_dashboard_state()
    market_state = state['market_state']
    ws_state = state['ws_state']
    live_movers = state['live_movers']
    top_opps = market_state.get('top_opportunities', [])
    metrics = market_state.get('metrics', {})
    loop_info = state.get('main_loop_status', {})

    scanner_dt = market_state.get('computed_at')
    ws_dt = ws_state.get('last_message_at')
    now = datetime.now(timezone.utc)
    scanner_age = None
    ws_age = None
    try:
        if scanner_dt:
            parsed = datetime.fromisoformat(scanner_dt.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                from zoneinfo import ZoneInfo
                parsed = parsed.replace(tzinfo=ZoneInfo('America/Los_Angeles'))
            scanner_age = now.timestamp() - parsed.astimezone(timezone.utc).timestamp()
    except Exception:
        scanner_age = None
    try:
        if ws_dt:
            ws_age = now.timestamp() - datetime.fromisoformat(ws_dt.replace('Z', '+00:00')).timestamp()
    except Exception:
        ws_age = None

    scanner_text, scanner_class = _stale_state_label(scanner_age, 3600)
    ws_text, ws_class = _stale_state_label(ws_age, 300)
    alert_count = len(state['status_flags'])
    runtime = read_runtime_controls()

    with ui.column().classes('w-full gap-4'):
        with ui.card().classes('top-bar w-full'):
            with ui.row().classes('w-full justify-between items-center'):
                with ui.column().classes('gap-0'):
                    ui.label('LokiAI Operator Console').classes('hero-title')
                    ui.label('Scanner + Coinbase live ingest command surface').classes('hero-subtitle')
                with ui.row().classes('gap-3 items-center wrap'):
                    _pill('MODE • REBUILD / PAPER ONLY', 'info')
                    _pill(f"CORE • {'ON' if runtime['main_loop']['running'] else 'OFF'} / 30S", 'healthy' if runtime['main_loop']['running'] else 'warning')
                    _pill(f"SCANNER • {scanner_text.upper()}", 'warning' if 'stale' in scanner_text else 'healthy')
                    loop_recent = bool(loop_info.get('last_cycle_started_at'))
                    loop_mode = 'RUNNING' if runtime['main_loop']['running'] else 'ACTIVE' if loop_recent else 'IDLE'
                    loop_mode_level = 'healthy' if loop_mode in {'RUNNING', 'ACTIVE'} else 'warning'
                    _pill(f"MAIN LOOP • {loop_mode}", loop_mode_level)
                    _pill(f"OUTPUTS • {'ON' if runtime.get('output_cycle', {}).get('running') else 'OFF'} / 5M", 'healthy' if runtime.get('output_cycle', {}).get('running') else 'warning')
                    _pill(f"TG SUMMARY • {'ON' if runtime.get('telegram_summary_cycle', {}).get('running') else 'OFF'} / 15M", 'healthy' if runtime.get('telegram_summary_cycle', {}).get('running') else 'warning')
                    _pill(f'WEBSOCKET • {"ONLINE" if ws_state.get("connected") else "OFFLINE"}', 'healthy' if ws_state.get('connected') else 'danger')
                    _pill(f'ALERTS • {alert_count}', 'warning' if alert_count else 'healthy')

        with ui.grid(columns=3).classes('w-full gap-4'):
            with _panel('Live Machine State', 'What matters right now'):
                _telemetry_row('Automation', 'running' if runtime['main_loop']['running'] else 'stopped', 'status-healthy' if runtime['main_loop']['running'] else 'status-danger')
                _telemetry_row('Scanner freshness', scanner_text, scanner_class)
                _telemetry_row('Websocket', 'online' if ws_state.get('connected') else 'offline', 'status-healthy' if ws_state.get('connected') else 'status-danger')
                _telemetry_row('Last cycle start', loop_info.get('last_cycle_started_at') or '–', 'status-healthy' if loop_info.get('last_cycle_started_at') else 'status-warning')
                _telemetry_row('Last cycle end', loop_info.get('last_cycle_completed_at') or '–', 'status-healthy' if loop_info.get('last_cycle_completed_at') else 'status-warning')
                _telemetry_row('Scanner run', loop_info.get('task_completed_at', {}).get('market_scanner') or '–')
                _telemetry_row('Trader run', loop_info.get('task_completed_at', {}).get('paper_trader') or '–')
                _telemetry_row('Manager run', loop_info.get('task_completed_at', {}).get('position_manager') or '–')
                _telemetry_row('Open V2 slots', str(len(state.get('open_positions_v2', []))), 'status-warning' if len(state.get('open_positions_v2', [])) else 'status-healthy')
                _telemetry_row('Signals in snapshot', str(metrics.get('total_signals', 0)), 'status-warning' if int(metrics.get('total_signals', 0) or 0) == 0 else 'status-healthy')

            with _panel('Market Summary', 'Latest scanner snapshot in one read'):
                _telemetry_row('High-quality signals', str(metrics.get('high_quality_signals', 0)))
                _telemetry_row('Avg top score', _fmt_num(metrics.get('avg_top_score'), 4))
                _telemetry_row('Breadth positive', _fmt_num(metrics.get('breadth_positive'), 2))
                _telemetry_row('Top opportunities', str(len(top_opps)))
                _telemetry_row('Mode', market_state.get('mode', '–'))

            with _panel('Action Feed', 'Latest operator and system results'):
                ui.label(LAST_ACTION_RESULT['message']).classes('telemetry-value font-semibold')
                ui.separator().classes('my-2 opacity-20')
                if not state['status_flags'] and not loop_info.get('last_error'):
                    ui.label('No active warnings').classes('status-healthy font-semibold')
                for flag in state['status_flags'][:4]:
                    level_class = 'status-danger' if flag['level'] == 'danger' else 'status-warning'
                    ui.label(f"• {flag['message']}").classes(f'text-sm telemetry-row {level_class}')
                if loop_info.get('last_error'):
                    ui.label(f"• Loop error: {loop_info.get('last_error')}").classes('text-sm telemetry-row status-warning')

            with _panel('Top Scanner Opportunities', 'Primary ranked output', 'anchor-panel'):
                if not top_opps:
                    ui.label('No opportunities yet').classes('text-gray-400')
                for opp in top_opps[:6]:
                    with ui.row().classes('w-full justify-between items-center signal-row'):
                        with ui.column().classes('gap-0'):
                            ui.label(opp.get('token', '?')).classes('signal-symbol')
                            ui.label(f"trend • {opp.get('trend', '–')}").classes('signal-meta')
                        with ui.column().classes('items-end gap-0'):
                            ui.label(f"{_fmt_num(opp.get('momentum'), 1)}%").classes('signal-momentum')
                            ui.label(f"p{opp.get('persistence', 0)} • score {_fmt_num(opp.get('score'), 3)}").classes('signal-meta')

            with _panel('Persistence / Repeat Names', 'What is surviving multiple scans'):
                if not state['persistence_summary']:
                    ui.label('Need more scanner history').classes('text-gray-400')
                for item in state['persistence_summary'][:8]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        ui.label(item['token']).classes('font-semibold')
                        ui.label(f"r{item['repeat_count']} • {_fmt_num(item['latest_score'], 3)} • {item['latest_trend']}").classes('telemetry-value')

            with _panel('This Cycle', 'What changed most recently'):
                latest_history = state['scanner_history'][-1] if state['scanner_history'] else None
                if not latest_history:
                    ui.label('No cycle history yet').classes('text-gray-400')
                else:
                    _telemetry_row('Signals', str(latest_history.get('signal_count', 0)))
                    _telemetry_row('High quality', str(latest_history.get('high_quality_count', 0)))
                    _telemetry_row('Top score', _fmt_num(latest_history.get('top_score'), 3))
                    _telemetry_row('Cycle stamp', latest_history.get('timestamp', '–')[-8:])

            with _panel('Coinbase Live Movers', 'Short-horizon live pulse'):
                if not live_movers:
                    ui.label('Waiting for live ticker population').classes('text-gray-400')
                for mover in live_movers[:8]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        with ui.column().classes('gap-0'):
                            ui.label(mover['product_id']).classes('font-semibold')
                            ui.label(f"px {_fmt_num(mover.get('price'), 4)}").classes('signal-meta')
                        with ui.column().classes('items-end gap-0'):
                            drift = float(mover.get('drift_300s') or 0.0)
                            drift_cls = 'status-healthy' if drift > 0 else 'status-warning' if drift < 0 else 'telemetry-value'
                            ui.label(f"{_fmt_num(drift, 3)}%").classes(f'font-semibold {drift_cls}')
                            ui.label(f"fresh {_fmt_num(mover.get('freshness_seconds'), 1)}s").classes('signal-meta')

            with _panel('Outputs Snapshot', 'What the machine is saying externally'):
                telegram_state = runtime.get('telegram_sender', {})
                x_state = runtime.get('x_autoposter', {})
                _telemetry_row('Telegram', str(telegram_state.get('state') or '–').upper())
                _telemetry_row('Telegram result', str(telegram_state.get('last_result') or COMPONENT_ACTION_RESULTS.get('telegram_sender') or '–'))
                _telemetry_row('X mode', str(x_state.get('state') or 'draft_only').upper())
                _telemetry_row('X result', str(x_state.get('last_result') or COMPONENT_ACTION_RESULTS.get('x_autoposter') or '–'))

            with _panel('Websocket Activity History', 'Recent Coinbase snapshots'):
                if not state['ws_snapshots']:
                    ui.label('No websocket snapshots yet').classes('text-gray-400')
                for snap in state['ws_snapshots'][-6:]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        ui.label(snap.get('timestamp', '–')[-8:]).classes('telemetry-key')
                        ui.label(f"msgs {snap.get('messages_received', 0)} • tracked {snap.get('tracked_products', 0)}").classes('telemetry-value')

        with _panel('Operator Rail', 'Operate the system from a full-width control strip'):
            runtime_map = {item['group']: item for item in state['controls_placeholder']}

            def compact_row(component_id: str):
                    item = runtime_map.get(component_id)
                    if not item:
                        return
                    state_text = str(item.get('display_state') or item['state']).upper()
                    deps_text = 'Ready' if item.get('dependency_health') == 'clear' else 'Waiting on ' + ', '.join(item.get('dependency_blockers') or [])
                    last_success = _format_meta_time(item.get('last_success_at')) if item.get('last_success_at') else '–'
                    with ui.row().classes('w-full telemetry-row'):
                        ui.label(str(item['label'])).classes('font-semibold')
                        ui.label(str(item.get('owned_by') or 'manual').upper()).classes('signal-meta')
                        ui.label(state_text).classes(f'status-pill {_status_class("healthy" if state_text in {"RUNNING", "ACTIVE"} else "warning" if state_text in {"WAITING", "BLOCKED", "DEGRADED"} else "info")}')
                        ui.label(deps_text).classes('signal-meta')
                        ui.label(last_success).classes('signal-meta')
                        ui.label(str(item.get('last_result') or COMPONENT_ACTION_RESULTS.get(item['group']) or '–')).classes('signal-meta')
                        with ui.row().classes('operator-actions'):
                            if item.get('kind') == 'service':
                                if item['group'] != 'main_loop':
                                    start_btn = ui.button('Start').props('size=sm color=positive unelevated').classes('min-w-[78px]')
                                    if item.get('running'):
                                        start_btn.disable()
                                    start_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'start'))
                                stop_btn = ui.button('Stop').props('size=sm color=negative outline').classes('min-w-[78px]')
                                if not item.get('running'):
                                    stop_btn.disable()
                                stop_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'stop'))
                            elif item.get('kind') == 'job':
                                can_run_job = bool(item.get('start_script')) and (item.get('dependency_health') != 'blocked' or item['group'] in {'paper_trader_v2', 'position_manager', 'telegram_sender', 'x_autoposter', 'performance_analyzer'})
                                if can_run_job:
                                    run_btn = ui.button(item.get('start_label') or 'Run').props('size=sm color=positive unelevated').classes('min-w-[78px]')
                                    run_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'start'))
                                if item.get('pid_file'):
                                    stop_btn = ui.button('Stop').props('size=sm color=negative outline').classes('min-w-[78px]')
                                    if not item.get('running'):
                                        stop_btn.disable()
                                    stop_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'stop'))
                            inspect_btn = ui.button('Inspect').props('size=sm color=secondary outline').classes('min-w-[78px]')
                            inspect_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'inspect'))

            with ui.column().classes('w-full gap-3'):
                ui.label('System Controls').classes('panel-title')
                with ui.card().classes('glass-panel w-full p-3'):
                    with ui.row().classes('w-full items-center justify-between gap-2 wrap'):
                        start_auto = ui.button('Start Automation').props('color=positive unelevated').classes('min-w-[150px]')
                        if runtime_map.get('main_loop', {}).get('running'):
                            start_auto.disable()
                        start_auto.on('click', lambda: _control_action('main_loop', 'start'))
                        ui.button('Run Cycle').props('color=positive outline').classes('min-w-[130px]').on('click', lambda: _control_action('main_loop', 'run_cycle'))
                        stop_auto = ui.button('Stop Automation').props('color=negative outline').classes('min-w-[150px]')
                        if not runtime_map.get('main_loop', {}).get('running'):
                            stop_auto.disable()
                        stop_auto.on('click', lambda: _control_action('main_loop', 'stop'))
                        ui.button('Flatten V2').props('color=warning unelevated').classes('min-w-[130px]').on('click', lambda: _control_action('paper_trader_v2', 'flatten'))
                        ui.button('Run Reports').props('color=secondary outline').classes('min-w-[130px]').on('click', lambda: _control_action('performance_analyzer', 'run_outputs'))
                        ui.button('Loop Log').props('color=secondary outline').classes('min-w-[110px]').on('click', lambda: _control_action('main_loop', 'inspect'))

                with ui.column().classes('w-full gap-4'):
                    with ui.column().classes('w-full gap-2 operator-table'):
                        ui.label('Core Systems').classes('panel-title')
                        ui.label('Status + manual overrides. Use the top action bar for normal machine operation.').classes('panel-subtitle')
                        with ui.card().classes('glass-panel w-full p-3'):
                            with ui.row().classes('w-full operator-header-row'):
                                ui.label('Name')
                                ui.label('Owner')
                                ui.label('Status')
                                ui.label('Reason')
                                ui.label('Last')
                                ui.label('Result')
                                ui.label('Actions')
                            for component_id in ['coinbase_feed', 'market_scanner', 'paper_trader_v2', 'position_manager', 'main_loop']:
                                compact_row(component_id)

                    with ui.column().classes('w-full gap-2 operator-table'):
                        ui.label('Outputs & Automation').classes('panel-title')
                        with ui.card().classes('glass-panel w-full p-3'):
                            with ui.row().classes('w-full operator-header-row'):
                                ui.label('Name')
                                ui.label('Mode')
                                ui.label('State')
                                ui.label('Last')
                                ui.label('Result')
                                ui.label('Actions')
                            for component_id in ['market_broadcaster', 'telegram_sender', 'x_autoposter', 'performance_analyzer']:
                                item = runtime_map.get(component_id)
                                if not item:
                                    continue
                                with ui.row().classes('w-full telemetry-row'):
                                    ui.label(str(item['label'])).classes('font-semibold')
                                    ui.label(str(item.get('desired_state') or 'unknown').upper()).classes('status-pill status-info')
                                    state_value = str(item.get('display_state') or item.get('state') or 'IDLE').upper()
                                    if item['group'] == 'x_autoposter':
                                        state_value = f"{state_value} / {str(item.get('state') or 'draft_only').upper()}"
                                    ui.label(state_value).classes('signal-meta')
                                    ui.label(_format_meta_time(item.get('last_success_at')) if item.get('last_success_at') else '–').classes('signal-meta')
                                    last_result = str(item.get('last_result') or COMPONENT_ACTION_RESULTS.get(item['group']) or '–')
                                    ui.label(last_result).classes('signal-meta')
                                    with ui.row().classes('operator-actions'):
                                        enable_btn = ui.button('On').props('size=sm color=positive outline').classes('min-w-[62px]')
                                        if str(item.get('desired_state')) == 'enabled':
                                            enable_btn.disable()
                                        enable_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'enable'))
                                        disable_btn = ui.button('Off').props('size=sm color=negative outline').classes('min-w-[62px]')
                                        if str(item.get('desired_state')) == 'disabled':
                                            disable_btn.disable()
                                        disable_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'disable'))
                                        if item['group'] == 'x_autoposter':
                                            ui.button('Draft').props('size=sm color=positive outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'draft'))
                                            ui.button('Queue').props('size=sm color=secondary outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'queue'))
                                            ui.button('Post').props('size=sm color=warning outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'post_now'))
                                        elif item['group'] == 'telegram_sender':
                                            ui.button('Test').props('size=sm color=positive outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'test_lanes'))
                                            ui.button('Social').props('size=sm color=secondary outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'run_social'))
                                            ui.button('Run').props('size=sm color=warning outline').classes('min-w-[66px]').on('click', lambda e=None, group=item['group']: _control_action(group, 'start'))
                                        else:
                                            run_btn = ui.button('Run').props('size=sm color=positive outline').classes('min-w-[66px]')
                                            run_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'start'))
                                        inspect_btn = ui.button('Inspect').props('size=sm color=secondary outline').classes('min-w-[66px]')
                                        inspect_btn.on('click', lambda e=None, group=item['group']: _control_action(group, 'inspect'))

                with ui.expansion('Advanced Components').classes('w-full'):
                    with ui.column().classes('w-full gap-2 mt-2'):
                        compact_row('stream_dashboard')
                        compact_row('sol_shadow_logger')


@ui.refreshable
def stream_view():
    state = compute_dashboard_state()
    market_state = state['market_state']
    ws_state = state['ws_state']
    metrics = market_state.get('metrics', {})
    top_opps = market_state.get('top_opportunities', [])
    live_movers = state['live_movers']

    with ui.column().classes('w-full gap-4'):
        with ui.card().classes('top-bar w-full stream-hero'):
            with ui.row().classes('w-full justify-between items-center'):
                with ui.column().classes('gap-0'):
                    ui.label('LokiAI Market Engine').classes('hero-title')
                    ui.label('Live scanner + Coinbase pulse • paper-only rebuild phase').classes('hero-subtitle')
                with ui.row().classes('gap-3 items-center wrap'):
                    _pill('STREAM • LIVE', 'healthy')
                    _pill(f"SCANNER • {market_state.get('metrics', {}).get('total_signals', 0)} signals", 'info')
                    _pill(f"WEBSOCKET • {'ONLINE' if ws_state.get('connected') else 'OFFLINE'}", 'healthy' if ws_state.get('connected') else 'danger')

        with ui.row().classes('w-full gap-4 no-wrap stream-main'):
            with ui.column().classes('w-2/3 gap-4'):
                with _panel('Live Coinbase Pulse', 'Short-horizon movers from tracked universe', 'anchor-panel'):
                    if not live_movers:
                        ui.label('Waiting for live ticker population').classes('text-gray-400')
                    for mover in live_movers[:10]:
                        with ui.row().classes('w-full justify-between items-center signal-row'):
                            with ui.column().classes('gap-0'):
                                ui.label(mover['product_id']).classes('signal-symbol')
                                ui.label(f"fresh { _fmt_num(mover.get('freshness_seconds'), 1) }s").classes('signal-meta')
                            with ui.column().classes('items-end gap-0'):
                                drift = float(mover.get('drift_300s') or 0.0)
                                drift_cls = 'status-healthy' if drift > 0 else 'status-warning' if drift < 0 else 'telemetry-value'
                                ui.label(f"{_fmt_num(drift, 3)}%").classes(f'font-semibold {drift_cls}')
                                ui.label(f"px {_fmt_num(mover.get('price'), 4)}").classes('signal-meta')

                with _panel('Scanner Highlights', 'Top ranked opportunities from the latest scan'):
                    if not top_opps:
                        ui.label('No scanner highlights yet').classes('text-gray-400')
                    for opp in top_opps[:6]:
                        with ui.row().classes('w-full justify-between items-center signal-row'):
                            with ui.column().classes('gap-0'):
                                ui.label(opp.get('token', '?')).classes('signal-symbol')
                                ui.label(f"trend • {opp.get('trend', '–')}").classes('signal-meta')
                            with ui.column().classes('items-end gap-0'):
                                ui.label(f"{_fmt_num(opp.get('momentum'), 1)}%").classes('signal-momentum')
                                ui.label(f"p{opp.get('persistence', 0)} • score {_fmt_num(opp.get('score'), 3)}").classes('signal-meta')

                with _panel('System Progress', 'What the machine has done today'):
                    _telemetry_row('Signals logged', str(metrics.get('total_signals', 0)))
                    _telemetry_row('High-quality signals', str(metrics.get('high_quality_signals', 0)))
                    _telemetry_row('Tracked Coinbase products', str(ws_state.get('tracked_products', 0)))
                    _telemetry_row('Current mode', 'rebuild / paper only')

            with ui.column().classes('w-1/3 gap-4'):
                with _panel('Operating Status', 'Transparency over hype'):
                    ui.label('Paper-only mode.').classes('text-sm font-semibold status-info')
                    ui.label('Live funds are staged but inactive until system stability is proven.').classes('text-sm panel-row')
                    ui.label('No real-money execution is active.').classes('text-sm panel-row')

                with _panel('Distribution Surface', 'Current outbound surfaces'):
                    ui.label('Substack: lokiai.substack.com').classes('text-sm panel-row')
                    ui.label('Gumroad: lokiclips.gumroad.com').classes('text-sm panel-row')
                    ui.label('X posting: optional / controlled').classes('text-sm panel-row')

        with ui.card().classes('glass-panel w-full footer-ticker'):
            ui.label('SCANNER LIVE • PAPER ONLY • QUALITY GATE ACTIVE • SUBSTACK + GUMROAD REBUILD IN PROGRESS').classes('ticker-text')


def render_operator_page():
    with ui.column().classes('w-full min-h-screen dashboard-shell p-6 gap-4'):
        operator_view()
    ui.timer(30, operator_view.refresh)


def render_stream_page():
    with ui.column().classes('w-full min-h-screen dashboard-shell p-6 gap-4'):
        stream_view()
    ui.timer(30, stream_view.refresh)


def apply_theme() -> None:
    ui.add_head_html(
        '''
        <style>
            body {
                background: radial-gradient(circle at top, rgba(78, 0, 146, 0.35), transparent 35%),
                            radial-gradient(circle at 20% 20%, rgba(0, 200, 255, 0.18), transparent 25%),
                            linear-gradient(180deg, #050816 0%, #090b1f 45%, #02040d 100%);
                color: #eef6ff;
                font-family: Inter, system-ui, sans-serif;
            }
            .dashboard-shell {
                background-image:
                    radial-gradient(circle at 50% -20%, rgba(0,255,255,0.08), transparent 40%),
                    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
                background-size: auto, 24px 24px, 24px 24px;
            }
            .top-bar, .glass-panel {
                background: rgba(7, 14, 32, 0.68);
                border: 1px solid rgba(0, 255, 255, 0.16);
                box-shadow: 0 0 18px rgba(0, 220, 255, 0.08), inset 0 0 28px rgba(180, 0, 255, 0.04);
                backdrop-filter: blur(14px);
                border-radius: 18px;
            }
            .anchor-panel {
                border-color: rgba(115, 245, 255, 0.35);
                box-shadow: 0 0 24px rgba(0, 220, 255, 0.12), inset 0 0 36px rgba(180, 0, 255, 0.06);
            }
            .hero-title {
                font-size: 1.6rem;
                font-weight: 700;
                color: #f3fbff;
                letter-spacing: 0.03em;
            }
            .hero-subtitle, .panel-subtitle, .signal-meta {
                color: rgba(210, 225, 255, 0.72);
                font-size: 0.78rem;
            }
            .panel-title {
                color: #73f5ff;
                font-size: 0.95rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.2rem;
            }
            .status-pill {
                border: 1px solid rgba(255,255,255,0.1);
                padding: 0.45rem 0.7rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 600;
                letter-spacing: 0.04em;
            }
            .status-healthy { color: #7bf7c6 !important; }
            .status-warning { color: #ffd36b !important; }
            .status-danger { color: #ff8d9b !important; }
            .status-info { color: #8dd8ff !important; }
            .status-muted { color: #b9c6e8 !important; opacity: 0.7; }
            .telemetry-row {
                padding: 0.24rem 0;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }
            .operator-table {
                width: 100%;
            }
            .operator-table .telemetry-row {
                display: grid;
                grid-template-columns: minmax(120px, 1.05fr) minmax(84px, 0.6fr) minmax(84px, 0.6fr) minmax(120px, 0.95fr) minmax(72px, 0.55fr) minmax(180px, 1.25fr) auto;
                align-items: center;
                column-gap: 0.5rem;
            }
            .operator-header-row {
                display: grid;
                grid-template-columns: minmax(120px, 1.05fr) minmax(84px, 0.6fr) minmax(84px, 0.6fr) minmax(120px, 0.95fr) minmax(72px, 0.55fr) minmax(180px, 1.25fr) auto;
                column-gap: 0.55rem;
                opacity: 0.72;
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                padding-bottom: 0.35rem;
                border-bottom: 1px solid rgba(255,255,255,0.06);
                margin-bottom: 0.25rem;
            }
            .operator-actions {
                display: flex;
                gap: 0.28rem;
                justify-content: flex-end;
                align-items: center;
                flex-wrap: wrap;
            }
            .telemetry-key {
                color: rgba(220, 232, 255, 0.7);
                font-size: 0.8rem;
            }
            .telemetry-value {
                color: #eef6ff;
                font-size: 0.82rem;
                font-weight: 600;
                text-align: right;
            }
            .signal-row {
                padding: 0.35rem 0;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            .signal-symbol {
                font-size: 1rem;
                font-weight: 700;
                color: #f4fbff;
            }
            .signal-momentum {
                font-size: 1rem;
                font-weight: 700;
                color: #73f5ff;
                text-align: right;
            }
            .control-button {
                border-color: rgba(255,255,255,0.12) !important;
                background: rgba(255,255,255,0.02) !important;
            }
            .stream-hero {
                border-color: rgba(255, 0, 220, 0.18);
                box-shadow: 0 0 26px rgba(0, 220, 255, 0.12), inset 0 0 40px rgba(255, 0, 220, 0.05);
            }
            .footer-ticker {
                overflow: hidden;
                border-color: rgba(255,255,255,0.12);
            }
            .ticker-text {
                color: #dff7ff;
                letter-spacing: 0.08em;
                font-size: 0.78rem;
                text-transform: uppercase;
            }
        </style>
        ''', shared=True
    )


def run():
    apply_theme()
    ui.page('/')(render_operator_page)
    import dashboard.stream  # noqa: F401
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    port = int(os.getenv('DASHBOARD_PORT', '8500'))
    ui.run(title='LokiAI Operator Console', reload=False, host=host, port=port)


if __name__ == '__main__':
    run()
