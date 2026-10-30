@echo off
setlocal EnableExtensions
title Samsun Tevkil Botu - Çalıştırma Paneli
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   SAMSUN TEVKIL BOTU - ÇALIŞTIRMA PANELİ
echo ========================================================
echo.

:: 1. DEBUG MODU SEÇİMİ (E/H)
:DEBUG_SOR
set "debug_secim="
echo [BİLGİ] Debug Modu: Açık (E) seçilirse, bot kendi attığın 
echo         mesajlara da yanıt verir (Test ve geliştirme içindir).
set /p "debug_secim=Debug Modu aktif olsun mu? [E: Evet / H: Hayır]: "

if "%debug_secim%"=="" goto DEBUG_HATA

if /i "%debug_secim:~0,1%"=="E" (
    set "DEBUG_MODU=True"
    echo ---> Debug Modu: AÇIK
    goto DEVAM_1
) 
if /i "%debug_secim:~0,1%"=="H" (
    set "DEBUG_MODU=False"
    echo ---> Debug Modu: KAPALI
    goto DEVAM_1
)

:DEBUG_HATA
echo [HATA] Lütfen sadece 'E' veya 'H' harfi girin!
echo.
goto DEBUG_SOR

:DEVAM_1
echo.
echo --------------------------------------------------------
echo.

:: 2. OTOMATİK GÖNDERİM SEÇİMİ (E/H)
:GONDER_SOR
set "gonder_secim="
set /p "gonder_secim=Otomatik Gönderim aktif olsun mu? [E: Evet (Mesaj atar) / H: Hayır (Sadece loglar)] : "

if "%gonder_secim%"=="" goto GONDER_HATA

if /i "%gonder_secim:~0,1%"=="E" (
    set "OTOMATIK_GONDER=True"
    echo ---> Otomatik Gönderim: AÇIK
    goto DEVAM_2
) 
if /i "%gonder_secim:~0,1%"=="H" (
    set "OTOMATIK_GONDER=False"
    echo ---> Otomatik Gönderim: KAPALI (Simülasyon)
    goto DEVAM_2
)

:GONDER_HATA
echo [HATA] Lütfen sadece 'E' veya 'H' harfi girin!
echo.
goto GONDER_SOR

:DEVAM_2
echo.
echo --------------------------------------------------------
echo.

:: 3. ÖZEL YANIT MESAJI GİRİŞİ
echo [BİLGİ] Botun göndereceği yanıt mesajını belirleyin.
echo         Boş bırakıp Enter'a basarsanız varsayılan mesaj kullanılır:
echo         "ben yardımcı olabilirim"
set /p "YANIT_MESAJI=Özel Yanıt Mesajı (Boş bırakılabilir): "

if "%YANIT_MESAJI%"=="" (
    set "YANIT_MESAJI=ben yardımcı olabilirim"
    echo ---> Varsayılan Yanıt Mesajı Kullanılacak.
) else (
    echo ---> Özel Yanıt Mesajı Ayarlandı: "%YANIT_MESAJI%"
)

echo.
echo ========================================================
echo [BİLGİ] Bot başlatılıyor. Loglar aşağıya akacaktır...
echo ========================================================
echo.

:: OTOMATİK PYTHON BULUCU
set "PYTHON_EXE="

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i /c:"\\WindowsApps\\" >nul
    if errorlevel 1 if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

if not defined PYTHON_EXE set "PYTHON_EXE=python"

"%PYTHON_EXE%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Sistemde geçerli bir Python bulunamadı!
    echo [BİLGİ] Lütfen önce 'install.bat' dosyasını çalıştırın.
    goto SON
)

:: bot.py içindeki os.environ isimleriyle birebir eşleşen değişkenleri aktarıyoruz
set "DEBUG_MODU=%DEBUG_MODU%"
set "OTOMATIK_GONDER=%OTOMATIK_GONDER%"
set "YANIT_MESAJI=%YANIT_MESAJI%"

"%PYTHON_EXE%" bot.py

echo.
echo ========================================================
echo [UYARI] Program sonlandırıldı.
echo ========================================================

:SON
echo.
pause