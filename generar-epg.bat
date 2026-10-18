@echo off
REM ============================================================
REM  Genera la EPG. Doble clic para ejecutar.
REM  Si Python no esta en el PATH, cambia la ruta de abajo.
REM ============================================================

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python scripts\build_epg.py %*
) else (
    py -3 scripts\build_epg.py %*
)

echo.
echo ============================================
echo  Listo. Pulsa una tecla para cerrar.
echo ============================================
pause >nul
