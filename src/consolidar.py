# -*- coding: utf-8 -*-
"""
FASE 2 (nueva) — Consolidación sin UISARD.

Construye ``02_Consolidado_General.csv`` a partir del **bloque propio** (solo
nuevas versiones: ``contratos_normalizados.csv``) y el mapa de correos de los
ordenadores (Excel manual).

A diferencia de la versión anterior (``conciliacion_datos`` +
``unificar_expedientes``), este módulo **no consume reportes UISARD**. El nombre
real de la carpeta del expediente (``NOMBRE EXPEDIENTE``) y su ruta
(``UAA/SERIE/SUBSERIE``) se dejan vacíos aquí y los rellena la fase de
verificación en Alfresco (``src/alfresco_mcp``), que es quien consulta el
repositorio.

Esquema de salida (compatible con ``fase_merge_alfresco``/``resultados``)::

    contrato, centro_costo, ordenador, correo_ordenador, origen, uisard,
    NOMBRE EXPEDIENTE, UAA, SERIE, SUBSERIE, alfresco, cantidad_archivos

Este módulo es parte del flujo. Se ejecuta desde ``main.py``.
"""

import os

import pandas as pd

from config import CONTRATOS_DIR, EXTRACCION_DIR
from nuevas_versiones import enriquecer, leer_nuevas_versiones
from ordenadores import cargar_correos_ordenadores, normalizar_nombre
from utils.logger import configurar_logger

logger = configurar_logger("consolidacion")

# Campos que se extraen del reporte de nuevas versiones.
CAMPOS_NUEVAS_VERSIONES = [
    "tipo",
    "unidad",
    "contratista",
    "valor",
    "total_pagado",
    "fecha_contrato",
    "fecha_inicio",
    "fecha_fin",
    "duracion",
    "estado_contrato",
    "modalidad",
    "objeto",
    "supervisor",
]

# Columnas del consolidado 02, en orden.
COLUMNAS_CONSOLIDADO = [
    "contrato",
    "centro_costo",
    "ordenador",
    "correo_ordenador",
    *CAMPOS_NUEVAS_VERSIONES,
    "origen",
    "uisard",
    "NOMBRE EXPEDIENTE",
    "UAA",
    "SERIE",
    "SUBSERIE",
    "alfresco",
    "cantidad_archivos",
]

# Columnas que el bloque propio ya trae y que se conservan tal cual.
COLUMNAS_BASE = ["contrato", "centro_costo", "ordenador"]

# Origen de todas las filas cuando el flujo es solo nuevas versiones.
ORIGEN_NUEVAS_VERSIONES = "NUEVAS VERSIONES"


def construir_consolidado_desde_excel(
    ruta_excel: str,
    ruta_salida: str,
    correos: dict = None,
) -> dict:
    """Construye el consolidado directamente desde el Excel cargado por el usuario."""
    from nuevas_versiones import leer_nuevas_versiones

    datos = leer_nuevas_versiones(ruta_excel)
    if not datos:
        return {"ruta": "", "total": 0, "con_correo": 0, "encontrado": False}

    filas = []
    vistos = set()
    for numero, registro in datos.items():
        contrato = str(registro.get("contrato", "")).strip() or str(numero).strip()
        if contrato in vistos:
            continue
        vistos.add(contrato)
        filas.append({"contrato": contrato, **registro})
    base = pd.DataFrame(filas)
    for col in COLUMNAS_BASE:
        if col not in base.columns:
            base[col] = ""
    if correos is None:
        correos = cargar_correos_ordenadores()
    base["correo_ordenador"] = base.get("correo_ordenador", "")
    if correos:
        mapeados = base["ordenador"].map(
            lambda nombre: correos.get(normalizar_nombre(nombre), "")
        )
        base.loc[mapeados != "", "correo_ordenador"] = mapeados[mapeados != ""]

    for campo in CAMPOS_NUEVAS_VERSIONES:
        if campo not in base.columns:
            base[campo] = ""
    base["origen"] = ORIGEN_NUEVAS_VERSIONES
    base["uisard"] = ""
    for col in ("NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUBSERIE", "alfresco", "cantidad_archivos"):
        base[col] = ""

    consolidado = _normalizar(base[COLUMNAS_CONSOLIDADO])
    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    consolidado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    con_correo = int((consolidado["correo_ordenador"] != "").sum())
    return {
        "ruta": ruta_salida,
        "total": len(consolidado),
        "con_correo": con_correo,
        "encontrado": True,
    }


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte todo a texto y reemplaza NaNs por "" para facilitar el manejo."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df.fillna("")


