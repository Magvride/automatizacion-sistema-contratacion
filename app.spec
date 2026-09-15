# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller configuration for the Windows desktop application.

Aplicación basada en MCP/REST: ya no se empaquetan Selenium, Playwright ni
Chromium. El backend legado (``--backend-alfresco selenium``) solo funciona en
entorno de desarrollo con esas dependencias instaladas.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPEC).resolve().parent

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

# PyQt6 y keyring contienen módulos y datos descubiertos dinámicamente.
for package in ("PyQt6", "keyring"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

hiddenimports.extend(collect_submodules("desktop"))

# Se excluyen los módulos legados de scraping (Selenium/Playwright): el flujo
# empaquetado usa solo el backend MCP/REST.
_LEGACY = ("uisard_extractor", "alfresco_extractor", "uis_login_p1")
hiddenimports.extend(
    collect_submodules(
        "src",
        filter=lambda name: not any(legacy in name for legacy in _LEGACY),
    )
)

analysis = Analysis(
    [str(ROOT / "desktop" / "__main__.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "selenium", "playwright", "playwright_stealth"],
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
