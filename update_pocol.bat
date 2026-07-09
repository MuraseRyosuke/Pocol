@echo off
title Pocol - Maintenance ^& Update Tool
chcp 65001 >nul

:: --- 1. カレントディレクトリの固定 ---
cd /d "%~dp0"

echo ========================================================
echo  🐶 Pocol Maintenance ^& Update Tool
echo ========================================================
echo.

:: --- 2. データベースの自動バックアップ ---
echo [1/3] データベースのバックアップを作成中...
if exist "pocol.db" (
    :: 日付を取得してファイル名に付与 (例: pocol_backup_20260709.db)
    set BACKUP_DATE=%date:/=%
    set BACKUP_DATE=%BACKUP_DATE: =%
    copy /y "pocol.db" "pocol_backup_%BACKUP_DATE%.db" >nul
    echo   -^> バックアップ完了: pocol_backup_%BACKUP_DATE%.db
) else (
    echo   -^> pocol.db が見つかりません。(新規作成としてスキップします)
)
echo.

:: --- 3. AIモデルの更新 ---
echo [2/3] AIモデル (Ollama) を最新バージョンに更新中...
where ollama >nul 2>nul
if %errorlevel% equ 0 (
    ollama pull gemma4:e2b-it-qat
    ollama pull deepseek-r1:1.5b
) else (
    echo   [ERROR] Ollamaが見つかりません。
)
echo.

:: --- 4. Pythonライブラリの更新 ---
echo [3/3] Pythonライブラリ (uv) を最新安定版に更新中...
where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv sync --upgrade
) else (
    echo   [ERROR] uvコマンドが見つかりません。
)
echo.

echo ========================================================
echo  ✨ メンテナンスがすべて完了しました！
echo  (start_pocol.bat からPocolを再起動してあげてください)
echo ========================================================
pause