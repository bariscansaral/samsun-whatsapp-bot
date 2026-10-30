
@echo off
setlocal EnableExtensions
title Samsun Tevkil Botu - Kurulum Merkezi
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_VERSION=3.12.4"
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "INSTALLER=%TEMP%\python-3.12.4-amd64.exe"
set "PYTHON_LOG=%TEMP%\samsun_python_install.log"
set "FREE_GB="

echo ========================================================
echo          SAMSUN TEVKIL BOTU - KURULUM MERKEZI
echo ========================================================
echo.
echo Bu kurulum asagidaki islemleri gerceklestirecektir:
echo - Python kontrolu ve gerekirse kurulumu
echo - Python dijital imza kontrolu
echo - Pip kurulumu ve guncellenmesi
echo - Gerekli kutuphanelerin yuklenmesi
echo - Kurulum dogrulamasi
echo.
echo ========================================================
echo.

echo [1/6] DISK ALANI KONTROL EDILIYOR...

for /f %%A in ('powershell -NoProfile -Command "[math]::Floor(([System.IO.DriveInfo]::new($env:SystemDrive)).AvailableFreeSpace / 1GB)"') do set "FREE_GB=%%A"

if not defined FREE_GB goto DISK_KONTROL_HATASI

echo.
echo Sistem diskinde bos alan: %FREE_GB% GB
echo Minimum gerekli alan: 1 GB
echo Onerilen bos alan: 2 GB
echo.

if %FREE_GB% LSS 1 goto DISK_YETERSIZ

if %FREE_GB% LSS 2 (
    echo [UYARI] Disk alani yeterli ancak sinira yakin.
) else (
    echo [BASARILI] Disk alani yeterli.
)

echo.
echo [2/6] PYTHON KONTROL EDILIYOR...

if exist "%PYTHON_EXE%" goto PYTHON_DOGRULA

set "PYTHON_EXE="

echo [BILGI] Standart Python kurulum konumu kontrol edildi.
echo [BILGI] Diger Python kurulumlari araniyor...

where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)

if defined PYTHON_EXE goto PYTHON_DOGRULA

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i /c:"\WindowsApps\" >nul
    if errorlevel 1 if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if defined PYTHON_EXE goto PYTHON_DOGRULA

goto PYTHON_INDIR

:PYTHON_DOGRULA

if not exist "%PYTHON_EXE%" set "PYTHON_EXE="
if not defined PYTHON_EXE goto PYTHON_INDIR

"%PYTHON_EXE%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1

if errorlevel 1 (
    echo [UYARI] Bulunan Python surumu uyumlu degil.
    set "PYTHON_EXE="
    goto PYTHON_INDIR
)

echo.
echo [BASARILI] Kullanilabilir Python bulundu:
"%PYTHON_EXE%" --version
echo.

goto PYTHON_HAZIR

:PYTHON_INDIR

echo.
echo [BILGI] Uygun Python bulunamadi.
echo [BILGI] Resmi Python sitesinden 3.12.4 indirilecek.
echo.

echo Python indiriliyor...

powershell -NoProfile -Command "$ProgressPreference='Continue'; try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '%INSTALLER%' -ErrorAction Stop; exit 0 } catch { Write-Host $_; exit 1 }"

if errorlevel 1 goto INDIRME_HATASI
if not exist "%INSTALLER%" goto INDIRME_HATASI

echo.
echo [BILGI] Python kurulum dosyasi indirildi.
echo.
echo Dijital imza kontrol ediliyor...

powershell -NoProfile -Command "$s=Get-AuthenticodeSignature -LiteralPath '%INSTALLER%'; if ($s.Status -ne 'Valid') { Write-Host 'HATA: Dijital imza gecerli degil.'; exit 1 }; if ($s.SignerCertificate.Subject -notmatch 'CN\s*=\s*Python Software Foundation') { Write-Host 'HATA: Beklenmeyen yayinci.'; exit 1 }; Write-Host 'Dijital imza gecerli.'; Write-Host ('Yayinci: ' + $s.SignerCertificate.Subject); exit 0"

