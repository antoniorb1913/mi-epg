@echo off
REM ============================================================
REM  Regenera la EPG y la sirve en la red local.
REM  Doble clic para ejecutar. Deja esta ventana abierta.
REM ============================================================

cd /d "%~dp0"
title Servidor EPG - no cerrar esta ventana

echo ============================================================
echo   1. Regenerando la guia (puede tardar un par de minutos)
echo ============================================================
echo.

python scripts\build_epg.py
if errorlevel 1 py -3 scripts\build_epg.py

echo.
echo ============================================================
echo   2. Servidor activo
echo ============================================================
echo.
echo   Descubre tu IP con:  ipconfig   (busca "IPv4")
echo.
echo   URLs para el reproductor:
echo      http://TU-IP:8765/mi-epg.xml.gz
echo      http://TU-IP:8765/mi-epg.xml
echo.
echo   Pulsa Ctrl+C para detener el servidor.
echo ============================================================
echo.

python -m http.server 8765 --bind 0.0.0.0 --directory output
if errorlevel 1 py -3 -m http.server 8765 --bind 0.0.0.0 --directory output

pause
