from __future__ import annotations

import os

from nicegui import ui

from .common import fmt_num, panel, pill
from .data import compute_dashboard_state, read_runtime_controls, _safe_iso_to_dt
from .runtime_registry import components_by_category
from .theme import apply_theme


def _fmt_meta_ts(value: str | None) -> str:
    dt = _safe_iso_to_dt(value)
    if not dt:
        return '–'
    return dt.astimezone().strftime('%H:%M:%S')


def _candles_svg(candles: list[dict], width: int = 640, height: int = 260) -> str:
    margin_x = 18
    margin_y = 18
    if not candles:
        return '<div class="chart-empty">Waiting for candle data…</div>'

    highs = [float(c['high']) for c in candles]
    lows = [float(c['low']) for c in candles]
    max_high = max(highs)
    min_low = min(lows)
    price_range = max(max_high - min_low, 1e-9)

    plot_w = width - margin_x * 2
    plot_h = height - margin_y * 2
    step = plot_w / max(len(candles), 1)
    body_w = max(step * 0.55, 4)

    def y(price: float) -> float:
        return margin_y + (max_high - price) / price_range * plot_h

    svg = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">',
        '<defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#73f5ff" stop-opacity="0.20"/><stop offset="100%" stop-color="#050816" stop-opacity="0"/></linearGradient></defs>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#g)"/>',
    ]

    for i in range(5):
        gy = margin_y + (plot_h / 4) * i
        svg.append(f'<line x1="{margin_x}" y1="{gy:.2f}" x2="{width-margin_x}" y2="{gy:.2f}" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>')

    closes_path = []
    for idx, candle in enumerate(candles):
        x = margin_x + step * idx + step / 2
        high_y = y(float(candle['high']))
        low_y = y(float(candle['low']))
        open_y = y(float(candle['open']))
        close_y = y(float(candle['close']))
        color = '#7bf7c6' if float(candle['close']) >= float(candle['open']) else '#ff8d9b'
        top = min(open_y, close_y)
        body_h = max(abs(close_y - open_y), 3)
        svg.append(f'<line x1="{x:.2f}" y1="{high_y:.2f}" x2="{x:.2f}" y2="{low_y:.2f}" stroke="{color}" stroke-width="2" opacity="0.95"/>')
        svg.append(f'<rect x="{x - body_w/2:.2f}" y="{top:.2f}" width="{body_w:.2f}" height="{body_h:.2f}" rx="2" fill="{color}" opacity="0.95"/>')
        closes_path.append(f'{x:.2f},{close_y:.2f}')

    if closes_path:
        svg.append(f'<polyline points="{" ".join(closes_path)}" stroke="#73f5ff" stroke-width="1.5" fill="none" opacity="0.22"/>')

    svg.append('</svg>')
    return ''.join(svg)


def _candidate_candles(btc_candles: list[dict], seed: float = 1.0) -> list[dict]:
    if not btc_candles:
        return []
    out = []
    for idx, candle in enumerate(btc_candles[-24:]):
        scale = 1.0 + (seed * 0.002)
        drift = ((idx % 5) - 2) * seed * 0.0008
        open_p = float(candle['open']) * scale * (1 + drift)
        close_p = float(candle['close']) * scale * (1 + drift * 1.1)
        high_p = max(open_p, close_p) * (1 + 0.0015)
        low_p = min(open_p, close_p) * (1 - 0.0015)
        out.append({'open': open_p, 'close': close_p, 'high': high_p, 'low': low_p})
    return out


