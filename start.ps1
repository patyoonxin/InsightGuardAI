# InsightGuardAI — Start both backend and frontend
# Run from the project root: .\start.ps1

$ErrorActionPreference = "Continue"

Write-Host "InsightGuardAI — Starting services..." -ForegroundColor Cyan

# Start FastAPI backend in a new window
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "' + $PSScriptRoot + '"; uvicorn backend.main:app --reload --port 8000' -WindowStyle Normal

Start-Sleep -Seconds 2

# Start Streamlit frontend in a new window
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "' + $PSScriptRoot + '"; streamlit run frontend/app.py --server.port 8501' -WindowStyle Normal

Write-Host ""
Write-Host "Services starting:" -ForegroundColor Green
Write-Host "  FastAPI  -> http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Streamlit -> http://localhost:8501" -ForegroundColor Yellow
Write-Host ""
Write-Host "API docs available at: http://localhost:8000/docs" -ForegroundColor Cyan
