@echo off
title Pocol - AI Dog Assistant
chcp 65001 >nul

:: --- 1. カレントディレクトリをこのバッチファイルのある場所に移動 ---
:: これにより、C:\Projects\Pocol 以外にフォルダを移動しても動くようになります
cd /d "%~dp0"

echo ========================================================
echo   Pocol System Startup
echo   Target: Intel N100 Mini PC
echo ========================================================

:: --- 2. 初回起動時のシステム待機 (Ollama/Wi-Fiの準備待ち) ---
echo.
echo [System] Waiting for background services (30s)...
timeout /t 30 /nobreak >nul

:: --- 3. メインループ (自動再起動システム) ---
:loop
cls
echo ========================================================
echo   Starting Pocol... (%date% %time%)
echo ========================================================
echo.

:: Pythonスクリプトの実行
uv run main.py

:: ここに来るのは、Botが停止(クラッシュ)した時だけ
echo.
echo ========================================================
echo   WARNING: Pocol has stopped!
echo   Restarting in 10 seconds... (Press Ctrl+C to stop)
echo ========================================================
timeout /t 10

:: ループ先頭に戻る
goto loop