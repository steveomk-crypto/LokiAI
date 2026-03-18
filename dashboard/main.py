from datetime import datetime, timezone
from typing import Dict, List

import os

from nicegui import ui

from .data import (
    load_entry_events,
    load_latest_packet,
    load_loop_status,
    load_open_positions,
    load_run_baseline,
    load_trades,
)

DASHBOARD_FILTERS = {
    'tier': 'All tiers',
    'exit_reason': 'All exits',
}


HEADER_REGIME_LABEL = None
DATA_SOURCE_LABEL = None


def compute_metrics() -> Dict:
    packet = load_latest_packet()
    baseline_str, baseline_dt = load_run_baseline()
    positions, positions_path, positions_updated = load_open_positions()
    trades_all, trades_path, trades_updated = load_trades()
    entry_events_all, entry_events_path, entry_events_updated = load_entry_events()

    def _parse_iso(value: str):
        if not value:
            return None
        formatted = value[:-1] + '+00:00' if value.endswith('Z') else value
        try:
            return datetime.fromisoformat(formatted)
        except ValueError:
            return None

    def _is_in_run(dt_obj):
        if not baseline_dt or not dt_obj:
            return True
        return dt_obj >= baseline_dt

    run_positions: List[Dict] = []
    carryover_positions: List[Dict] = []
    for pos in positions:
        entry_dt = _parse_iso(pos.get('entry_time') or pos.get('last_update'))
        (run_positions if _is_in_run(entry_dt) else carryover_positions).append(pos)

    run_trades: List[Dict] = []
    for trade in trades_all:
        exit_dt = _parse_iso(trade.get('exit_time') or trade.get('last_update'))
        if _is_in_run(exit_dt):
            run_trades.append(trade)

    run_entry_events: List[Dict] = []
    for event in entry_events_all:
        event_dt = _parse_iso(event.get('timestamp'))
        if _is_in_run(event_dt):
            run_entry_events.append(event)

    def _open_pnl(bucket: List[Dict]):
        return sum((float(pos.get('pnl_percent') or 0.0) / 100.0) * float(pos.get('position_size_usd') or 0.0) for pos in bucket)

    def _exposure(bucket: List[Dict]):
        return sum(float(pos.get('position_size_usd') or 0.0) for pos in bucket)

    realized = sum(float(trade.get('pnl_usd') or 0.0) for trade in run_trades)
    wins = sum(1 for trade in run_trades if float(trade.get('pnl_percent') or 0.0) > 0)
    total = len(run_trades)
    win_rate = (wins / total * 100) if total else 0.0

    open_pnl = _open_pnl(run_positions)
    exposure = _exposure(run_positions)

    meta = packet.get('meta', {})
    signal_rows = packet.get('signals', [])[:10]
    signal_headline = packet.get('assets', {}).get('headline', '')

    tier_options = sorted({pos.get('tier', '–') for pos in run_positions if pos.get('tier')})
    exit_reason_options = sorted({get_trade_exit_label(trade) for trade in run_trades})

    run_trades_preview = list(reversed(run_trades[-10:]))

    return {
        'baseline': baseline_str,
        'regime': meta.get('regime', '–'),
        'signals': meta.get('total_signals', 0),
        'scan_time': meta.get('scan_timestamp', '–'),
        'open_positions': len(run_positions),
        'run_positions_detail': run_positions,
        'carryover_positions_detail': carryover_positions,
        'run_trades': run_trades_preview,
        'realized_pnl': realized,
        'open_pnl': open_pnl,
        'exposure': exposure,
        'win_rate': win_rate,
        'top_opportunities': packet.get('signals', [])[:3],
        'signal_rows': signal_rows,
        'signal_headline': signal_headline,
        'entry_events': run_entry_events,
        'loop_status': load_loop_status(),
        'tier_options': tier_options,
        'exit_reason_options': exit_reason_options,
        'pnl_chart': build_pnl_chart_data(run_trades),
        'open_positions_path': positions_path,
        'open_positions_updated': positions_updated,
        'trades_path': trades_path,
        'trades_updated': trades_updated,
        'entry_events_path': entry_events_path,
        'entry_events_updated': entry_events_updated,
    }


