# -*- coding: utf-8 -*-
"""Sube la matriz de seguimiento actualizada a la carpeta de OneDrive del equipo.

La carpeta destino se resuelve en ``config.ruta_onedrive_destino()``: si el
usuario la configuró manualmente desde la GUI se respeta; si no, se detecta la
raíz de OneDrive del equipo (registro de Windows) y se usa la carpeta fija.
"""

import shutil
from pathlib import Path

from config import (
    MATRIZ_ACTUALIZADA_DIR,
    NOMBRE_MATRIZ_ACTUALIZADA,
    ruta_onedrive_destino,
)
from utils.logger import configurar_logger

logger = configurar_logger("onedrive")


def ruta_matriz_origen() -> Path:
    """Ruta de la matriz actualizada generada por ``seguimiento_p2.py``."""
    return MATRIZ_ACTUALIZADA_DIR / NOMBRE_MATRIZ_ACTUALIZADA


def subir_a_onedrive(origen: Path | None = None) -> Path:
    """Copia la matriz a la carpeta de OneDrive del equipo.

    Crea la carpeta destino si no existe y copia el archivo conservando su
    nombre. Devuelve la ruta destino. Lanza ``FileNotFoundError`` si el archivo
    origen no existe.
    """
    origen = Path(origen) if origen else ruta_matriz_origen()

    if not origen.is_file():
        raise FileNotFoundError(f"No existe la matriz actualizada: {origen}")

    destino = ruta_onedrive_destino()
    destino.mkdir(parents=True, exist_ok=True)

    ruta_destino = destino / origen.name
    shutil.copy2(origen, ruta_destino)
    logger.info("Matriz actualizada copiada a OneDrive: %s", ruta_destino)
    return ruta_destino
