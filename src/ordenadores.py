# -*- coding: utf-8 -*-
"""
Carga del mapa ``nombre del ordenador -> correo`` desde el Excel manual
``Ordenadores_*.xlsx``.

Módulo compartido por la consolidación (``src/consolidar.py``) y, de forma
transitoria, por ``src/unificar_expedientes.py``. Se aísla aquí para tener una
única fuente de verdad del parseo (la cabecera del reporte no siempre está en la
primera fila y los nombres requieren normalización de acentos/mayúsculas).
"""

import os
import re
import unicodedata

import pandas as pd

from config import MATRIZ_MANUAL_DIR, PATRON_ORDENADORES, ruta_ordenadores
from utils.logger import configurar_logger

logger = configurar_logger("ordenadores")

# Encabezados esperados en el Excel manual (se normalizan antes de comparar).
COLUMNA_NOMBRE = "ORDENADORES DE GASTO"
COLUMNA_CORREO = "CORREO"
# El reporte SEP trae además esta columna (p. ej. "Ordenadores_SEP_*.xlsx").
# Es opcional: si el archivo no la tiene, los apoyos quedan vacíos.
COLUMNA_APOYO = "CORREOS DE APOYO"

# Las celdas de apoyo mezclan nombres, saltos de línea y formatos como
# "ESCUELA X <apoyo@uis.edu.co>"; se extrae con regex en vez de separar.
_CORREO_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def extraer_correos(texto) -> list:
    """Extrae los correos de una celda libre, sin duplicados y en orden.

    Acepta separadores ``, ;`` saltos de línea y envolturas tipo
    ``Nombre <correo@x>``. Devuelve ``[]`` si no hay nada válido.
    """
    if texto is None:
        return []
    vistos = set()
    correos = []
    for encontrado in _CORREO_RE.findall(str(texto)):
        correo = encontrado.strip()
        clave = correo.casefold()
        if clave and clave not in vistos:
            vistos.add(clave)
            correos.append(correo)
    return correos


def normalizar_nombre(valor) -> str:
    """Normaliza nombres para cruzar el ordenador entre archivos (sin acentos, mayúsculas)."""
    if valor is None:
        return ""
    texto = str(valor).strip().upper()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", texto)


def _normalizar_columna(valor) -> str:
    """Igual que ``normalizar_nombre`` pero sin colapsar espacios internos."""
    if valor is None:
        return ""
    texto = str(valor).strip().upper()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return texto


def buscar_archivo_ordenadores() -> str:
    """Devuelve el archivo de ordenadores configurado por la GUI o el más reciente."""
    ruta_cfg = ruta_ordenadores()
    if ruta_cfg and os.path.isfile(ruta_cfg):
        return str(ruta_cfg)

    archivos = list(MATRIZ_MANUAL_DIR.glob(PATRON_ORDENADORES))
    if not archivos:
        return ""
    return str(max(archivos, key=lambda archivo: archivo.stat().st_mtime))


def _leer_tabla_ordenadores(ruta: str):
    """Lee el Excel como tabla cruda y localiza la fila de cabecera.

    Devuelve ``(libro, fila_cabecera, indices)`` donde ``indices`` tiene las
    claves ``nombre``, ``correo`` y, si existe, ``apoyo``. Si no hay cabecera
    válida devuelve ``(None, None, {})``.
    """
    try:
        libro = pd.read_excel(ruta, dtype=str, header=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer el archivo de ordenadores %s: %s", ruta, exc)
        return None, None, {}

    # La cabecera puede no estar en la primera fila (el reporte exporta título y
    # fecha arriba). Se busca la fila que contiene las columnas esperadas.
    for i, fila in libro.iterrows():
        mapa = {_normalizar_columna(celda): j for j, celda in enumerate(fila)}
        if COLUMNA_NOMBRE in mapa and COLUMNA_CORREO in mapa:
            indices = {
                "nombre": mapa[COLUMNA_NOMBRE],
                "correo": mapa[COLUMNA_CORREO],
            }
            if COLUMNA_APOYO in mapa:
                indices["apoyo"] = mapa[COLUMNA_APOYO]
            return libro, i, indices
    return libro, None, {}


def cargar_mapa_ordenadores(ruta: str = "") -> dict:
    """Carga el mapa ``nombre normalizado -> {correo, apoyos}``.

    Incluye la columna opcional ``CORREOS DE APOYO`` del reporte SEP: cada
    entrada es ``{"correo": str, "apoyos": [str, ...]}``. Si ``ruta`` es vacía
    se autodetecta (config GUI o el archivo más reciente). Devuelve un dict
    vacío si el archivo no existe o no tiene las columnas esperadas.
    """
    ruta = ruta or buscar_archivo_ordenadores()
    if not ruta or not os.path.isfile(ruta):
        logger.warning(
            "No se encontró ningún archivo %s en %s; los correos quedan vacíos.",
            PATRON_ORDENADORES,
            MATRIZ_MANUAL_DIR,
        )
        return {}

    libro, fila_cabecera, indices = _leer_tabla_ordenadores(ruta)
    if libro is None:
        return {}
    if fila_cabecera is None:
        logger.warning(
            "El archivo %s debe contener las columnas 'ordenadores de gasto' y 'correo'.",
            ruta,
        )
        return {}

    mapa = {}
    for _, fila in libro.iloc[fila_cabecera + 1:].iterrows():
        nombre = normalizar_nombre(fila.iloc[indices["nombre"]])
        if not nombre or nombre in mapa:
            continue
        correo = str(fila.iloc[indices["correo"]]).strip() or ""
        if not correo:
            continue
        apoyos = []
        if "apoyo" in indices:
            apoyos = extraer_correos(fila.iloc[indices["apoyo"]])
        mapa[nombre] = {"correo": correo, "apoyos": apoyos}

    logger.info(
        "Mapa de ordenadores cargado desde %s: %d registros.",
        ruta,
        len(mapa),
    )
    return mapa


def cargar_correos_apoyo(ruta: str = "") -> dict:
    """Carga el mapa ``nombre normalizado -> correos de apoyo`` ("a@x; b@y").

    Devuelve un dict vacío si el archivo no existe o no trae la columna
    ``CORREOS DE APOYO`` (el reporte SEP sí la trae).
    """
    return {
        nombre: "; ".join(entrada.get("apoyos", []))
        for nombre, entrada in cargar_mapa_ordenadores(ruta).items()
        if entrada.get("apoyos")
    }


def cargar_correos_ordenadores(ruta: str = "") -> dict:
    """Carga el mapa ``nombre normalizado -> correo`` desde el Excel manual.

    Si ``ruta`` es vacía se autodetecta (config GUI o el archivo más reciente).
    Devuelve un dict vacío si el archivo no existe, no se puede leer o no tiene
    las columnas esperadas.
    """
    return {
        nombre: entrada["correo"]
        for nombre, entrada in cargar_mapa_ordenadores(ruta).items()
    }
