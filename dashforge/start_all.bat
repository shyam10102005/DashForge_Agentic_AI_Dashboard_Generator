@echo off
title DashForge - Agentic AI Dashboard Generator
echo ====================================================
echo   ⚡ DashForge - Power BI & Tableau Agentic AI Suite
echo ====================================================
echo.
cd /d "%~dp0"

echo [1/2] Starting Backend API on http://localhost:8001 ...
start "DashForge Backend" cmd /k "run_backend.bat"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Streamlit Frontend on http://localhost:8502 ...
start "DashForge Frontend" cmd /k "run_frontend.bat"

echo.
echo ====================================================
echo   DashForge is now running!
echo   Frontend: http://localhost:8502
echo   Backend:  http://localhost:8001/docs
echo ====================================================