def format_positions_table(positions):
    columns = [
        {'name': 'token', 'label': 'Token', 'field': 'token'},
        {'name': 'tier', 'label': 'Tier', 'field': 'tier'},
        {'name': 'pnl', 'label': 'PnL %', 'field': 'pnl'},
        {'name': 'size', 'label': 'Size USD', 'field': 'size'},
    ]
    rows = [
        {
            'token': pos.get('token', '?'),
            'tier': pos.get('tier', '–'),
            'pnl': f"{float(pos.get('pnl_percent') or 0.0):+.2f}%",
            'size': f"${float(pos.get('position_size_usd') or 0.0):.2f}",
        }
        for pos in positions
    ]
    return columns, rows


def get_trade_exit_label(trade):
    return trade.get('exit_category') or trade.get('exit_reason') or '–'


def format_trades_table(trades):
    columns = [
        {'name': 'token', 'label': 'Token', 'field': 'token'},
        {'name': 'pnl', 'label': 'PnL %', 'field': 'pnl'},
        {'name': 'reason', 'label': 'Reason', 'field': 'reason'},
    ]
    rows = [
        {
            'token': trade.get('token', '?'),
            'pnl': f"{float(trade.get('pnl_percent') or 0.0):+.2f}%",
            'reason': get_trade_exit_label(trade),
        }
        for trade in trades
    ]
    return columns, rows


def format_events_table(events):
    columns = [
        {'name': 'time', 'label': 'Time', 'field': 'time'},
        {'name': 'token', 'label': 'Token', 'field': 'token'},
        {'name': 'tier', 'label': 'Tier', 'field': 'tier'},
        {'name': 'reason', 'label': 'Reason', 'field': 'reason'},
    ]
    rows = [
        {
            'time': event.get('timestamp', '')[-8:],
            'token': event.get('token', '?'),
            'tier': event.get('tier', '–'),
            'reason': event.get('reason', '–'),
        }
        for event in events
    ]
    return columns, rows


def format_signals_table(signals):
    columns = [
        {'name': 'token', 'label': 'Token', 'field': 'token'},
        {'name': 'momentum', 'label': 'Momentum %', 'field': 'momentum'},
        {'name': 'volume', 'label': 'Volume (USD)', 'field': 'volume'},
        {'name': 'persistence', 'label': 'Persistence', 'field': 'persistence'},
        {'name': 'status', 'label': 'Status', 'field': 'status'},
    ]
    rows = [
        {
            'token': sig.get('token', '?'),
            'momentum': f"{float(sig.get('momentum') or 0.0):+.1f}%",
            'volume': f"${float(sig.get('volume') or 0.0):,.0f}",
            'persistence': sig.get('persistence', 0),
            'status': sig.get('status', '–').title() if sig.get('status') else '–',
        }
        for sig in signals
    ]
    return columns, rows


def render_top_opportunities(opps):
    if not opps:
        ui.label('No signals available').classes('text-gray-500')
        return
    for entry in opps:
        with ui.card().classes('w-full sm:w-1/3'):
            ui.label(entry.get('token', '?')).classes('text-lg font-semibold')
            ui.label(f"Momentum: {entry.get('momentum', 0):+.1f}%")
            ui.label(f"Volume: ${entry.get('volume', 0):,.0f}")
            ui.label(f"Persistence: {entry.get('persistence', 0)} scans")
            ui.label(f"Liquidity score: {entry.get('liquidity_score', 0):.2f}")


