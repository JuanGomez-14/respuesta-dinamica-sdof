@echo off
REM ==========================================================================
REM  Abre la plataforma de calculo de respuesta dinamica.
REM  Doble clic en este archivo: no hay que escribir nada.
REM  La primera vez tarda un par de minutos instalando lo necesario.
REM ==========================================================================
cd /d "%~dp0"

echo ============================================================
echo  Laboratorio de Respuesta Dinamica - Universidad de Medellin
echo ============================================================
echo.

set PY=
for %%P in (py python) do (
    if not defined PY (
        %%P -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set PY=%%P
    )
)

if not defined PY (
    echo   No se encontro Python 3.10 o superior en este computador.
    echo.
    echo   Descarguelo ^(gratis^) desde:  https://www.python.org/downloads/
    echo   IMPORTANTE: marque la casilla "Add Python to PATH" al instalarlo,
    echo   y luego vuelva a dar doble clic en este archivo.
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo   Primera vez: preparando el entorno ^(tarda 1-2 minutos^)...
    %PY% -m venv .venv
    if errorlevel 1 ( echo   No se pudo crear el entorno. & pause & exit /b 1 )
    .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    if errorlevel 1 ( echo   Fallo la instalacion. Hay conexion a internet? & pause & exit /b 1 )
    echo   Entorno listo.
) else (
    .venv\Scripts\python.exe -c "import streamlit" >nul 2>&1
    if errorlevel 1 .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
)

echo.
echo   Abriendo la herramienta en el navegador...
echo   Para cerrarla: vuelva a esta ventana y presione Ctrl+C.
echo.
REM Streamlit corre headless (ver .streamlit\config.toml) para no preguntar por
REM un correo en el primer arranque; el navegador lo abrimos nosotros.
start "" /b cmd /c "timeout /t 6 >nul & start "" http://localhost:8501"
.venv\Scripts\python.exe -m streamlit run app_streamlit.py --server.headless=true
pause
