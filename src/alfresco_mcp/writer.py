# -*- coding: utf-8 -*-
"""
Escritura de las salidas de verificación de Alfresco.

* ``06_Verificacion_Alfresco.csv`` — todos los registros (9 columnas).
* ``07_Expedientes_Faltantes.csv`` — solo los no encontrados (8 columnas, sin
  ``DESCRIPCION``).

El esquema es idéntico al de la versión Selenium para no romper las fases
posteriores (``fase_merge_alfresco``, ``resultados``, dashboard, notificación).
"""

import os

import pandas as pd

from utils.logger import configurar_logger

logger = configurar_logger("alfresco_writer")

COLUMNAS_06 = [
    "NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUB-SERIE",
    "alfresco", "cantidad_archivos",
    "MOTIVO", "EXPEDIENTE_ENCONTRADO", "DESCRIPCION",
]

COLUMNAS_07 = [c for c in COLUMNAS_06 if c != "DESCRIPCION"]


def escribir_verificacion(resultados: list, ruta_06: str, ruta_07: str) -> dict:
    """Escribe 06 y 07 a partir de la lista de resultados.

    ``resultados`` es una lista de dicts devueltos por ``verificar_contrato``.
    Devuelve ``{ruta_resumen, ruta_pendientes, total, encontrados, no_encontrados}``.
    """
    filas = [r.get("verificacion", {}) for r in resultados or []]

    os.makedirs(os.path.dirname(ruta_06) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(ruta_07) or ".", exist_ok=True)

    df_06 = pd.DataFrame(filas, columns=COLUMNAS_06)
    df_06.to_csv(ruta_06, index=False, encoding="utf-8-sig")

    pendientes = [f for f in filas if str(f.get("EXPEDIENTE_ENCONTRADO", "")).upper() == "NO"]
    df_07 = pd.DataFrame(pendientes, columns=COLUMNAS_07)
    df_07.to_csv(ruta_07, index=False, encoding="utf-8-sig")

    encontrados = sum(1 for f in filas if str(f.get("EXPEDIENTE_ENCONTRADO", "")).upper() == "SI")
    logger.info(
        "Verificación escrita: %d registros | %d encontrados | %d no encontrados -> %s",
        len(filas), encontrados, len(pendientes), ruta_06,
    )
    return {
        "ruta_resumen": ruta_06,
        "ruta_pendientes": ruta_07,
        "total": len(filas),
        "encontrados": encontrados,
        "no_encontrados": len(pendientes),
    }
