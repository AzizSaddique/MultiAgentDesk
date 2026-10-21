# start-backend.ps1
# AgentDesk FastAPI Local Backend Service Launcher

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Starting AgentDesk FastAPI Backend Service" -ForegroundColor Cyan
Write-Host "   Binding to: http://127.0.0.1:8000" -ForegroundColor DarkCyan
Write-Host "   Health Endpoint: http://127.0.0.1:8000/health" -ForegroundColor DarkCyan
Write-Host "=============================================" -ForegroundColor Cyan

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --loop none
