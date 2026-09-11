# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller configuration for the Windows desktop application.

The browser files are downloaded by ``build_gui.ps1`` into
``build/playwright_browsers`` before this specification is evaluated.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPEC).resolve().parent
BROWSER_DIR = ROOT / "build" / "playwright_browsers"

datas = [
    (str(ROOT / "desktop" / "assets"), "desktop/assets"),
    (str(ROOT / "config_rutas.json"), "."),
]
binaries = []
hiddenimports = [
    "desktop.__main__",
    "main",
    "src",
]

# PyQt6 and Playwright contain dynamically discovered modules and support data.
for package in ("PyQt6", "playwright", "playwright_stealth"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

hiddenimports.extend(collect_submodules("desktop"))
hiddenimports.extend(collect_submodules("src"))

if not BROWSER_DIR.is_dir():
    raise SystemExit(
        "No se encontró Chromium de Playwright en "
        f"{BROWSER_DIR}. Ejecute build_gui.ps1 antes de PyInstaller."
    )

datas.append((str(BROWSER_DIR), "playwright_browsers"))

analysis = Analysis(
    [str(ROOT / "desktop" / "__main__.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "rthook_playwright.py")],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="SistemaContrataciones",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "desktop" / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SistemaContrataciones",
)
