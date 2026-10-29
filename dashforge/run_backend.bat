@echo off
title DashForge - FastAPI Backend
echo ====================================================
echo Starting DashForge Backend API (Port 8001)...
echo ====================================================
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m uvicorn backend.api:app --host 0.0.0.0 --port 8001 --reload
pause