if errorlevel 1 goto IMZA_HATASI

echo.
echo [BILGI] Python 3.12.4 kurulumu baslatiliyor...
echo [BILGI] Kurulum gunlugu islem sonrasinda terminale yazdirilacak.
echo.

"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 /log "%PYTHON_LOG%"

if errorlevel 1 goto PYTHON_HATASI

if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto PYTHON_HATASI

set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

echo.
echo ========================================================
echo PYTHON KURULUM GUNLUGU
echo ========================================================

if exist "%PYTHON_LOG%" type "%PYTHON_LOG%"

echo.
echo ========================================================

"%PYTHON_EXE%" --version

if errorlevel 1 goto PYTHON_HATASI

:PYTHON_HAZIR

echo.
echo [3/6] PIP KONTROL EDILIYOR...

"%PYTHON_EXE%" -m ensurepip --upgrade

if errorlevel 1 goto PIP_HATASI

echo.
echo [4/6] PIP GUNCELLENIYOR...

"%PYTHON_EXE%" -m pip install --upgrade pip

if errorlevel 1 goto PIP_HATASI

echo.
echo [5/6] REQUIREMENTS.TXT KONTROL EDILIYOR...

if not exist "%~dp0requirements.txt" goto REQUIREMENTS_HATASI

echo.
echo Kutuphaneler requirements.txt dosyasina gore yukleniyor...
echo.

"%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 goto PAKET_HATASI

echo.
echo [6/6] KURULUM DOGRULANIYOR...

"%PYTHON_EXE%" -c "import selenium, webdriver_manager, customtkinter; import importlib.metadata as m; print('Selenium:',m.version('selenium')); print('webdriver-manager:',m.version('webdriver-manager')); print('customtkinter:',m.version('customtkinter')); print('Tum kutuphaneler basariyla import edildi.')"

if errorlevel 1 goto PAKET_HATASI

echo.
echo Pip bagimlilik kontrolu yapiliyor...

"%PYTHON_EXE%" -m pip check

if errorlevel 1 goto PAKET_HATASI

echo.
echo ========================================================
echo          KURULUM BASARIYLA TAMAMLANDI!
echo ========================================================
echo.
echo Python:
"%PYTHON_EXE%" --version
echo.
echo Kurulan kutuphaneler:
echo Selenium              4.51.0
echo Webdriver-manager     4.1.2
echo CustomTkinter         5.2.2
echo.
echo run.bat ile botu calistirabilirsiniz.
echo.
goto SON

:DISK_YETERSIZ
echo.
echo [HATA] DISK ALANI YETERSIZ!
echo Mevcut bos alan: %FREE_GB% GB
echo Minimum gerekli alan: 1 GB
echo Lutfen sistem diskinizde yer acin.
goto SON

:DISK_KONTROL_HATASI
echo.
echo [HATA] Disk alani kontrol edilemedi.
goto SON

:INDIRME_HATASI
echo.
echo [HATA] Python indirilemedi!
goto SON

:IMZA_HATASI
echo.
echo [HATA] Python dijital imza kontrolu basarisiz!
echo Kurulum guvenlik nedeniyle durduruldu.
goto SON

:PYTHON_HATASI
echo.
echo [HATA] Python kurulumu basarisiz!
goto SON

:PIP_HATASI
echo.
echo [HATA] Pip islemi basarisiz!
goto SON

:REQUIREMENTS_HATASI
echo.
echo [HATA] requirements.txt bulunamadi!
echo install.bat ile ayni klasorde bulunmalidir.
goto SON

:PAKET_HATASI
echo.
echo [HATA] Kutuphane kurulumu veya dogrulamasi basarisiz!
goto SON

:SON
if exist "%INSTALLER%" del "%INSTALLER%" >nul 2>&1
echo.
echo ========================================================
echo Kurulum islemi sona erdi.
echo Terminali kapatmak icin bir tusa basin.
echo ========================================================
pause >nul
