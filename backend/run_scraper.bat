@echo off
echo ========================================
echo   PartyFinder - Ejecutar Scraper
echo ========================================

cd /d "%~dp0"

REM Activar entorno virtual si existe
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Crear directorio data si no existe
if not exist "data" mkdir data

echo.
echo Iniciando scraping de eventos...
echo URLs a scrapear:
echo   - Luminata Disco
echo   - El Club by Odiseo
echo.

python scraper.py

echo.
echo ========================================
pause

