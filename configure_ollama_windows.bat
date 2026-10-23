@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AyurMitra - configure local Ollama RAG

echo ============================================================
echo AyurMitra local RAG model setup
echo ============================================================
where ollama >nul 2>nul
if errorlevel 1 goto missingollama

echo Checking whether qwen2.5:3b is already downloaded...
ollama list | findstr /I /C:"qwen2.5:3b" >nul
if errorlevel 1 (
  echo This downloads a local model (approximately 2 GB; size may vary).
  echo Keep the internet connection active until the download finishes.
  ollama pull qwen2.5:3b
  if errorlevel 1 goto pullfailed
) else (
  echo Model already downloaded; reusing it.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $c=@(); if (Test-Path $p) { $c=@(Get-Content $p | Where-Object { $_ -notmatch '^AYURMITRA_OLLAMA_MODEL=' }) }; $c += 'AYURMITRA_OLLAMA_MODEL=qwen2.5:3b'; Set-Content -Path $p -Value $c -Encoding ascii"
if errorlevel 1 goto configfailed
echo.
echo SUCCESS: .env now configures AyurMitra to use qwen2.5:3b through Ollama.
echo Restart the AyurMitra website after changing this setting.
echo Test the runtime with: ollama run qwen2.5:3b
pause
exit /b 0

:missingollama
echo Ollama runtime is not available in this terminal.
echo The VS Code extension alone is not the same as the Ollama Windows runtime.
echo 1. Open https://ollama.com/download/windows
start "" "https://ollama.com/download/windows"
echo 2. Install Ollama for Windows, then close and reopen VS Code/Terminal.
echo 3. Run this file again.
pause
exit /b 1

:pullfailed
echo The model download failed. Check internet access and available disk space, then rerun this file.
pause
exit /b 1

:configfailed
echo Could not update .env. Create it manually and add: AYURMITRA_OLLAMA_MODEL=qwen2.5:3b
pause
exit /b 1
