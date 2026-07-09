@echo off
title Pocol (Gemma 4 Edition) - Auto Restart Runner
chcp 65001 >nul

:: --- 1. カレントディレクトリの固定 ---
:: スクリプトがどこから呼び出されても、確実に Pocol のフォルダを基準に動作させます
cd /d "%~dp0"

echo ========================================================
echo  🐶 Pocol System Startup
echo  Target: Intel N100 Mini PC (Gemma 4 E2B QAT)
echo ========================================================
echo.

:: --- 2. 必須ツールの動作確認 ---
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] パッケージマネージャー 'uv' が見つかりません。
    echo インストールされているか、環境変数が設定されているか確認してください。
    pause
    exit /b
)

:: --- 3. 初回起動時のシステム待機 ---
:: PC起動直後の自動スタートを想定し、Wi-FiとOllamaの準備が整うのを待ちます
echo [System] バックグラウンドサービス (Ollama/Wi-Fi) の準備を待機しています (30秒)...
timeout /t 30 /nobreak >nul

:: --- 4. メインループ (自動再起動システム) ---
:loop
cls
echo ========================================================
echo  🚀 Starting Pocol... [%date% %time%]
echo ========================================================
echo.

:: Pythonスクリプトの実行
uv run main.py

:: 正常終了、またはエラーでクラッシュした場合はここへ到達します
echo.
echo ========================================================
echo  ⚠️ WARNING: Pocolのプロセスが停止しました！
echo  10秒後に自動で再起動します... 
echo  (完全に停止してメンテナンスをする場合は Ctrl+C を押してください)
echo ========================================================
timeout /t 10

:: ループの先頭に戻り、Pocolを再起動します
goto loop