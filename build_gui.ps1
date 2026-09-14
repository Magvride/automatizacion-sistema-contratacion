# Compila la aplicación de escritorio y el instalador Windows.
# Uso: powershell -ExecutionPolicy Bypass -File build_gui.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".build-venv"
$python = Join-Path $venv "Scripts\python.exe"
$distPath = Join-Path $root "dist"
$workPath = Join-Path $root "build\pyinstaller"
$updaterWorkPath = Join-Path $workPath "updater"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 no está instalado en el equipo usado para COMPILAR el instalador."
}

if (-not (Test-Path -LiteralPath $venv)) {
    Write-Host "[1/4] Creando entorno aislado de compilación..."
    & python -m venv $venv
} else {
    Write-Host "[1/4] Reutilizando entorno de compilación..."
}

Write-Host "[2/4] Instalando requirements de ejecución y GUI..."
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "requirements.txt")
& $python -m pip install -r (Join-Path $root "requirements-gui.txt")

Write-Host "[3/4] Empaquetando la GUI con PyInstaller..."
& $python (Join-Path $root "desktop\assets\generar_icono.py")
& $python -m PyInstaller (Join-Path $root "app.spec") --noconfirm --clean --distpath $distPath --workpath $workPath

$updaterOutput = Join-Path $distPath "SistemaContrataciones\updater.exe"
Write-Host "[4/5] Empaquetando el actualizador externo..."
New-Item -ItemType Directory -Path $updaterWorkPath -Force | Out-Null
& $python -m PyInstaller (Join-Path $root "desktop\updater.py") --noconfirm --clean --onefile --noconsole --name updater --distpath (Join-Path $distPath "SistemaContrataciones") --workpath $updaterWorkPath --specpath $updaterWorkPath
if (-not (Test-Path -LiteralPath $updaterOutput)) {
    throw "PyInstaller no generó el actualizador esperado: $updaterOutput"
}

$exe = Join-Path $distPath "SistemaContrataciones\SistemaContrataciones.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "PyInstaller no generó el ejecutable esperado: $exe"
}

$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 no está instalado. Instálelo desde https://jrsoftware.org/isdl.php y vuelva a ejecutar este script."
}

Write-Host "[5/5] Generando instalador .exe..."
$versionText = Get-Content -LiteralPath (Join-Path $root "desktop\__init__.py") -Raw
if ($versionText -notmatch '__version__\s*=\s*["'']([^"'']+)["'']') {
    throw "No se pudo obtener la versión desde desktop\__init__.py"
}
$appVersion = $Matches[1]
& $iscc "/DMyAppVersion=$appVersion" (Join-Path $root "installer.iss")
Write-Host "[4/4] Generando instalador .exe..."
& $iscc (Join-Path $root "installer.iss")
Write-Host "Instalador generado en installer_output\"
