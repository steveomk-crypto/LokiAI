$ErrorActionPreference = 'Stop'

$Workspace = '/home/lokiai/.openclaw/workspace'

bash -lc "cd '$Workspace' && ./scripts/run_dashboard.sh"
Start-Process 'http://localhost:8500'
