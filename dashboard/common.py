from __future__ import annotations

from datetime import datetime, timezone

from nicegui import ui


def fmt_ts(value: str | None) -> str:
    if not value:
        return '–'
    return value.replace('T', ' ').replace('+00:00', ' UTC')


def fmt_num(value, digits: int = 2) -> str:
    try:
        return f'{float(value):,.{digits}f}'
    except Exception:
        return '–'


def status_class(level: str) -> str:
    return {
        'healthy': 'status-healthy',
        'warning': 'status-warning',
        'danger': 'status-danger',
        'info': 'status-info',
        'locked': 'status-muted',
        'pending': 'status-warning',
        'ready later': 'status-info',
    }.get(level, 'status-info')


def stale_state_label(seconds: float | None, warn_at: int) -> tuple[str, str]:
    if seconds is None:
        return 'unknown', 'status-warning'
    if seconds > warn_at:
        return f'stale • {int(seconds)}s', 'status-warning'
    return f'fresh • {int(seconds)}s', 'status-healthy'


def panel(title: str, subtitle: str | None = None, extra_classes: str = ''):
    card = ui.card().classes(f'glass-panel w-full h-full {extra_classes}'.strip())
    with card:
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-0'):
                ui.label(title).classes('panel-title')
                if subtitle:
                    ui.label(subtitle).classes('panel-subtitle')
    return card


def telemetry_row(left: str, right: str, right_class: str = '') -> None:
    with ui.row().classes('w-full justify-between items-center telemetry-row'):
        ui.label(left).classes('telemetry-key')
        ui.label(right).classes(f'telemetry-value {right_class}'.strip())


def pill(text: str, level: str = 'info') -> None:
    ui.label(text).classes(f'status-pill {status_class(level)}')


def compute_ages(market_state: dict, ws_state: dict) -> tuple[float | None, float | None]:
    now = datetime.now(timezone.utc)
    scanner_age = None
    ws_age = None
    try:
        scanner_dt = market_state.get('computed_at')
        if scanner_dt:
            scanner_age = now.timestamp() - datetime.fromisoformat(scanner_dt.replace('Z', '+00:00')).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        scanner_age = None
    try:
        ws_dt = ws_state.get('last_message_at')
        if ws_dt:
            ws_age = now.timestamp() - datetime.fromisoformat(ws_dt.replace('Z', '+00:00')).timestamp()
    except Exception:
        ws_age = None
    return scanner_age, ws_age
