# -*- coding: utf-8 -*-
"""
FASE 3.5 — Reporte maestro de resultados (``03_Resultado_Final.xlsx``).

Une el consolidado ``02_Consolidado_General.csv`` (contratos
propios + UISARD, con la unión completa de los tres grupos) con la verificación
de Alfresco y resume, por contrato:

    - si está registrado en UISARD (columna ``uisard``),
    - si el expediente existe en Alfresco y cuántos archivos tiene.

El mismo archivo se actualiza "en vivo" durante la FASE 3 (Alfresco) para seguir
el avance de la verificación, y queda como insumo del envío final.

Este módulo es parte del flujo. Se ejecuta desde ``main.py``:
    python main.py
"""

import os

import pandas as pd

from utils.logger import configurar_logger
from config import RESULTADOS_DIR

logger = configurar_logger("resultados")

RUTA_RESULTADOS = str(RESULTADOS_DIR / "03_Resultado_Final.xlsx")

# Columnas que se conservan en el reporte maestro (en este orden).
COLUMNAS_SALIDA = [
    "contrato",
    "centro_costo",
    "ordenador",
    "correo_ordenador",
    "origen",
    "uisard",
    "NOMBRE EXPEDIENTE",
    "UAA",
    "SERIE",
    "SUBSERIE",
    "alfresco",
    "cantidad_archivos",
    "estado",
]


def _normalizar(df) -> pd.DataFrame:
    """Convierte a texto, rellena vacíos y garantiza que sea un DataFrame."""
    if df is None:
        return pd.DataFrame()
    df = pd.DataFrame(df)
    if df.empty:
        return df
    df = df.fillna("").copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


def _estado(uisard, alfresco) -> str:
    """Resumen legible de la situación de un contrato."""
    if str(uisard).strip().upper() != "SI":
        return "NO ESTA EN UISARD"
    estado_alf = str(alfresco).strip().upper()
    if estado_alf == "SI":
        return "EN UISARD - CON ARCHIVOS"
    if estado_alf == "NO":
        return "EN UISARD - SIN ARCHIVOS"
    return "EN UISARD - PENDIENTE"


def construir_resultados(consolidado, verificacion=None) -> pd.DataFrame:
    """Arma el reporte maestro a partir del consolidado 02 y la verificación.

    ``verificacion`` es opcional: si se pasa (lista de dicts o DataFrame con
    ``NOMBRE EXPEDIENTE``/``alfresco``/``cantidad_archivos``) se usa para
    refrescar el estado de Alfresco; si es ``None`` se respetan las columnas
    ``alfresco``/``cantidad_archivos`` que ya traiga el consolidado.
    """
    cons = _normalizar(consolidado)

    if verificacion is not None:
        ver = _normalizar(verificacion)
        if (
            not ver.empty
            and "NOMBRE EXPEDIENTE" in ver.columns
            and "NOMBRE EXPEDIENTE" in cons.columns
        ):
            cons = cons.drop(
                columns=[c for c in ("alfresco", "cantidad_archivos") if c in cons.columns],
                errors="ignore",
            )
            columnas_ver = [
                c for c in ("NOMBRE EXPEDIENTE", "alfresco", "cantidad_archivos")
                if c in ver.columns
            ]
            ver = ver[columnas_ver].drop_duplicates(subset=["NOMBRE EXPEDIENTE"])
            cons = cons.merge(ver, on="NOMBRE EXPEDIENTE", how="left")

    if cons.empty:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)

    for col in ("uisard", "alfresco", "cantidad_archivos"):
        if col not in cons.columns:
            cons[col] = ""
        cons[col] = cons[col].fillna("")

    cons["estado"] = [_estado(u, a) for u, a in zip(cons["uisard"], cons["alfresco"])]

    for col in COLUMNAS_SALIDA:
        if col not in cons.columns:
            cons[col] = ""
    return cons[COLUMNAS_SALIDA]


def guardar_resultados(df: pd.DataFrame, ruta: str = RUTA_RESULTADOS) -> str:
    """Guarda el reporte maestro en Excel. Lanza ``PermissionError`` si está abierto."""
    ruta = str(ruta)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    df.to_excel(ruta, index=False, engine="openpyxl")
    return ruta


def generar_reporte(consolidado, verificacion=None, ruta: str = RUTA_RESULTADOS) -> pd.DataFrame:
    """Construye y guarda el reporte maestro. Devuelve el DataFrame resultante."""
    df = construir_resultados(consolidado, verificacion)
    try:
        guardar_resultados(df, ruta)
        logger.info("[OK] Reporte maestro guardado: %s (%d filas)", ruta, len(df))
    except PermissionError:
        logger.warning("No se pudo guardar %s (archivo abierto en Excel).", ruta)
    return df


def main():
    # Rechaza la ejecución directa: el flujo debe pasar por main.py.
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    import sys
    sys.exit(0)


if __name__ == "__main__":
    main()
