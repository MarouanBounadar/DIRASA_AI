@echo off
chcp 65001 >nul
echo ====================================================
echo   DIRASA AI - Creation du fichier .exe
echo ====================================================
cd /d "%~dp0"

python -m PyInstaller --noconfirm --clean --windowed ^
  --name "DIRASA_AI" ^
  --collect-all customtkinter ^
  --collect-all static_ffmpeg ^
  --collect-submodules yt_dlp ^
  --collect-submodules google.genai ^
  --hidden-import pyttsx3.drivers ^
  --hidden-import pyttsx3.drivers.sapi5 ^
  --hidden-import comtypes.stream ^
  --hidden-import win32com.client ^
  app.py

if errorlevel 1 (
  echo [ERREUR] La creation du .exe a echoue.
  pause
  exit /b 1
)

echo.
copy /Y "LISEZ-MOI_DARIJA.txt" "dist\DIRASA_AI\LISEZ-MOI_DARIJA.txt" >nul
echo [OK] Application prete : dist\DIRASA_AI\DIRASA_AI.exe
echo Pour partager : compressez le dossier dist\DIRASA_AI en .zip
pause