def build_pnl_chart_data(trades: List[Dict]):
    labels: List[str] = []
    pnl_percent: List[float] = []
    cumulative_usd: List[float] = []
    running_total = 0.0
    for trade in trades:
        label = trade.get('token', '?')
        pnl_pct = float(trade.get('pnl_percent') or 0.0)
        position_size = float(trade.get('position_size_usd') or trade.get('position_size') or 0.0)
        pnl_usd = float(trade.get('pnl_usd') or position_size * pnl_pct / 100.0)
        running_total += pnl_usd
        labels.append(label)
        pnl_percent.append(round(pnl_pct, 2))
        cumulative_usd.append(round(running_total, 2))
    return {'labels': labels, 'percent': pnl_percent, 'cumulative': cumulative_usd}


def render_pnl_chart(data: Dict):
    if not data['labels']:
        ui.label('Not enough closes to chart yet').classes('text-gray-500')
        return
    ui.echart(
        {
            'tooltip': {'trigger': 'axis'},
            'legend': {'data': ['PnL %', 'Cumulative USD']},
            'xAxis': {'type': 'category', 'data': data['labels']},
            'yAxis': [
                {'type': 'value', 'name': 'PnL %'},
                {'type': 'value', 'name': 'Cum USD', 'position': 'right'},
            ],
            'series': [
                {
                    'name': 'PnL %',
                    'type': 'bar',
                    'data': data['percent'],
                    'itemStyle': {
                        'color': '#10b981',
                    },
                },
                {
                    'name': 'Cumulative USD',
                    'type': 'line',
                    'yAxisIndex': 1,
                    'data': data['cumulative'],
                    'smooth': True,
                    'lineStyle': {'color': '#2563eb', 'width': 2},
                },
            ],
        }
    ).classes('w-full h-72')


def filter_positions(positions: List[Dict]):
    tier = DASHBOARD_FILTERS['tier']
    if tier == 'All tiers':
        return positions
    return [pos for pos in positions if pos.get('tier') == tier]


def filter_trades(trades: List[Dict]):
    reason_filter = DASHBOARD_FILTERS['exit_reason']
    if reason_filter == 'All exits':
        return trades
    return [trade for trade in trades if get_trade_exit_label(trade) == reason_filter]


def update_tier_filter(value: str):
    DASHBOARD_FILTERS['tier'] = value or 'All tiers'
    render_dashboard.refresh()


def update_exit_filter(value: str):
    DASHBOARD_FILTERS['exit_reason'] = value or 'All exits'
    render_dashboard.refresh()


