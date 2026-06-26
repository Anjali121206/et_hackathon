# Start all SentinelSafe Microservices
Write-Host "Starting SentinelSafe Distributed Architecture..." -ForegroundColor Cyan

# Start ERP Microservice (Port 8001)
Start-Process powershell -ArgumentList "-NoExit -Command `"uvicorn services.erp_service:app --port 8001 --reload`"" -WindowStyle Normal

# Start Computer Vision Microservice (Port 8002)
Start-Process powershell -ArgumentList "-NoExit -Command `"uvicorn services.cv_service:app --port 8002 --reload`"" -WindowStyle Normal

# Start Main Orchestrator (Port 8000)
Start-Process powershell -ArgumentList "-NoExit -Command `"uvicorn app.main:app --port 8000 --reload`"" -WindowStyle Normal

Write-Host "All microservices have been launched in separate windows!" -ForegroundColor Green
Write-Host "Main Dashboard available at: http://localhost:8000" -ForegroundColor Yellow
