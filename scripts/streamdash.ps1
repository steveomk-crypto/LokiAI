$ErrorActionPreference = 'Stop'

$Workspace = '/home/lokiai/.openclaw/workspace'

bash -lc "cd '$Workspace' && ./scripts/run_stream_dashboard.sh"
Start-Process 'http://localhost:8501'
