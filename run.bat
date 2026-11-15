@echo off
title DIRASA AI - Convertisseur de Seances en Cours PDF
echo ====================================================
echo   DIRASA AI - Demarrage de l'Application Desktop...
echo ====================================================
echo.
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERREUR] Impossible de lancer l'application. Verifiez votre installation Python.
    pause
)
