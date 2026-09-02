"""Rutas compartidas y configuración del flujo de contratación."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _directorio_base() -> Path:
    """Carpeta donde viven los datos de entrada/salida.

    En modo compilado (PyInstaller) `__file__` queda en la carpeta temporal de
    extracción, así que se usa la carpeta del ejecutable para conservar el .env,
    los archivos/ y los logs junto al .exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _directorio_base()
ARCHIVOS_DIR = BASE_DIR / "archivos"
REPORTES_DIR = ARCHIVOS_DIR / "reportes_demo"
CONTRATOS_DIR = ARCHIVOS_DIR / "contratos_uis"
MATRIZ_MANUAL_DIR = ARCHIVOS_DIR / "matriz_manual"
MATRIZ_ACTUALIZADA_DIR = ARCHIVOS_DIR / "matriz_actualizada"
EXTRACCION_DIR = ARCHIVOS_DIR / "extraccion_csv"
RESULTADOS_DIR = ARCHIVOS_DIR / "resultados"
STORAGE_STATE_PATH = ARCHIVOS_DIR / "sesion" / "uis_storage_state.json"

load_dotenv(BASE_DIR / ".env")


def preparar_directorios() -> None:
    """Crea las carpetas de trabajo sin tocar archivos existentes."""
    for carpeta in (
        REPORTES_DIR,
        CONTRATOS_DIR,
        MATRIZ_MANUAL_DIR,
        MATRIZ_ACTUALIZADA_DIR,
        EXTRACCION_DIR,
        RESULTADOS_DIR,
        STORAGE_STATE_PATH.parent,
    ):
        carpeta.mkdir(parents=True, exist_ok=True)


def variable(nombre: str, predeterminado: str = "") -> str:
    return os.getenv(nombre, predeterminado).strip()
