@echo off
chcp 65001 >nul
echo Starting ReelCutter (dev mode)...

:: Проверка зависимостей
python -c "import customtkinter, cv2, moviepy, faster_whisper, vosk" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt --break-system-packages
)

:: Запуск
python -m reelcutter
pause