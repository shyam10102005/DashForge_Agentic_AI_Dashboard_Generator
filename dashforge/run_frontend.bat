@echo off
title DashForge - Streamlit Frontend
echo ====================================================
echo Starting DashForge Agentic Frontend (Port 8502)...
echo ====================================================
cd /d "%~dp0"
"%~dp0.venv\Scripts\streamlit.exe" run frontend\app.py --server.port 8502 --server.headless false
pause
