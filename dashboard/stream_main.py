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
    body_w = max(step * 0.62, 4.5)

    def y(price: float) -> float:
        return margin_y + (max_high - price) / price_range * plot_h

    latest_close = float(candles[-1]['close']) if candles else 0.0
    latest_open = float(candles[-1]['open']) if candles else latest_close
    latest_y = y(latest_close)
    latest_up = latest_close >= latest_open
    latest_color = '#2dffb2' if latest_up else '#ff5f87'

    svg = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">',
        '<defs>'
        '<linearGradient id="g" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0%" stop-color="#0c1626" stop-opacity="1"/>'
        '<stop offset="100%" stop-color="#04070f" stop-opacity="1"/>'
        '</linearGradient>'
        '<filter id="glow"><feGaussianBlur stdDeviation="2.4" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '</defs>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#g)"/>',
        f'<line x1="{margin_x}" y1="{latest_y:.2f}" x2="{width-margin_x}" y2="{latest_y:.2f}" stroke="{latest_color}" stroke-width="1.6" opacity="0.38"/>',
    ]

    for i in range(5):
        gy = margin_y + (plot_h / 4) * i
        svg.append(f'<line x1="{margin_x}" y1="{gy:.2f}" x2="{width-margin_x}" y2="{gy:.2f}" stroke="rgba(120,170,255,0.10)" stroke-width="1"/>')

    closes_path = []
    for idx, candle in enumerate(candles):
        x = margin_x + step * idx + step / 2
        high_y = y(float(candle['high']))
        low_y = y(float(candle['low']))
        open_y = y(float(candle['open']))
        close_y = y(float(candle['close']))
        is_up = float(candle['close']) >= float(candle['open'])
        is_latest = idx == len(candles) - 1
        color = '#18e899' if is_up else '#ff4d6d'
        wick_color = '#74ffd1' if is_up else '#ff92a5'
        top = min(open_y, close_y)
        body_h = max(abs(close_y - open_y), 3)
        wick_width = 2.3 if is_latest else 1.7
        body_opacity = 1.0 if is_latest else 0.94
        body_width = body_w * (1.08 if is_latest else 1.0)
        svg.append(f'<line x1="{x:.2f}" y1="{high_y:.2f}" x2="{x:.2f}" y2="{low_y:.2f}" stroke="{wick_color}" stroke-width="{wick_width}" opacity="0.98" {"filter=\"url(#glow)\"" if is_latest else ""}/>')
        svg.append(f'<rect x="{x - body_width/2:.2f}" y="{top:.2f}" width="{body_width:.2f}" height="{body_h:.2f}" rx="2" fill="{color}" opacity="{body_opacity:.2f}" {"filter=\"url(#glow)\"" if is_latest else ""}/>')
        closes_path.append(f'{x:.2f},{close_y:.2f}')

    if closes_path:
        svg.append(f'<polyline points="{" ".join(closes_path)}" stroke="{latest_color}" stroke-width="1.8" fill="none" opacity="0.20"/>')
        last_x = margin_x + step * (len(candles) - 1) + step / 2
        svg.append(f'<circle cx="{last_x:.2f}" cy="{latest_y:.2f}" r="3.2" fill="{latest_color}" opacity="0.92" filter="url(#glow)"/>')

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
    focus_leads = state.get('focus_leads', [])
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
    trader_mode = str(v2_audit.get('mode', 'watch')).upper()
    active_slot_count = int(v2_audit.get('active_slot_count', len(open_positions_v2)) or 0)
    closed_trade_count = int(v2_audit.get('closed_trade_count', 0) or 0)
    win_count = int(v2_audit.get('win_count', 0) or 0)
    loss_count = int(v2_audit.get('loss_count', 0) or 0)
    high_quality_signals = int(metrics.get('high_quality_signals', 0) or 0)
    total_signals = int(metrics.get('total_signals', 0) or 0)
    trader_runtime_state = str(runtime.get('paper_trader_v2', {}).get('display_state', trader_status)).upper()

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

            with ui.column().classes('stream-center gap-2'):
                with ui.card().classes('glass-panel cockpit-hero w-full h-full watchboard-shell'):
                    active_slots = open_positions_v2[:3]
                    focus_items = focus_leads[:3]

                    with ui.row().classes('w-full justify-between items-start stream-center-header'):
                        with ui.column().classes('gap-0'):
                            ui.label('Trader Watchboard').classes('panel-title text-[13px]')
                            ui.label('Active positions, top candidates, and current trigger logic').classes('panel-subtitle text-[10px]')
                        with ui.column().classes('items-end gap-0'):
                            ui.label('PAPER-FIRST').classes('status-pill status-info text-[10px]')
                            ui.label('3S VISUAL • 30S CORE').classes('panel-subtitle text-xs')

                    with ui.card().classes('mission-overlay-card w-full compact-active-panel center-tight-panel stream-active-block'):
                        ui.label('ACTIVE POSITIONS').classes('mission-card-title focus-title')
                        with ui.row().classes('w-full gap-2 wrap'):
                            for idx in range(3):
                                slot = active_slots[idx] if idx < len(active_slots) else None
                                chart = load_product_candles(str(slot.get('product_id')), limit=24, granularity=60).get('candles', []) if slot and slot.get('product_id') else _candidate_candles(btc_candles, idx + 1)
                                shell_cls = 'mini-candle-shell compact-slot' if slot else 'mini-candle-shell compact-slot ghost-shell'
                                with ui.card().classes('glass-panel flex-1 min-w-[150px] p-[0.28rem]'):
                                    if slot:
                                        ui.label(str(slot.get('token', '?'))).classes('signal-symbol')
                                        ui.label(f"entry {fmt_num(slot.get('entry_price'), 4)} • live {fmt_num(slot.get('current_price'), 4)}").classes('signal-meta')
                                        ui.label(f"pnl {fmt_num(slot.get('pnl_percent'), 2)}% • {int(slot.get('time_in_trade_minutes', 0) or 0)}m • {str(slot.get('product_id', '–'))}").classes('signal-meta')
                                        ui.html(f'<div class="{shell_cls}">{_candles_svg(chart, width=240, height=82)}</div>').classes('w-full')
                                        ui.label(str(slot.get('trade_state', 'ACTIVE')).upper()).classes('status-pill status-healthy')
                                    else:
                                        ui.label(f'SLOT {idx + 1}').classes('signal-symbol')
                                        ui.label('Waiting for qualified entry').classes('signal-meta')
                                        ui.label('No live position in this slot').classes('signal-meta')
                                        ui.html(f'<div class="{shell_cls}">{_candles_svg(chart, width=240, height=82)}</div>').classes('w-full')
                                        ui.label('STANDBY').classes('status-pill status-info')

                    with ui.card().classes('mission-overlay-card w-full compact-active-panel center-tight-panel stream-focus-block focus-shell'):
                        ui.label('TRADER FOCUS').classes('mission-card-title focus-title')
                        with ui.row().classes('w-full gap-2 wrap focus-row'):
                            for idx in range(3):
                                opp = focus_items[idx] if idx < len(focus_items) else None
                                chart = (opp or {}).get('candles') or _candidate_candles(btc_candles, idx + 1.5)
                                shell_cls = 'mini-candle-shell compact-slot' if opp else 'mini-candle-shell compact-slot ghost-shell'
                                with ui.card().classes('glass-panel flex-1 min-w-[150px] p-[0.28rem] focus-card-fit'):
                                    if opp:
                                        ui.label(str(opp.get('token', '?'))).classes('signal-symbol')
                                        ui.label(f"score {fmt_num(opp.get('score'), 3)} • {str(opp.get('source', opp.get('status', 'watch'))).upper()}").classes('signal-meta')
                                        ui.label(f"mom {fmt_num(opp.get('momentum'), 1)}% • p{opp.get('persistence', 0)} • {opp.get('trend', '–')}").classes('signal-meta')
                                        ui.label(f"{str(opp.get('product_id', '–'))} • drift {fmt_num((opp.get('drift_300s') or 0), 3)}% • fresh {fmt_num(opp.get('freshness_seconds'), 1)}s").classes('signal-meta')
                                        ui.html(f'<div class="{shell_cls}">{_candles_svg(chart, width=228, height=72)}</div>').classes('w-full')
                                        ui.label(str(opp.get('status', opp.get('source', 'WATCH'))).upper()).classes('status-pill status-info')
                                    else:
                                        ui.label(f'LEAD SLOT {idx + 1}').classes('signal-symbol')
                                        ui.label('No qualified lead').classes('signal-meta')
                                        ui.label('Scanner awaiting stronger setup').classes('signal-meta')
                                        ui.html(f'<div class="{shell_cls}">{_candles_svg(chart, width=228, height=72)}</div>').classes('w-full')
                                        ui.label('IDLE').classes('status-pill status-warning')

                    with ui.card().classes('mission-overlay-card w-full center-tight-panel stream-context-block'):
                        ui.label('TRADER CONTEXT').classes('mission-card-title focus-title')
                        with ui.column().classes('w-full gap-1'):
                            with ui.row().classes('w-full justify-between items-center wrap'):
                                ui.label(f"MODE • {trader_mode}").classes('mission-card-meta')
                                ui.label(f"TRADER • {trader_runtime_state}").classes('mission-card-meta')
                                ui.label(f"LOOP • {loop_status}").classes('mission-card-meta')
                            with ui.row().classes('w-full justify-between items-center wrap'):
                                ui.label(f"ACTIVE SLOTS • {active_slot_count}/3").classes('mission-card-meta')
                                ui.label(f"HQ SIGNALS • {high_quality_signals}/{total_signals}").classes('mission-card-meta')
                                ui.label(f"CLOSED • {closed_trade_count}").classes('mission-card-meta')
                            with ui.row().classes('w-full justify-between items-center wrap'):
                                ui.label(f"W/L • {win_count}-{loss_count}").classes('mission-card-meta')
                                ui.label('TRIGGER • MOMENTUM + PERSISTENCE').classes('mission-card-meta')
                                ui.label(f"LEADS • {len(focus_items)}").classes('mission-card-meta')

                    with ui.row().classes('w-full justify-between items-center chart-footer'):
                        ui.label(f"{trader_mode} mode • {active_slot_count} active slots • {len(focus_items)} leads in watch").classes('panel-subtitle')
                        ui.label(f"scanner {total_signals} • high-quality {high_quality_signals} • closed {closed_trade_count}").classes('panel-subtitle')


            with ui.column().classes('stream-right gap-2 compact-right-rail'):
                with panel('System State', 'Core runtime posture', 'right-panel-tall compact-status-panel'):
                    with ui.column().classes('w-full h-full gap-2'):
                        with ui.column().classes('w-full gap-0'):
                            ui.label('PAPER ONLY').classes('text-sm font-semibold status-info')
                            ui.label('No live funds active.').classes('text-sm panel-row compact-copy')
                            ui.label('Focus: stability, control, signal quality.').classes('text-sm panel-row compact-copy')
                        with ui.row().classes('w-full gap-3 no-wrap items-start'):
                            with ui.column().classes('flex-1 gap-1 min-w-0'):
                                ui.label('Core Systems').classes('telemetry-key compact-key mt-1')
                                ui.label(f'Feed: {str(runtime.get("coinbase_feed", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                                ui.label(f'Scanner: {str(runtime.get("market_scanner", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                                ui.label(f'Trader: {str(runtime.get("paper_trader_v2", {}).get("display_state", "IDLE")).upper()}').classes('telemetry-value compact-value')
                                ui.label(f'Loop: {loop_status}').classes('telemetry-value compact-value')
                            with ui.column().classes('flex-1 gap-1 min-w-0'):
                                ui.label('Data Freshness').classes('telemetry-key compact-key mt-1')
                                ui.label(f'Scanner log: {scanner_log_time}').classes('telemetry-value compact-value')
                                ui.label(f'Loop log: {loop_log_time}').classes('telemetry-value compact-value')
                                ui.label(f'Feed: {feed_status}').classes('telemetry-value compact-value')

                with panel('Trading State', 'Paper trader execution posture', 'compact-right-panel compact-status-panel'):
                    with ui.column().classes('w-full h-full justify-between gap-2'):
                        with ui.column().classes('w-full gap-0'):
                            ui.label(f'Mode: {trader_mode}').classes('font-semibold compact-headline')
                            ui.label(f'Active slots: {active_slot_count}/3').classes('text-sm panel-row compact-copy')
                            ui.label(f'Closed trades: {closed_trade_count}').classes('text-sm panel-row compact-copy')
                        with ui.column().classes('w-full gap-0'):
                            ui.label(f'Win / Loss: {win_count}-{loss_count}').classes('text-sm panel-row compact-copy')
                            ui.label(f'Last flatten: {last_manual_flatten}').classes('text-sm panel-row compact-copy')
                        with ui.column().classes('w-full gap-0'):
                            ui.label(f'Broadcaster: {str(runtime.get("market_broadcaster", {}).get("display_state", "IDLE")).upper()}').classes('text-sm panel-row compact-copy')
                            ui.label(f'Reports: {str(runtime.get("performance_analyzer", {}).get("display_state", "IDLE")).upper()}').classes('text-sm panel-row compact-copy')

                with panel('Social / Intel Pulse', 'Curated catalyst layer', 'compact-right-panel'):
                    with ui.column().classes('w-full h-full justify-between gap-2'):
                        items = social_pulse.get('items', [])[:2]
                        if not items:
                            with ui.column().classes('w-full gap-1'):
                                ui.label('No intel pulse yet').classes('font-semibold status-warning')
                                ui.label('Research layer standing by for fresh catalysts.').classes('text-sm panel-row compact-copy')
                        for item in items:
                            with ui.column().classes('w-full gap-1'):
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
            .stream-center { width: 56%; min-width: 56%; max-width: 56%; min-height: 0; height: 100%; }
            .cockpit-hero {
                position: relative;
                overflow: hidden;
                height: 100%;
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
            .watchboard-shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
            }
            .stream-center-header { flex: 0 0 auto; }
            .stream-active-block { flex: 0 0 auto; }
            .stream-focus-block { flex: 1 1 auto; min-height: 0; overflow: hidden; }
            .focus-shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
            }
            .focus-row {
                flex: 1 1 auto;
                min-height: 0;
                align-items: stretch;
            }
            .focus-card-fit {
                display: flex;
                flex-direction: column;
                min-height: 0;
                overflow: hidden;
                gap: 0.08rem;
            }
            .stream-context-block { flex: 0 0 auto; }
            .chart-footer { flex: 0 0 auto; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 0.25rem; }
            .mini-candle-shell {
                width: 100%;
                min-height: 100px;
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
                min-height: 62px;
            }
            .compact-focus {
                min-height: 34px;
            }
            .lead-focus {
                min-height: 42px;
            }
            .focus-panel {
                padding: 0.5rem !important;
            }
            .ultra-compact-focus-panel {
                padding: 0.28rem !important;
            }
            .extreme-focus-panel {
                padding: 0.16rem !important;
            }
            .compact-active-panel {
                padding: 0.45rem !important;
            }
            .center-tight-panel {
                padding: 0.22rem !important;
            }
            .focus-title {
                margin-bottom: 0.15rem;
            }
            .focus-card {
                min-height: 0;
            }
            .ultra-compact-focus-card {
                line-height: 1.0;
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
