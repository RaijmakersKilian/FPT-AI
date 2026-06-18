@echo off
title FTP-AI Dashboard
color 0A

echo.
echo  ============================================
echo   FTP-AI - Construction Progress Dashboard
echo  ============================================
echo.

:: Move to the backend folder (relative to this .bat file)
cd /d "%~dp0backend"

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FOUT] Python niet gevonden.
    echo  Installeer Python 3.10 of hoger via https://www.python.org/downloads/
    echo  Zorg dat je "Add Python to PATH" aanvinkt tijdens de installatie.
    echo.
    pause
    exit /b 1
)

:: ── Check .env ────────────────────────────────────────────────────────────────
if not exist ".env" (
    echo  [FOUT] .env bestand niet gevonden in de backend map.
    echo  Kopieer .env.example naar .env en vul je gegevens in.
    echo.
    pause
    exit /b 1
)

:: ── Maak virtualenv aan als die nog niet bestaat ──────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo  Eerste keer opstarten - dependencies installeren...
    echo  Dit kan een minuutje duren.
    echo.
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [FOUT] Kon geen virtual environment aanmaken.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet --disable-pip-version-check
    if %errorlevel% neq 0 (
        echo  [FOUT] Installatie van packages mislukt.
        pause
        exit /b 1
    )
    echo  Dependencies geinstalleerd.
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: ── Open browser na 2 seconden ────────────────────────────────────────────────
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: ── Start de backend ──────────────────────────────────────────────────────────
echo  Dashboard wordt gestart op http://localhost:8000
echo  De browser opent automatisch.
echo.
echo  Druk Ctrl+C om te stoppen.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo  Server gestopt.
pause