@ui.refreshable
def stream_view():
    state = compute_dashboard_state()
    market_state = state['market_state']
    ws_state = state['ws_state']
    metrics = market_state.get('metrics', {})
    top_opps = market_state.get('top_opportunities', [])
    live_movers = state['live_movers']
    btc_payload = state.get('btc_candles', {})
    btc_candles = btc_payload.get('candles', [])
    open_positions = state.get('open_positions', [])
    open_positions_v2 = state.get('open_positions_v2', [])
    v2_audit = state.get('paper_trader_v2_audit', {})
    social_pulse = state.get('social_intel_pulse', {})
    runtime = read_runtime_controls()
    scanner_status = 'RUNNING' if runtime['market_scanner']['running'] else 'IDLE'
    feed_status = 'RUNNING' if runtime['coinbase_feed']['running'] else 'STOPPED'
    trader_status = 'RUNNING' if runtime['paper_trader_v2']['running'] else 'STOPPED'
    loop_cycle_status = 'RECENT' if state.get('main_loop_status', {}).get('last_cycle_started_at') else 'NONE'
    loop_status = 'RUNNING' if runtime['main_loop']['running'] else 'ACTIVE' if loop_cycle_status == 'RECENT' else 'IDLE'
    scanner_log_time = _fmt_meta_ts((runtime.get('market_scanner') or {}).get('log_meta', {}).get('updated_at'))
    loop_log_time = _fmt_meta_ts((runtime.get('main_loop') or {}).get('log_meta', {}).get('updated_at'))
    flatten_runtime = runtime.get('paper_trader_v2', {})
    flatten_status = 'IDLE'
    flatten_log_time = _fmt_meta_ts((flatten_runtime or {}).get('log_meta', {}).get('updated_at'))
    last_manual_flatten = _fmt_meta_ts((v2_audit or {}).get('last_manual_flatten_at'))
    log_outputs_status = 'RUNNING' if runtime.get('market_broadcaster', {}).get('running') else 'IDLE'
    log_outputs_time = _fmt_meta_ts((runtime.get('market_broadcaster') or {}).get('log_meta', {}).get('updated_at'))

    with ui.column().classes('stream-stage w-full h-screen gap-2 p-3'):
        with ui.card().classes('top-bar w-full stream-hero stage-top'):
            with ui.row().classes('w-full justify-between items-center'):
                with ui.column().classes('gap-0'):
                    ui.label('LokiAI Market Engine').classes('hero-title')
                    ui.label('Autonomous market intelligence cockpit • paper-only rebuild phase').classes('hero-subtitle')
                with ui.row().classes('gap-3 items-center wrap'):
                    pill('STREAM • LIVE', 'healthy')
                    pill(f"SCANNER DATA • {market_state.get('metrics', {}).get('total_signals', 0)} SIGNALS", 'info')
                    pill(f"SCANNER JOB • {scanner_status}", 'healthy' if scanner_status == 'RUNNING' else 'info')
                    pill(f"SCANNER LOG • {scanner_log_time}", 'info')
                    pill(f"COINBASE FEED • {feed_status}", 'healthy' if feed_status == 'RUNNING' else 'danger')

        with ui.row().classes('w-full no-wrap gap-2 stage-main'):
            with ui.column().classes('stream-left gap-3'):
                with panel('Live Movers', 'Tracked Coinbase names showing live movement now', 'left-panel-compact'):
                    if not live_movers:
                        ui.label('Waiting for live ticker population').classes('text-gray-400')
                    for mover in live_movers[:6]:
                        with ui.row().classes('w-full justify-between items-center telemetry-row'):
                            with ui.column().classes('gap-0'):
                                ui.label(mover['product_id']).classes('font-semibold')
                                ui.label(f"px {fmt_num(mover.get('price'), 4)}").classes('signal-meta')
                            with ui.column().classes('items-end gap-0'):
                                drift = float(mover.get('drift_300s') or 0.0)
                                drift_cls = 'status-healthy' if drift > 0 else 'status-warning' if drift < 0 else 'telemetry-value'
                                ui.label(f"{fmt_num(drift, 3)}%").classes(f'font-semibold {drift_cls}')
                                ui.label(f"{fmt_num(mover.get('freshness_seconds'), 1)}s").classes('signal-meta')

                with panel('Scanner Highlights', 'Names the system currently rates highest', 'left-panel-compact'):
                    if not top_opps:
                        ui.label('No scanner highlights yet').classes('text-gray-400')
                    for opp in top_opps[:4]:
                        with ui.row().classes('w-full justify-between items-center signal-row'):
                            with ui.column().classes('gap-0'):
                                ui.label(opp.get('token', '?')).classes('signal-symbol')
                                ui.label(f"trend • {opp.get('trend', '–')}").classes('signal-meta')
                            with ui.column().classes('items-end gap-0'):
                                ui.label(f"{fmt_num(opp.get('momentum'), 1)}%").classes('signal-momentum')
                                ui.label(f"persistence {opp.get('persistence', 0)}").classes('signal-meta')

                with panel('Distribution', 'Current outward-facing surfaces', 'left-panel-compact'):
                    ui.label('Brief → lokiai.substack.com').classes('text-sm panel-row')
                    ui.label('Pack → lokiclips.gumroad.com').classes('text-sm panel-row')
                    ui.label('Posting → controlled').classes('text-sm panel-row')

            with ui.column().classes('stream-center gap-3'):
                with ui.card().classes('glass-panel cockpit-hero w-full h-full'):
                    active_slots = open_positions_v2[:3]
                    focus_items = top_opps[:4]

                    with ui.row().classes('w-full justify-between items-start'):
                        with ui.column().classes('gap-0'):
                            ui.label('Trader Watchboard').classes('panel-title')
                            ui.label('Active positions, top candidates, and current trigger logic').classes('panel-subtitle')
                        with ui.column().classes('items-end gap-1'):
                            ui.label('PAPER-FIRST').classes('status-pill status-info')
                            ui.label('REFRESH TARGET • 3S VISUAL / 30S CORE').classes('panel-subtitle')

                    with ui.card().classes('mission-overlay-card w-full'):
                        ui.label('ACTIVE POSITIONS').classes('mission-card-title')
                        with ui.row().classes('w-full gap-2 wrap'):
                            for idx in range(3):
                                slot = active_slots[idx] if idx < len(active_slots) else None
                                chart = _candidate_candles(btc_candles, idx + 1)
                                with ui.card().classes('glass-panel flex-1 min-w-[160px] p-2'):
                                    if slot:
                                        ui.label(str(slot.get('token', '?'))).classes('signal-symbol')
                                        ui.label(f"entry {fmt_num(slot.get('entry_price'), 4)} • pnl {fmt_num(slot.get('pnl_percent'), 2)}%").classes('signal-meta')
                                        ui.html(f'<div class="mini-candle-shell compact-slot">{_candles_svg(chart, width=260, height=92)}</div>').classes('w-full')
                                        ui.label(str(slot.get('trade_state', 'ACTIVE')).upper()).classes('status-pill status-healthy')
                                    else:
                                        ui.label(f'SLOT {idx + 1}').classes('signal-symbol')
                                        ui.label('No active position').classes('signal-meta')
                                        ui.html(f'<div class="mini-candle-shell compact-slot ghost-shell">{_candles_svg(chart, width=260, height=92)}</div>').classes('w-full')
                                        ui.label('EMPTY').classes('status-pill status-info')

                    with ui.card().classes('mission-overlay-card w-full focus-panel'):
                        ui.label('TRADER FOCUS').classes('mission-card-title focus-title')
                        with ui.grid(columns=2).classes('w-full gap-2 mt-1'):
                            for idx in range(4):
                                opp = focus_items[idx] if idx < len(focus_items) else None
                                with ui.card().classes('glass-panel w-full focus-card p-[0.28rem]'):
                                    if opp:
                                        chart = _candidate_candles(btc_candles, idx + 1.5)
                                        status = 'READY' if idx == 0 else 'WATCH' if idx < 3 else 'FADING'
                                        ui.label(str(opp.get('token', '?'))).classes('signal-symbol text-sm')
                                        ui.label(f"{fmt_num(opp.get('momentum'), 1)}% • p{opp.get('persistence', 0)} • {opp.get('trend', '–')}").classes('signal-meta text-xs')
                                        ui.html(f'<div class="mini-candle-shell compact-focus">{_candles_svg(chart, width=250, height=80)}</div>').classes('w-full')
                                        badge_cls = 'status-healthy' if status == 'READY' else 'status-info' if status == 'WATCH' else 'status-warning'
                                        ui.label(status).classes(f'status-pill {badge_cls} text-[10px]')
                                    else:
                                        ghost = _candidate_candles(btc_candles, idx + 2.2)
                                        ui.label(f'OPEN SLOT {idx + 1}').classes('signal-symbol text-sm')
                                        ui.label('Waiting for a qualified setup').classes('signal-meta text-xs')
                                        ui.html(f'<div class="mini-candle-shell compact-focus ghost-shell">{_candles_svg(ghost, width=250, height=80)}</div>').classes('w-full')
                                        ui.label('IDLE').classes('status-pill status-info text-[10px]')

                    with ui.card().classes('mission-overlay-card w-full'):
                        ui.label('TRADER CONTEXT').classes('mission-card-title')
                        with ui.row().classes('w-full justify-between items-center wrap'):
                            ui.label(f"MODE • PAPER-FIRST / {loop_status}").classes('mission-card-meta')
                            ui.label(f"OPEN POSITIONS • {len(active_slots)}").classes('mission-card-meta')
                            ui.label(f"OPEN SLOTS • {max(0, 4 - len(active_slots))}").classes('mission-card-meta')
                            ui.label('TRIGGER • MOMENTUM + PERSISTENCE + VOLUME').classes('mission-card-meta')

                    with ui.row().classes('w-full justify-between items-center chart-footer'):
                        ui.label('trader-centered stream interface • pass 1 skeleton').classes('panel-subtitle')
                        ui.label(f"captured {metrics.get('total_signals', 0)} • active slots {len(active_slots)} • closed {v2_audit.get('closed_trade_count', 0)}").classes('panel-subtitle')


            with ui.column().classes('stream-right gap-2 compact-right-rail'):
                with panel('System Posture', 'Current operating stance', 'right-panel-tall compact-status-panel'):
                    ui.label('PAPER ONLY').classes('text-sm font-semibold status-info')
                    ui.label('No live funds active.').classes('text-sm panel-row compact-copy')
                    ui.label('System focus: stability, control, signal quality.').classes('text-sm panel-row compact-copy')
                    ui.separator().classes('my-1 opacity-20')
                    ui.label('Core Systems').classes('telemetry-key compact-key mt-1')
                    ui.label(f'Feed: {str(runtime.get("coinbase_feed", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                    ui.label(f'Scanner: {str(runtime.get("market_scanner", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                    ui.label(f'Trader: {str(runtime.get("paper_trader_v2", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                    ui.label('Cycle State').classes('telemetry-key compact-key mt-1')
                    ui.label(f'Main loop: {loop_status}').classes('telemetry-value compact-value')
                    ui.label(f'Last cycle: {loop_cycle_status}').classes('telemetry-value compact-value')
                    ui.label(f'Loop log: {loop_log_time}').classes('telemetry-value compact-value')
                    ui.label('Trading State').classes('telemetry-key compact-key mt-1')
                    ui.label(f'Active V2 slots: {len(open_positions_v2)}').classes('telemetry-value compact-value')
                    ui.label(f'Closed V2 trades: {v2_audit.get("closed_trade_count", 0)}').classes('telemetry-value compact-value')
                    ui.label(f'Last flatten: {last_manual_flatten}').classes('telemetry-value compact-value')
                    ui.label('Distribution').classes('telemetry-key compact-key mt-1')
                    ui.label(f'Broadcaster: {str(runtime.get("market_broadcaster", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                    ui.label(f'Reports: {str(runtime.get("performance_analyzer", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')

                with panel('Research Surface', 'Current intelligence layer', 'compact-right-panel'):
                    ui.label('Atlas Pulse').classes('font-semibold compact-headline')
                    ui.label('Daily Coinbase momentum brief.').classes('text-sm panel-row compact-copy')
                    ui.label('Distribution remains controlled.').classes('text-sm panel-row compact-copy')

                with panel('Social / Intel Pulse', 'Curated catalyst layer', 'compact-right-panel'):
                    items = social_pulse.get('items', [])[:2]
                    if not items:
                        ui.label('No intel pulse yet').classes('font-semibold status-warning')
                    for item in items:
                        ui.label(f"{item.get('category', 'intel').upper()} • {item.get('headline', 'Untitled')}").classes('font-semibold compact-headline')
                        ui.label(item.get('market_implication', 'No implication yet')).classes('text-sm panel-row compact-copy')
                        ui.label(f"{item.get('source', 'unknown')} • {item.get('actionability', 'observe')}").classes('text-xs panel-row opacity-70 compact-copy')



@ui.page('/')
def index():
    with ui.column().classes('w-full min-h-screen dashboard-shell stream-root'):
        stream_view()
    ui.timer(30, stream_view.refresh)


def run():
    apply_theme()
    ui.add_head_html(
        '''
        <style>
            .stream-root { overflow: hidden; }
            .stream-stage { min-height: 100vh; box-sizing: border-box; overflow: auto; }
            .stage-top { flex: 0 0 auto; }
            .stage-main { flex: 1 1 auto; min-height: 0; align-items: stretch; }
            .stream-left, .stream-right { width: 22%; min-width: 22%; max-width: 22%; }
            .stream-center { width: 56%; min-width: 56%; max-width: 56%; }
            .cockpit-hero {
                position: relative;
                overflow: hidden;
                border-color: rgba(115, 245, 255, 0.32);
                box-shadow: 0 0 30px rgba(0, 220, 255, 0.16), inset 0 0 48px rgba(180, 0, 255, 0.07);
            }
            .cockpit-hero::before {
                content: '';
                position: absolute;
                inset: 0;
                border: 1px solid rgba(255,255,255,0.05);
                clip-path: polygon(2% 0, 98% 0, 100% 8%, 100% 92%, 98% 100%, 2% 100%, 0 92%, 0 8%);
                pointer-events: none;
            }
            .candle-shell {
                width: 100%;
                height: 100%;
                min-height: 420px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: radial-gradient(circle at center, rgba(115,245,255,0.08), transparent 55%);
            }
            .left-panel-compact .telemetry-row, .left-panel-compact .signal-row { padding: 0.22rem 0; }
            .left-panel-compact .panel-subtitle { font-size: 0.72rem; }
            .center-lower { flex: 0 0 auto; }
            .mini-panel { min-height: 112px; }
            .mini-panel .panel-row { padding: 0.16rem 0; }
            .right-panel-tall { min-height: 200px; }
            .compact-right-rail { gap: 0.45rem !important; }
            .compact-right-panel { min-height: 132px; }
            .compact-right-panel .panel-title { font-size: 0.9rem; }
            .compact-right-panel .panel-subtitle { font-size: 0.66rem; }
            .compact-right-panel .panel-row { padding: 0.06rem 0; line-height: 1.08; }
            .compact-status-panel .panel-subtitle { font-size: 0.68rem; }
            .compact-status-panel .panel-row { padding: 0.08rem 0; line-height: 1.15; }
            .compact-copy { line-height: 1.08; margin: 0; }
            .compact-key { margin-top: 0.12rem !important; }
            .compact-value { line-height: 1.02; }
            .compact-headline { font-size: 0.82rem; line-height: 1.05; }
            .mission-strip {
                border: 1px solid rgba(255,255,255,0.06);
                background: rgba(255,255,255,0.03);
                border-radius: 12px;
                padding: 0.45rem 0.7rem;
                margin-top: 0.35rem;
            }
            .mission-state {
                color: #73f5ff;
                font-size: 0.9rem;
                font-weight: 700;
                letter-spacing: 0.08em;
            }
            .mission-focus {
                color: #f3fbff;
                font-size: 0.82rem;
                font-weight: 600;
            }
            .mission-lower {
                margin-top: 0.35rem;
            }
            .mission-overlay-card {
                background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(9,16,28,0.88));
                border: 1px solid rgba(115,245,255,0.14);
                border-radius: 14px;
                padding: 0.7rem;
                box-shadow: inset 0 0 28px rgba(115,245,255,0.035), 0 0 18px rgba(0,0,0,0.24);
            }
            .mission-card-title {
                color: rgba(210, 225, 255, 0.72);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            .mission-card-body {
                color: #f4fbff;
                font-size: 0.95rem;
                font-weight: 700;
                margin-top: 0.2rem;
            }
            .mission-card-meta {
                color: rgba(210, 225, 255, 0.72);
                font-size: 0.74rem;
                margin-top: 0.18rem;
            }
            .chart-footer { border-top: 1px solid rgba(255,255,255,0.06); padding-top: 0.25rem; }
            .mini-candle-shell {
                width: 100%;
                min-height: 116px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: radial-gradient(circle at center, rgba(115,245,255,0.10), transparent 60%);
                border: 1px solid rgba(115,245,255,0.08);
                border-radius: 10px;
                overflow: hidden;
                margin-top: 0.3rem;
                box-shadow: inset 0 0 20px rgba(115,245,255,0.04);
            }
            .compact-slot {
                min-height: 88px;
            }
            .compact-focus {
                min-height: 62px;
            }
            .focus-panel {
                padding: 0.5rem !important;
            }
            .focus-title {
                margin-bottom: 0.15rem;
            }
            .focus-card {
                min-height: 0;
            }
            .empty-mini {
                color: rgba(210, 225, 255, 0.6);
                font-size: 0.75rem;
            }
            .ghost-shell {
                opacity: 0.48;
                filter: saturate(0.75) brightness(0.88);
            }
            .tactical-empty {
                color: #73f5ff;
                text-shadow: 0 0 10px rgba(115,245,255,0.24);
                letter-spacing: 0.08em;
            }
        </style>
        ''', shared=True
    )
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    port = int(os.getenv('DASHBOARD_PORT', '8501'))
    ui.run(title='LokiAI Stream Dashboard', reload=False, host=host, port=port)


if __name__ == '__main__':
    run()
