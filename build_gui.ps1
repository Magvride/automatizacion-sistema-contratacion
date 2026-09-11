# Compila la aplicación de escritorio y el instalador Windows.
# Uso: powershell -ExecutionPolicy Bypass -File build_gui.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".build-venv"
$python = Join-Path $venv "Scripts\python.exe"
$playwright = Join-Path $venv "Scripts\playwright.exe"
$browserPath = Join-Path $root "build\playwright_browsers"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 no está instalado en el equipo usado para COMPILAR el instalador."
}

if (-not (Test-Path -LiteralPath $venv)) {
    Write-Host "[1/5] Creando entorno aislado de compilación..."
    & python -m venv $venv
} else {
    Write-Host "[1/5] Reutilizando entorno de compilación..."
}

Write-Host "[2/5] Instalando requirements de ejecución y GUI..."
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "requirements.txt")
& $python -m pip install -r (Join-Path $root "requirements-gui.txt")

Write-Host "[3/5] Descargando Chromium de Playwright..."
$env:PLAYWRIGHT_BROWSERS_PATH = $browserPath
New-Item -ItemType Directory -Path $browserPath -Force | Out-Null
& $playwright install chromium

Write-Host "[4/5] Empaquetando la GUI con PyInstaller..."
& $python (Join-Path $root "desktop\assets\generar_icono.py")
& $python -m PyInstaller (Join-Path $root "app.spec") --noconfirm --clean --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build\pyinstaller")

$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 no está instalado. Instálelo desde https://jrsoftware.org/isdl.php y vuelva a ejecutar este script."
}

Write-Host "[5/5] Generando instalador .exe..."
& $iscc (Join-Path $root "installer.iss")
Write-Host "Instalador generado en installer_output\"
