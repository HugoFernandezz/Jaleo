@echo off
echo ========================================
echo   PartyFinder Backend - Iniciar
echo ========================================

cd /d "%~dp0"

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt --quiet

REM Verificar si Chromium está instalado
echo.
echo Verificando Chromium...
playwright install chromium 2>nul

REM Iniciar servidor
echo.
echo ========================================
echo   Iniciando servidor en puerto 5000
echo ========================================
python server.py

pause

