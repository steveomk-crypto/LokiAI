from nicegui import ui


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
                padding: 0.2rem 0;
                border-bottom: 1px solid rgba(255,255,255,0.04);
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
