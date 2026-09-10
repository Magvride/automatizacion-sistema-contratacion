# Compila la aplicación de escritorio y el instalador.
# Uso:  powershell -ExecutionPolicy Bypass -File build_gui.ps1

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "[1/4] Instalando dependencias..."
python -m pip install -r requirements.txt
python -m pip install -r requirements-gui.txt

Write-Host "[2/4] Generando icono..."
python desktop\assets\generar_icono.py

Write-Host "[3/4] Empaquetando con PyInstaller (onedir)..."
python -m PyInstaller app.spec --noconfirm --clean

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path -LiteralPath $iscc) {
    Write-Host "[4/4] Compilando instalador con Inno Setup..."
    & $iscc installer.iss
    Write-Host "Instalador generado en installer_output\"
} else {
    Write-Host "[4/4] Inno Setup 6 no encontrado."
    Write-Host "Instalalo desde https://jrsoftware.org/isdl.php y ejecuta:"
    Write-Host '  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss'
}

Write-Host "Aplicacion lista en dist\SistemaContrataciones\"