def buscar_csv_normalizados() -> str:
    """Devuelve la ruta del CSV de contratos normalizados más reciente."""
    archivos = sorted(EXTRACCION_DIR.glob("contratos_normalizados*.csv"))
    if not archivos:
        return ""
    return str(max(archivos, key=lambda a: a.stat().st_mtime))


def buscar_nuevas_versiones() -> str:
    """Devuelve el reporte de nuevas versiones más reciente."""
    archivos = sorted(CONTRATOS_DIR.glob("contratos_*.xlsx"))
    if not archivos:
        return ""
    return str(max(archivos, key=lambda a: a.stat().st_mtime))


def construir_consolidado(
    ruta_normalizados: str,
    ruta_salida: str,
    correos: dict = None,
) -> dict:
    """Construye el consolidado 02 (solo nuevas versiones) y lo guarda en CSV.

    Devuelve ``{ruta, total, con_correo, encontrado}``. ``encontrado`` es ``False``
    cuando no hay CSV del bloque propio o está vacío (el llamador decide si aborta).
    """
    if not ruta_normalizados or not os.path.isfile(ruta_normalizados):
        logger.warning("No se encontró el CSV del bloque propio: %s", ruta_normalizados)
        return {"ruta": "", "total": 0, "con_correo": 0, "encontrado": False}

    base = _normalizar(pd.read_csv(ruta_normalizados, encoding="utf-8-sig", dtype=str))
    if base.empty:
        logger.warning("El CSV del bloque propio está vacío: %s", ruta_normalizados)
        return {"ruta": "", "total": 0, "con_correo": 0, "encontrado": False}

    if "contrato" not in base.columns:
        logger.error(
            "El CSV %s no tiene la columna 'contrato' (columnas: %s).",
            ruta_normalizados,
            list(base.columns),
        )
        return {"ruta": "", "total": 0, "con_correo": 0, "encontrado": False}

    for col in COLUMNAS_BASE:
        if col not in base.columns:
            base[col] = ""

    # Enriquecer con la información del reporte de nuevas versiones
    # (fechas, valor, contratista, unidad, estado, supervisor...).
    ruta_nuevas = buscar_nuevas_versiones()
    if ruta_nuevas:
        base = enriquecer(base, leer_nuevas_versiones(ruta_nuevas))
    for campo in CAMPOS_NUEVAS_VERSIONES:
        if campo not in base.columns:
            base[campo] = ""

    # El correo del ordenador se completa con el Excel manual (nuevas versiones).
    if correos is None:
        correos = cargar_correos_ordenadores()
    if "correo_ordenador" not in base.columns:
        base["correo_ordenador"] = ""
    if correos and "ordenador" in base.columns:
        mapeados = base["ordenador"].map(
            lambda nombre: correos.get(normalizar_nombre(nombre), "")
        )
        encontrados = mapeados != ""
        base.loc[encontrados, "correo_ordenador"] = mapeados[encontrados]
        logger.info(
            "Correos de ordenadores completados: %d de %d contratos.",
            int(encontrados.sum()),
            len(base),
        )

    # Columnas que rellenará la fase Alfresco MCP (o que quedan fijas sin UISARD).
    base["origen"] = ORIGEN_NUEVAS_VERSIONES
    base["uisard"] = ""
    for col in ("NOMBRE EXPEDIENTE", "UAA", "SERIE", "SUBSERIE", "alfresco", "cantidad_archivos"):
        base[col] = ""

    consolidado = base[COLUMNAS_CONSOLIDADO]

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    consolidado.to_csv(ruta_salida, index=False, encoding="utf-8-sig")

    con_correo = int((consolidado["correo_ordenador"].astype(str).str.strip() != "").sum())
    logger.info(
        "Consolidado 02 (solo nuevas versiones): %d contratos | %d con correo -> %s",
        len(consolidado),
        con_correo,
        ruta_salida,
    )
    return {
        "ruta": ruta_salida,
        "total": len(consolidado),
        "con_correo": con_correo,
        "encontrado": True,
    }


def main():
    # Rechaza la ejecución directa: el flujo debe pasar por main.py.
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    import sys
    sys.exit(0)


if __name__ == "__main__":
    main()
