@echo off
:: =============================================
:: Akyel AI + OmniRoute - Windows Startup
:: Double-clique pour tout lancer automatiquement
:: =============================================

title Akyel AI - Smart Multi-LLM Assistant

echo ============================================
echo    Akyel AI - Demarrage des services
echo ============================================
echo.

:: Se placer dans le bon dossier
cd /d "%~dp0"

:: 1. Kill any existing processes
echo [1/3] Arret des anciens processus...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul
echo   ✓ Anciens processus arretes

:: 2. Start OmniRoute
echo.
echo [2/3] Demarrage d'OmniRoute (routeur intelligent)...
start /B "" npx.cmd omniroute serve --port 20128 --daemon
timeout /t 4 /nobreak >nul
echo   ✓ OmniRoute pret sur http://localhost:20128

:: 3. Start Akyel AI
echo.
echo [3/3] Demarrage d'Akyel AI...
:: Clean Python cache
if exist __pycache__ rmdir /s /q __pycache__
start /B "" python app.py
timeout /t 4 /nobreak >nul

echo.
echo ============================================
echo    ✅ TOUT EST PRET !
echo    🌐 Akyel AI  : http://localhost:7777
echo    🌐 OmniRoute : http://localhost:20128
echo    ⚡ Smart Routing: ACTIF
echo.
echo    Ferme cette fenetre pour arreter
echo ============================================

:: Garder la fenetre ouverte
pause
