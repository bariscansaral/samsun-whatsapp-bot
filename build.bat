@echo off
CHCP 65001 > nul
echo ==========================================
echo Samsun Tevkil Botu Paketleniyor...
echo ==========================================

:: 1. PyInstaller ile derleme yapma
pyinstaller --noconsole --onefile --name="SamsunTevkilBot" --icon=elephant.ico --collect-all selenium --add-data "bot.py;." --add-data "config.json;." gui.py

if %errorlevel% neq 0 (
    echo [HATA] Paketleme basarisiz oldu!
    pause
    exit /b %errorlevel%
)

echo.
echo [1/3] Exe ana klasöre tasiniyor...
move /y dist\SamsunTevkilBot.exe .

echo.
echo [2/3] Gecici build ve dist klasörleri siliniyor...
rmdir /s /q build
rmdir /s /q dist

echo.
echo [3/3] Spec dosyasi temizleniyor...
del /q SamsunTevkilBot.spec

echo.
echo ==========================================
echo ISLEM TAMAMLANDI! Exe ana klasörde hazir.
echo ==========================================
pause