# start-backend.ps1
# AgentDesk FastAPI Local Backend Service Launcher

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Starting AgentDesk FastAPI Backend Service" -ForegroundColor Cyan
Write-Host "   Binding to: http://127.0.0.1:8000" -ForegroundColor DarkCyan
Write-Host "   Health Endpoint: http://127.0.0.1:8000/health" -ForegroundColor DarkCyan
Write-Host "=============================================" -ForegroundColor Cyan

# Load root .env into process environment if present
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "   Loading configuration from root .env..." -ForegroundColor DarkCyan
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line -split "=", 2
            $key = $parts[0].Trim()
            $val = $parts[1].Trim()
            # If quoted, strip matching quotes; if unquoted, strip trailing comment
            if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                $val = $val.Substring(1, $val.Length - 2)
            } elseif ($val.Contains(" #")) {
                $val = ($val -split " #", 2)[0].Trim()
            }
            if ($key) {
                [System.Environment]::SetEnvironmentVariable($key, $val, [System.EnvironmentVariableTarget]::Process)
            }
        }
    }
}

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --loop none

