@echo off
chcp 65001 >nul
echo Building ReelCutter...

:: Установка зависимостей
echo Installing dependencies...
pip install -r requirements.txt --break-system-packages

:: Скачивание моделей Vosk (если нет)
echo Checking Vosk models...
if not exist "reelcutter\models\vosk\vosk-model-small-ru-0.22" (
    echo Downloading Vosk Russian model...
    powershell -Command "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip' -OutFile 'vosk-ru.zip'"
    powershell -Command "Expand-Archive -Path 'vosk-ru.zip' -DestinationPath 'reelcutter\models\vosk' -Force"
    del vosk-ru.zip
)

if not exist "reelcutter\models\vosk\vosk-model-small-en-us-0.15" (
    echo Downloading Vosk English model...
    powershell -Command "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip' -OutFile 'vosk-en.zip'"
    powershell -Command "Expand-Archive -Path 'vosk-en.zip' -DestinationPath 'reelcutter\models\vosk' -Force"
    del vosk-en.zip
)

:: Сборка через PyInstaller
echo Building executable...
pyinstaller reelcutter.spec --clean --noconfirm

echo.
echo Build complete! Check dist/ReelCutter.exe
pause