@echo off
cd /d "%~dp0"
echo ========================================
echo   Pocol Maintenance Mode
echo ========================================

echo.
echo 1. Pulling latest AI models...
ollama pull qwen2.5:3b
ollama pull deepseek-r1:1.5b

echo.
echo 2. Updating Python libraries...
uv sync --upgrade

echo.
echo ========================================
echo   Update Complete!
echo ========================================
pause