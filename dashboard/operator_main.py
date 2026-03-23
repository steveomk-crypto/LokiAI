from __future__ import annotations

import os

from nicegui import ui

from .common import compute_ages, fmt_num, fmt_ts, panel, pill, stale_state_label, status_class, telemetry_row
from .data import compute_dashboard_state
from .theme import apply_theme


@ui.refreshable
def operator_view():
    state = compute_dashboard_state()
    market_state = state['market_state']
    ws_state = state['ws_state']
    live_movers = state['live_movers']
    top_opps = market_state.get('top_opportunities', [])
    metrics = market_state.get('metrics', {})

    scanner_age, ws_age = compute_ages(market_state, ws_state)
    scanner_text, scanner_class = stale_state_label(scanner_age, 3600)
    ws_text, ws_class = stale_state_label(ws_age, 300)
    alert_count = len(state['status_flags'])

    with ui.column().classes('w-full gap-4'):
        with ui.card().classes('top-bar w-full'):
            with ui.row().classes('w-full justify-between items-center'):
                with ui.column().classes('gap-0'):
                    ui.label('LokiAI Operator Console').classes('hero-title')
                    ui.label('Scanner + Coinbase live ingest command surface').classes('hero-subtitle')
                with ui.row().classes('gap-3 items-center wrap'):
                    pill('MODE • REBUILD / PAPER ONLY', 'info')
                    pill(f'SCANNER • {scanner_text.upper()}', 'warning' if 'stale' in scanner_text else 'healthy')
                    pill(f"WEBSOCKET • {'ONLINE' if ws_state.get('connected') else 'OFFLINE'}", 'healthy' if ws_state.get('connected') else 'danger')
                    pill(f'ALERTS • {alert_count}', 'warning' if alert_count else 'healthy')

        with ui.grid(columns=3).classes('w-full gap-4'):
            with panel('System Health', 'Immediate machine state'):
                telemetry_row('Scanner last run', fmt_ts(market_state.get('computed_at')), scanner_class)
                telemetry_row('Scanner freshness', scanner_text, scanner_class)
                telemetry_row('Signals this run', str(metrics.get('total_signals', 0)))
                telemetry_row('Websocket', 'online' if ws_state.get('connected') else 'offline', 'status-healthy' if ws_state.get('connected') else 'status-danger')
                telemetry_row('Last websocket message', fmt_ts(ws_state.get('last_message_at')), ws_class)
                telemetry_row('Tracked Coinbase products', str(ws_state.get('tracked_products', 0)))
                telemetry_row('Reconnect count', str(ws_state.get('reconnect_count', 0)))

            with panel('Market State Summary', 'Latest scanner snapshot'):
                telemetry_row('Avg top score', fmt_num(metrics.get('avg_top_score'), 4))
                telemetry_row('High-quality signals', str(metrics.get('high_quality_signals', 0)))
                telemetry_row('Breadth positive', fmt_num(metrics.get('breadth_positive'), 2))
                telemetry_row('Top opportunities loaded', str(len(top_opps)))
                telemetry_row('Mode', market_state.get('mode', '–'))

            with panel('Alerts / Warnings', 'Operational exceptions'):
                if not state['status_flags']:
                    ui.label('No active warnings').classes('status-healthy font-semibold')
                for flag in state['status_flags']:
                    level_class = 'status-danger' if flag['level'] == 'danger' else 'status-warning'
                    ui.label(f"• {flag['message']}").classes(f'text-sm telemetry-row {level_class}')

            with panel('Top Scanner Opportunities', 'Primary ranked output', 'anchor-panel'):
                if not top_opps:
                    ui.label('No opportunities yet').classes('text-gray-400')
                for opp in top_opps[:6]:
                    with ui.row().classes('w-full justify-between items-center signal-row'):
                        with ui.column().classes('gap-0'):
                            ui.label(opp.get('token', '?')).classes('signal-symbol')
                            ui.label(f"trend • {opp.get('trend', '–')}").classes('signal-meta')
                        with ui.column().classes('items-end gap-0'):
                            ui.label(f"{fmt_num(opp.get('momentum'), 1)}%").classes('signal-momentum')
                            ui.label(f"p{opp.get('persistence', 0)} • score {fmt_num(opp.get('score'), 3)}").classes('signal-meta')

            with panel('Persistence / Repeat Names', 'What is surviving multiple scans'):
                if not state['persistence_summary']:
                    ui.label('Need more scanner history').classes('text-gray-400')
                for item in state['persistence_summary'][:8]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        ui.label(item['token']).classes('font-semibold')
                        ui.label(f"r{item['repeat_count']} • {fmt_num(item['latest_score'], 3)} • {item['latest_trend']}").classes('telemetry-value')

            with panel('Scanner Run History', 'Cadence and quality'):
                if not state['scanner_history']:
                    ui.label('No run history yet').classes('text-gray-400')
                for row in state['scanner_history'][-8:]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        ui.label(row['timestamp'][-8:] if row['timestamp'] else '–').classes('telemetry-key')
                        ui.label(f"sig {row['signal_count']} • HQ {row['high_quality_count']} • {fmt_num(row['top_score'], 3)}").classes('telemetry-value')

            with panel('Coinbase Live Movers', 'Short-horizon live pulse'):
                if not live_movers:
                    ui.label('Waiting for live ticker population').classes('text-gray-400')
                for mover in live_movers[:8]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        with ui.column().classes('gap-0'):
                            ui.label(mover['product_id']).classes('font-semibold')
                            ui.label(f"px {fmt_num(mover.get('price'), 4)}").classes('signal-meta')
                        with ui.column().classes('items-end gap-0'):
                            drift = float(mover.get('drift_300s') or 0.0)
                            drift_cls = 'status-healthy' if drift > 0 else 'status-warning' if drift < 0 else 'telemetry-value'
                            ui.label(f"{fmt_num(drift, 3)}%").classes(f'font-semibold {drift_cls}')
                            ui.label(f"fresh {fmt_num(mover.get('freshness_seconds'), 1)}s").classes('signal-meta')

            with panel('Coinbase Universe Health', 'Tracked live universe status'):
                health = state['universe_health']
                telemetry_row('Tracked products', str(health['tracked_products']))
                telemetry_row('Active products', str(health['active_products']))
                telemetry_row('Stale products', str(health['stale_products']), 'status-warning' if health['stale_products'] else 'status-healthy')
                telemetry_row('Reconnect count', str(health['reconnect_count']))
                ui.separator().classes('my-2 opacity-20')
                for row in health['freshest_symbols']:
                    telemetry_row(row['product_id'], f"{fmt_num(row.get('freshness_seconds'), 1)}s")

            with panel('Websocket Activity History', 'Recent Coinbase snapshots'):
                if not state['ws_snapshots']:
                    ui.label('No websocket snapshots yet').classes('text-gray-400')
                for snap in state['ws_snapshots'][-6:]:
                    with ui.row().classes('w-full justify-between items-center telemetry-row'):
                        ui.label(snap.get('timestamp', '–')[-8:]).classes('telemetry-key')
                        ui.label(f"msgs {snap.get('messages_received', 0)} • tracked {snap.get('tracked_products', 0)}").classes('telemetry-value')

            with panel('Command / Controls Bay', 'Placeholder control surface'):
                with ui.grid(columns=2).classes('w-full gap-2'):
                    for item in state['controls_placeholder']:
                        level = item['state'] if item['state'] in {'locked', 'pending', 'ready later'} else 'locked'
                        ui.button(f"{item['label']} • {item['state']}").props('outline color=secondary').classes(f'w-full control-button {status_class(level)}')


@ui.page('/')
def index():
    with ui.column().classes('w-full min-h-screen dashboard-shell p-6 gap-4'):
        operator_view()
    ui.timer(30, operator_view.refresh)


def run():
    apply_theme()
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    port = int(os.getenv('DASHBOARD_PORT', '8500'))
    ui.run(title='LokiAI Operator Console', reload=False, host=host, port=port)


if __name__ == '__main__':
    run()
