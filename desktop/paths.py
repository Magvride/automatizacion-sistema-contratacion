# -*- coding: utf-8 -*-
"""Rutas y configuración de arranque del paquete ``desktop``.

Debe importarse **antes** que cualquier módulo del backend (``config``,
``main``, ``utils``...), porque agrega la raíz del proyecto y ``src/`` a
``sys.path`` para que los imports históricos (``from config import ...``)
sigan funcionando tanto en modo fuente como compilado con PyInstaller.
"""

import os
import sys

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # En modo --onedir el ejecutable vive junto a los datos del usuario
    # (archivos/, logs/, .env, config_rutas.json).
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    SRC_DIR = BASE_DIR
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SRC_DIR = os.path.join(BASE_DIR, "src")
    for _ruta in (BASE_DIR, SRC_DIR):
        if _ruta not in sys.path:
            sys.path.insert(0, _ruta)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def recurso(ruta_relativa: str) -> str:
    """Devuelve la ruta absoluta de un recurso empaquetado o del repositorio.

    Con PyInstaller ``sys._MEIPASS`` apunta a la carpeta temporal de extracción;
    en modo fuente se resuelve relativo a ``BASE_DIR``.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, ruta_relativa)
    return os.path.join(BASE_DIR, ruta_relativa)


def icono_app() -> str:
    """Ruta del icono principal de la aplicación (``.ico``)."""
    return os.path.join(ASSETS_DIR, "icon.ico")
