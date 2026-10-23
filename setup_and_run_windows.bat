@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AyurMitra - setup, dataset validation, and website

echo ============================================================
echo AyurMitra team setup
echo ============================================================
echo This script installs dependencies, attempts official dataset downloads,
echo prepares local indexes, writes a dataset audit, and launches the website.
echo Dataset files are not fabricated if a source is unavailable.
echo.

if not exist .venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  py -3.11 -m venv .venv
  if errorlevel 1 py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo [1/3] Attempting to download official source datasets...
python scripts\download_datasets.py

echo.
echo [2/3] Preparing and validating source indexes...
python scripts\prepare_datasets.py
python scripts\audit_datasets.py

findstr /B /C:"AYURMITRA_SETUP_COMPLETE=1" .env >nul 2>nul
if not errorlevel 1 goto launchwebsite

echo.
echo [3/3] Checking optional local Ollama model...
where ollama >nul 2>nul
if not errorlevel 1 (
  if exist .env (
    findstr /R /C:"^AYURMITRA_OLLAMA_MODEL=." .env >nul
    if errorlevel 1 (
      echo Ollama is installed, but AyurMitra has no model configured yet.
      choice /M "Configure the recommended local model now (download about 2 GB)"
      if errorlevel 2 goto startwebsite
      call configure_ollama_windows.bat
    )
  ) else (
    choice /M "Configure the recommended local Ollama model now (download about 2 GB)"
    if errorlevel 2 goto startwebsite
    call configure_ollama_windows.bat
  )
) else (
  echo Ollama runtime not found. The website can still run with extractive RAG.
  echo To enable local answer generation, install Ollama from https://ollama.com/download/windows
  echo Then run configure_ollama_windows.bat and restart this setup script.
)

:startwebsite
echo.
choice /M "Configure Hindi/Kannada translation now (large install; model weights download on first use)"
if not errorlevel 2 call configure_translation_windows.bat

echo AYURMITRA_SETUP_COMPLETE=1>>.env

:launchwebsite
echo Starting the website...
echo Open http://127.0.0.1:8000 in your browser.
echo Dataset readiness and next actions are shown in data\processed\dataset_audit.json.
echo Keep this window open while using the website.
echo Press Ctrl+C here to stop the server.
echo.
python -m uvicorn app.web_app:app --host 127.0.0.1 --port 8000
pause
exit /b 0

:failed
echo.
echo Setup failed. Check that Python 3.11 or 3.12 is installed and that the computer has internet access.
echo See TEAM_HANDOFF.md and docs\DATA_SOURCES.md.
pause
exit /b 1
