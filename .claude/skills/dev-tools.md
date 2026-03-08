# /dev-tools - Development Utilities

## Start Servers
```bash
# Backend (port 8000)
cd c:\dev\emai\emai-dev-03
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (port 5173)
cd c:\dev\emai\emai-dev-03\frontend
npm run dev
```
URLs: Backend http://localhost:8000, Docs http://localhost:8000/docs, Frontend http://localhost:5173

## Build for Production
```bash
cd c:\dev\emai\emai-dev-03\frontend
npm install && npm run build
```
Output: `frontend/dist/`

## Check Status
```bash
git status && git branch --show-current && git log --oneline -3
# Check servers
powershell -Command "Invoke-WebRequest -Uri 'http://localhost:8000/docs' -UseBasicParsing -TimeoutSec 3 | Select-Object StatusCode"
powershell -Command "Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 3 | Select-Object StatusCode"
# Check DB and env
powershell -Command "Test-Path 'c:\dev\emai\emai-dev-03\emai.db'"
powershell -Command "Test-Path 'c:\dev\emai\emai-dev-03\.env'"
```

## Reset Database
**Warning: Deletes all data. Dev/testing only.**
```bash
powershell -Command "Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force"
powershell -Command "Remove-Item 'c:\dev\emai\emai-dev-03\emai.db' -ErrorAction SilentlyContinue"
cd c:\dev\emai\emai-dev-03
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
