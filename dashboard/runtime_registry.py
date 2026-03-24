from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
CACHE_DIR = WORKSPACE / 'cache'
SYSTEM_LOG_DIR = WORKSPACE / 'system_logs'
PAPER_TRADES_DIR = WORKSPACE / 'paper_trades'


@dataclass(slots=True)
class ComponentDef:
    id: str
    name: str
    category: str
    kind: str  # service | job | mode
    pid_file: Path | None = None
    log_path: Path | None = None
    outputs: list[Path] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    notes: str = ''
    start_script: str | None = None
    inspect_target: Path | None = None
    start_label: str | None = None
    desired_default: str | None = None


COMPONENTS: dict[str, ComponentDef] = {
    'coinbase_feed': ComponentDef(
        id='coinbase_feed',
        name='Coinbase Feed',
        category='data_plane',
        kind='service',
        pid_file=SYSTEM_LOG_DIR / 'coinbase_ws.pid',
        log_path=SYSTEM_LOG_DIR / 'coinbase_ws.log',
        outputs=[CACHE_DIR / 'coinbase_ws_state.json', CACHE_DIR / 'coinbase_tickers.json'],
        notes='Primary websocket/data-plane service.',
        start_script='run_coinbase_ws.sh',
        inspect_target=SYSTEM_LOG_DIR / 'coinbase_ws.log',
        desired_default='on',
    ),
    'market_scanner': ComponentDef(
        id='market_scanner',
        name='Market Scanner',
        category='data_plane',
        kind='job',
        pid_file=SYSTEM_LOG_DIR / 'scanner.pid',
        log_path=SYSTEM_LOG_DIR / 'scanner.log',
        outputs=[CACHE_DIR / 'market_state.json'],
        dependencies=['coinbase_feed'],
        notes='One-shot ranking/scanner job producing market_state.',
        start_script='run_coinbase_scanner.sh',
        inspect_target=SYSTEM_LOG_DIR / 'run_coinbase_scanner.log',
        start_label='Run Scan',
        desired_default='auto',
    ),
    'paper_trader_v2': ComponentDef(
        id='paper_trader_v2',
        name='Paper Trader V2',
        category='trading_plane',
        kind='job',
        pid_file=SYSTEM_LOG_DIR / 'paper_trader_v2.pid',
        log_path=SYSTEM_LOG_DIR / 'paper_trader_v2.log',
        outputs=[
            PAPER_TRADES_DIR / 'open_positions_v2.json',
            PAPER_TRADES_DIR / 'trades_log_v2.json',
            PAPER_TRADES_DIR / 'paper_trader_v2_audit_summary.json',
        ],
        dependencies=['coinbase_feed', 'market_scanner'],
        notes='Consumes scanner/feed state and maintains V2 trade book.',
        start_script='run_paper_trader_v2.sh',
        inspect_target=SYSTEM_LOG_DIR / 'paper_trader_v2.log',
        start_label='Run Now',
        desired_default='auto',
    ),
    'position_manager': ComponentDef(
        id='position_manager',
        name='Position Manager',
        category='trading_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=['paper_trader_v2'],
        notes='Lifecycle/risk follow-up on open positions.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
    ),
    'main_loop': ComponentDef(
        id='main_loop',
        name='Main Loop',
        category='orchestration',
        kind='service',
        pid_file=SYSTEM_LOG_DIR / 'market_cycle_daemon.pid',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=['coinbase_feed', 'market_scanner', 'paper_trader_v2'],
        notes='Scheduler/repeating market cycle orchestrator.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        desired_default='on',
    ),
    'operator_dashboard': ComponentDef(
        id='operator_dashboard',
        name='Operator Dashboard',
        category='control_plane',
        kind='service',
        pid_file=SYSTEM_LOG_DIR / 'dashboard.pid',
        log_path=SYSTEM_LOG_DIR / 'dashboard.log',
        notes='Primary control UI.',
        start_script='run_dashboard.sh',
        desired_default='on',
    ),
    'stream_dashboard': ComponentDef(
        id='stream_dashboard',
        name='Stream Dashboard',
        category='control_plane',
        kind='service',
        pid_file=SYSTEM_LOG_DIR / 'stream_dashboard.pid',
        log_path=SYSTEM_LOG_DIR / 'stream_dashboard.log',
        notes='Condensed telemetry UI.',
        start_script='run_stream_dashboard.sh',
        desired_default='on',
    ),
    'market_broadcaster': ComponentDef(
        id='market_broadcaster',
        name='Market Broadcaster',
        category='output_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=['market_scanner'],
        notes='Builds posting/report output from scanner state.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        desired_default='auto',
    ),
    'telegram_sender': ComponentDef(
        id='telegram_sender',
        name='Telegram Sender',
        category='output_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=['market_broadcaster'],
        notes='Pushes messaging updates downstream.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
    ),
    'x_autoposter': ComponentDef(
        id='x_autoposter',
        name='X Autoposter',
        category='output_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=['market_broadcaster'],
        notes='Optional posting layer.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
    ),
    'performance_analyzer': ComponentDef(
        id='performance_analyzer',
        name='Performance Analyzer',
        category='output_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        outputs=[WORKSPACE / 'performance_reports'],
        dependencies=['paper_trader_v2'],
        notes='Generates report artifacts.',
        inspect_target=WORKSPACE / 'performance_reports',
        desired_default='auto',
    ),
    'sol_shadow_logger': ComponentDef(
        id='sol_shadow_logger',
        name='Sol Shadow Logger',
        category='output_plane',
        kind='job',
        log_path=SYSTEM_LOG_DIR / 'market_loop_cron.log',
        dependencies=[],
        notes='Sidecar logging path; should not define core stack health.',
        inspect_target=SYSTEM_LOG_DIR / 'market_loop_cron.log',
    ),
}


def components_by_category() -> dict[str, list[ComponentDef]]:
    grouped: dict[str, list[ComponentDef]] = {}
    for comp in COMPONENTS.values():
        grouped.setdefault(comp.category, []).append(comp)
    return grouped
