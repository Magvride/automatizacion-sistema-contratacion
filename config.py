"""Rutas compartidas y configuración del flujo de contratación."""

import json
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
REPORTES_DIR = ARCHIVOS_DIR / "04_Contratos_Descargados_UISARD"
CONTRATOS_DIR = ARCHIVOS_DIR / "01_Contratos_Descargados"
MATRIZ_MANUAL_DIR = ARCHIVOS_DIR / "00_Datos_Raw"
MATRIZ_ACTUALIZADA_DIR = ARCHIVOS_DIR / "02_Matriz_actualizada"
EXTRACCION_DIR = ARCHIVOS_DIR / "03_Contratos_Conciliacion"
RESULTADOS_DIR = ARCHIVOS_DIR / "resultados"
STORAGE_STATE_PATH = ARCHIVOS_DIR / "sesion" / "uis_storage_state.json"

# Archivos manuales que el usuario puede seleccionar desde la GUI (rutas por defecto).
NOMBRE_MATRIZ_MANUAL = "Matriz Seguimiento Contractual UIS.xlsx"
PATRON_ORDENADORES = "Ordenadores_*.xlsx"

# Persistencia de las rutas configuradas desde la GUI.
ARCHIVO_CONFIG_RUTAS = BASE_DIR / "config_rutas.json"

load_dotenv(BASE_DIR / ".env")


def _ruta_matriz_default() -> Path:
    """Ruta por defecto de la matriz manual (la carpeta histórica)."""
    return MATRIZ_MANUAL_DIR / NOMBRE_MATRIZ_MANUAL


def _ruta_ordenadores_default() -> Path:
    """Ruta por defecto del archivo de ordenadores: el más reciente de la carpeta."""
    archivos = sorted(
        MATRIZ_MANUAL_DIR.glob(PATRON_ORDENADORES),
        key=lambda a: a.stat().st_mtime,
    )
    return archivos[-1] if archivos else (MATRIZ_MANUAL_DIR / "Ordenadores_Agosto.xlsx")


def _cargar_config_rutas() -> dict:
    """Lee el JSON de rutas configuradas. Devuelve dict vacío si no existe o falla."""
    try:
        with open(ARCHIVO_CONFIG_RUTAS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar_config_rutas(config: dict) -> None:
    """Guarda el JSON de rutas configuradas de forma atómica."""
    try:
        with open(ARCHIVO_CONFIG_RUTAS, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def ruta_matriz_manual() -> Path:
    """Ruta de la matriz manual: la configurada por la GUI o la por defecto."""
    ruta = _cargar_config_rutas().get("matriz_manual", "")
    if ruta and Path(ruta).is_file():
        return Path(ruta)
    return _ruta_matriz_default()


def ruta_ordenadores() -> Path:
    """Ruta del archivo de ordenadores: el configurado o el más reciente por defecto."""
    ruta = _cargar_config_rutas().get("ordenadores", "")
    if ruta and Path(ruta).is_file():
        return Path(ruta)
    return _ruta_ordenadores_default()


def configurar_rutas(matriz_manual: str = "", ordenadores: str = "") -> None:
    """Guarda las rutas manuales elegidas en la GUI (vacías = usar el valor por defecto)."""
    config = _cargar_config_rutas()
    config["matriz_manual"] = str(matriz_manual) if matriz_manual else ""
    config["ordenadores"] = str(ordenadores) if ordenadores else ""
    _guardar_config_rutas(config)


def restablecer_rutas() -> None:
    """Vuelve a dejar las rutas manuales en sus valores por defecto."""
    configurar_rutas("", "")


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
