@echo off
rem ============================================================
rem  Genera el ejecutable autónomo SistemaContratacion.exe.
rem  Requiere: python -m pip install pyinstaller
rem ============================================================
setlocal
cd /d "%~dp0"

python -m pip install pyinstaller --quiet

python -m PyInstaller --clean --noconfirm --onefile --windowed --name SistemaContratacion ^
  --collect-all playwright ^
  --collect-all playwright_stealth ^
  --hidden-import main ^
  --hidden-import uis_login_p1 ^
  --hidden-import seguimiento_p2 ^
  --hidden-import extraccion_p21 ^
  --hidden-import uisard_extractor ^
  --hidden-import conciliacion_datos ^
  --hidden-import unificar_expedientes ^
  --hidden-import alfresco_extractor ^
  --hidden-import notificar_uisard ^
  --hidden-import utils ^
  --hidden-import utils.logger ^
  --hidden-import utils.limpieza ^
  --hidden-import config ^
  app_gui.py

if errorlevel 1 (
    echo  ERROR: fallo la compilacion.
    pause
    exit /b 1
)

echo.
echo  Listo: dist\SistemaContratacion.exe
echo  En el PC destino, coloca el .env (credendaiales) junto al .exe.
pause