@ui.refreshable
def render_dashboard():
    metrics = compute_metrics()

    run_positions = metrics['run_positions_detail']
    carryover_positions = metrics['carryover_positions_detail']
    positions_filtered = filter_positions(run_positions)
    carryover_filtered = filter_positions(carryover_positions)
    trades_filtered = filter_trades(metrics['run_trades'])

    global HEADER_REGIME_LABEL, DATA_SOURCE_LABEL
    if HEADER_REGIME_LABEL:
        HEADER_REGIME_LABEL.text = f"Regime: {metrics['regime']}"
    if DATA_SOURCE_LABEL:
        data_source = metrics.get('open_positions_path') or 'Not found'
        data_updated = metrics.get('open_positions_updated') or '–'
        baseline = metrics.get('baseline') or 'not set'
        DATA_SOURCE_LABEL.text = f"Data source: {data_source} (updated {data_updated}) | Run baseline: {baseline}"

    with ui.row().classes('w-full q-col-gutter-md'):
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Open positions (this run)').classes('text-sm text-gray-500')
            ui.label(str(metrics['open_positions'])).classes('text-2xl font-semibold')
            carry_count = len(carryover_positions)
            if carry_count:
                ui.label(f"{carry_count} carryover").classes('text-xs text-gray-500')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Realized PnL (this run)').classes('text-sm text-gray-500')
            ui.label(f"{metrics['realized_pnl']:+.2f}").classes('text-2xl font-semibold')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Win rate (this run)').classes('text-sm text-gray-500')
            ui.label(f"{metrics['win_rate']:.1f}%").classes('text-2xl font-semibold')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Loop status').classes('text-sm text-gray-500')
            ui.label(metrics['loop_status']['status'].title()).classes('text-2xl font-semibold')
            ui.label(f"Last cycle: {metrics['loop_status']['last_cycle']}").classes('text-sm text-gray-500')

    with ui.row().classes('w-full q-col-gutter-md mt-2'):
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Open PnL (USD)').classes('text-sm text-gray-500')
            ui.label(f"{metrics['open_pnl']:+.2f}").classes('text-2xl font-semibold')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Exposure (USD)').classes('text-sm text-gray-500')
            ui.label(f"${metrics['exposure']:.2f}").classes('text-2xl font-semibold')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Signals scanned').classes('text-sm text-gray-500')
            ui.label(str(metrics['signals'])).classes('text-2xl font-semibold')
        with ui.card().classes('w-full sm:w-1/4'):
            ui.label('Last scan').classes('text-sm text-gray-500')
            ui.label(metrics['scan_time']).classes('text-lg font-semibold')

    ui.separator().classes('my-4')
    ui.label('Market context').classes('text-lg font-semibold mb-2')
    with ui.card().classes('w-full mb-4'):
        ui.label(metrics['signal_headline'] or 'No packet headline available').classes('text-sm')

    ui.label('Top opportunities').classes('text-lg font-semibold mb-2')
    with ui.row().classes('w-full q-col-gutter-md'):
        render_top_opportunities(metrics['top_opportunities'])

    ui.separator().classes('my-4')
    ui.label('PnL trend (this run)').classes('text-lg font-semibold mb-2')
    render_pnl_chart(metrics['pnl_chart'])

    ui.separator().classes('my-4')
    ui.label('Open positions (this run)').classes('text-lg font-semibold')
    tier_options = ['All tiers'] + metrics['tier_options']
    with ui.row().classes('items-end q-gutter-md mb-3'):
        tier_select = ui.select(tier_options, label='Tier filter', value=DASHBOARD_FILTERS['tier'])
        tier_select.on_value_change(lambda e: update_tier_filter(e.value))
    columns, rows = format_positions_table(positions_filtered)
    ui.table(columns=columns, rows=rows).classes('w-full mb-6')

    if carryover_positions:
        ui.label('Carryover positions').classes('text-lg font-semibold mb-2')
        carry_columns, carry_rows = format_positions_table(carryover_filtered)
        ui.table(columns=carry_columns, rows=carry_rows).classes('w-full mb-6')

    trade_columns, trade_rows = format_trades_table(trades_filtered)
    ui.label("This run's closes").classes('text-lg font-semibold')
    exit_options = ['All exits'] + metrics['exit_reason_options']
    with ui.row().classes('items-end q-gutter-md mb-3'):
        reason_select = ui.select(exit_options, label='Exit filter', value=DASHBOARD_FILTERS['exit_reason'])
        reason_select.on_value_change(lambda e: update_exit_filter(e.value))
    ui.table(columns=trade_columns, rows=trade_rows).classes('w-full mb-6')

    signal_columns, signal_rows = format_signals_table(metrics['signal_rows'])
    ui.label('Signal depth (top 10)').classes('text-lg font-semibold mb-2')
    ui.table(columns=signal_columns, rows=signal_rows).classes('w-full mb-6')

    event_columns, event_rows = format_events_table(metrics['entry_events'])
    ui.label('Entry events (this run)').classes('text-lg font-semibold mb-2')
    ui.table(columns=event_columns, rows=event_rows).classes('w-full')


@ui.page('/')
def main_page():
    global HEADER_REGIME_LABEL, DATA_SOURCE_LABEL
    with ui.header().classes('justify-between items-center'):
        ui.label('Trader Dashboard').classes('text-xl font-bold')
        HEADER_REGIME_LABEL = ui.label('Regime: –')
    DATA_SOURCE_LABEL = ui.label('Data source: –').classes('text-xs text-gray-500 mb-2')
    render_dashboard()
    ui.timer(30, render_dashboard.refresh)


def run():
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    port = int(os.getenv('DASHBOARD_PORT', '8501'))
    ui.run(title='Trader Dashboard', reload=False, host=host, port=port)


if __name__ == '__main__':
    run()
