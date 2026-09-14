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


def cargar_correos_ordenadores(ruta: str = "") -> dict:
    """Carga el mapa ``nombre normalizado -> correo`` desde el Excel manual.

    Si ``ruta`` es vacía se autodetecta (config GUI o el archivo más reciente).
    Devuelve un dict vacío si el archivo no existe, no se puede leer o no tiene
    las columnas esperadas.
    """
    ruta = ruta or buscar_archivo_ordenadores()
    if not ruta or not os.path.isfile(ruta):
        logger.warning(
            "No se encontró ningún archivo %s en %s; los correos quedan vacíos.",
            PATRON_ORDENADORES,
            MATRIZ_MANUAL_DIR,
        )
        return {}

    try:
        libro = pd.read_excel(ruta, dtype=str, header=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer el archivo de ordenadores %s: %s", ruta, exc)
        return {}

    # La cabecera puede no estar en la primera fila (el reporte exporta título y
    # fecha arriba). Se busca la fila que contiene las columnas esperadas.
    fila_cabecera = None
    indices = {}
    for i, fila in libro.iterrows():
        mapa = {_normalizar_columna(celda): j for j, celda in enumerate(fila)}
        if COLUMNA_NOMBRE in mapa and COLUMNA_CORREO in mapa:
            fila_cabecera = i
            indices["nombre"] = mapa[COLUMNA_NOMBRE]
            indices["correo"] = mapa[COLUMNA_CORREO]
            break

    if fila_cabecera is None:
        logger.warning(
            "El archivo %s debe contener las columnas 'ordenadores de gasto' y 'correo'.",
            ruta,
        )
        return {}

    correos = {}
    for _, fila in libro.iloc[fila_cabecera + 1:].iterrows():
        nombre = normalizar_nombre(fila.iloc[indices["nombre"]])
        correo = str(fila.iloc[indices["correo"]]).strip() or ""
        if nombre and correo and nombre not in correos:
            correos[nombre] = correo

    logger.info(
        "Mapa de ordenadores cargado desde %s: %d registros.",
        ruta,
        len(correos),
    )
    return correos
