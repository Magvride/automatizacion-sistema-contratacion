@echo off
rem ============================================================
rem  Instalacion automatica en un PC nuevo (una sola vez).
rem  Instala dependencias + crea el .env + acceso directo.
rem  Despues, el cliente solo hace doble clic en el acceso.
rem ============================================================
setlocal
cd /d "%~dp0"
title Instalador - Sistema de Contratacion

echo.
echo  [1/4] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: No se encontro Python. Instala desde https://www.python.org/downloads/
    echo  Marca "Add Python to PATH" durante la instalacion y vuelve a ejecutar.
    pause
    exit /b 1
)

echo  [2/4] Instalando dependencias...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  ERROR: fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo  [3/4] Configurando .env...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    if exist ".env" (
        echo  Se creo .env con credenciales de ejemplo.
        echo  IMPORTANTE: abre .env con el Bloc de notas y completa las claves
        echo  (UISARD_USER/PASS, ALFRESCO_SHARE_PASS, UIS_LOGIN_*, etc.).
    ) else (
        echo  Aviso: no hay .env.example. Revisa que las credenciales esten en .env.
    )
) else (
    echo  .env ya existe, se mantiene.
)

echo  [4/4] Creando acceso directo en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$py=(Get-Command python.exe -ErrorAction SilentlyContinue).Source; if(!$py){Write-Host 'ERROR';
  exit 1}; $pw=Join-Path (Split-Path $py) 'pythonw.exe'; if(!(Test-Path $pw)){$pw=$py};
  $ws=New-Object -ComObject WScript.Shell; $d=[Environment]::GetFolderPath('Desktop');
  $lnk=$ws.CreateShortcut((Join-Path $d 'Sistema de Contratacion.lnk'));
  $lnk.TargetPath=$pw; $lnk.Arguments='app_gui.py'; $lnk.WorkingDirectory='%~dp0';
  $lnk.IconLocation=\"$pw,0\"; $lnk.Description='Automatizacion del sistema de contratacion';
  $lnk.Save(); Write-Host 'Acceso directo creado en el escritorio.'"
if errorlevel 1 (
    echo  Aviso: no se pudo crear el acceso directo automatico.
    echo  Hazlo manualmente; ver instrucciones en README.
)

echo.
echo  ============================================================
echo   Instalacion terminada.
echo   1. Edita .env con las credenciales (doble clic).
echo   2. Doble clic en el acceso "Sistema de Contratacion" del escritorio.
echo  ============================================================
pause
