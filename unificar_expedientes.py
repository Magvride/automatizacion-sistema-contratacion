# -*- coding: utf-8 -*-
"""
FASE 2.5 — Unificación.

Une el bloque propio (contratos del sistema Financiero UIS, ``contratos_normalizados.csv``)
con el bloque UISARD (``conciliacion_datos.csv``) usando el número de contrato como clave.

El bloque propio deja la columna ``uisard`` (y ``correo_ordenador``) vacía; esta fase las
completa cuando el contrato existe en UISARD y adjunta la ruta del expediente
(NOMBRE EXPEDIENTE, UAA, SERIE, SUB-SERIE) que la FASE 3 (Alfresco) necesita para verificar.

Este módulo es parte del flujo. Se ejecuta desde ``main.py``:
    python main.py
"""

import os
import re
import unicodedata

import pandas as pd

from config import EXTRACCION_DIR, MATRIZ_MANUAL_DIR, PATRON_ORDENADORES, ruta_ordenadores
from utils.logger import configurar_logger

logger = configurar_logger("unificacion")

# Columnas del expediente que llegan desde UISARD.
COLUMNAS_UISARD = ["NOMBRE EXPEDIENTE", "NÚMERO CONTRATO", "UAA", "SERIE", "SUBSERIE"]


def _clave_contrato(valor):
    """Extrae el número puro de contrato (último bloque de dígitos) de cualquier formato.

    Los prefijos difieren entre sistemas (Financiero: '270-2026000050'; UISARD:
    '20-2026000322'), por eso se descarta el prefijo y se conserva solo el número.
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return ""
    digitos = re.findall(r"\d+", texto)
    return digitos[-1] if digitos else ""


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte todo a texto y convierte NaNs en "" para facilitar la unión."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df.fillna("")


def _normalizar_nombre(valor) -> str:
    """Normaliza nombres para cruzar el ordenador entre ambos archivos."""
    if valor is None:
        return ""
    texto = str(valor).strip().upper()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", texto)


def _buscar_archivo_ordenadores() -> str:
    """Devuelve el archivo de ordenadores configurado por la GUI o el más reciente."""
    ruta_cfg = ruta_ordenadores()
    if ruta_cfg and os.path.isfile(ruta_cfg):
        return str(ruta_cfg)

    archivos = list(MATRIZ_MANUAL_DIR.glob(PATRON_ORDENADORES))
    if not archivos:
        return ""
    return str(max(archivos, key=lambda archivo: archivo.stat().st_mtime))


def _cargar_correos_ordenadores() -> dict:
    """Carga el mapa nombre del ordenador -> correo desde el Excel manual."""
    ruta = _buscar_archivo_ordenadores()
    if not ruta:
        logger.warning(
            "No se encontró ningún archivo %s en %s; los correos quedan vacíos.",
            PATRON_ORDENADORES,
            MATRIZ_MANUAL_DIR,
        )
        return {}

    try:
        libro = pd.read_excel(ruta, dtype=str, header=None)
    except Exception as exc:
        logger.warning("No se pudo leer el archivo de ordenadores %s: %s", ruta, exc)
        return {}

    # La cabecera puede no estar en la primera fila (el reporte exporta título y
    # fecha arriba). Se busca la fila que contiene las columnas esperadas.
    nombre_col = "ORDENADORES DE GASTO"
    correo_col = "CORREO"
    fila_cabecera = None
    indices = {}
    for i, fila in libro.iterrows():
        mapa = {_normalizar_nombre(celda): j for j, celda in enumerate(fila)}
        if nombre_col in mapa and correo_col in mapa:
            fila_cabecera = i
            indices["nombre"] = mapa[nombre_col]
            indices["correo"] = mapa[correo_col]
            break

    if fila_cabecera is None:
        logger.warning(
            "El archivo %s debe contener las columnas 'ordenadores de gasto' y 'correo'.",
            ruta,
        )
        return {}

    correos = {}
    for _, fila in libro.iloc[fila_cabecera + 1:].iterrows():
        nombre = _normalizar_nombre(fila.iloc[indices["nombre"]])
        correo = str(fila.iloc[indices["correo"]]).strip() or ""
        if nombre and correo and nombre not in correos:
            correos[nombre] = correo

    logger.info(
        "Mapa de ordenadores cargado desde %s: %d registros.",
        ruta,
        len(correos),
    )
    return correos


def _buscar_csv_propio() -> str:
    """Devuelve la ruta del CSV de contratos normalizados más reciente."""
    archivos = sorted(EXTRACCION_DIR.glob("contratos_normalizados*.csv"))
    if not archivos:
        return ""
    return str(max(archivos, key=lambda a: a.stat().st_mtime))


def unir_consolidados(ruta_base: str, df_uisard: pd.DataFrame, ruta_salida: str) -> dict:
    """Une los contratos del sistema Financiero con los datos UISARD (indicador + ruta).

    Devuelve un dict con estado: ``ruta`` (CSV generado), ``total``, ``con_uisard``,
    ``sin_uisard`` y ``encontrado`` (False si no se localizó el CSV base).
    """
    if not ruta_base or not os.path.isfile(ruta_base):
        logger.warning("No se encontró %s: no hay CSV del bloque propio para unir.", ruta_base)
        return {"ruta": "", "total": 0, "con_uisard": 0, "sin_uisard": 0, "encontrado": False}

    base = _normalizar(pd.read_csv(ruta_base, encoding="utf-8-sig", dtype=str))
    uis = _normalizar(df_uisard)

    if base.empty:
        return {"ruta": "", "total": 0, "con_uisard": 0, "sin_uisard": 0, "encontrado": False}

    base["_clave"] = base["contrato"].map(_clave_contrato)

    columnas_uis = [c for c in COLUMNAS_UISARD if c in uis.columns]
    uis_import = uis[columnas_uis].copy()
    uis_import["_clave"] = uis_import["NÚMERO CONTRATO"].map(_clave_contrato)

    merged = base.merge(uis_import, on="_clave", how="left")
    merged = merged.fillna("")

    # Completa el correo usando el archivo manual de ordenadores más reciente.
    correos_ordenadores = _cargar_correos_ordenadores()
    if "correo_ordenador" not in merged.columns:
        merged["correo_ordenador"] = ""
    if correos_ordenadores and "ordenador" in merged.columns:
        correos = merged["ordenador"].map(
            lambda nombre: correos_ordenadores.get(_normalizar_nombre(nombre), "")
        )
        encontrados = correos != ""
        merged.loc[encontrados, "correo_ordenador"] = correos[encontrados]
        logger.info(
            "Correos de ordenadores completados: %d de %d contratos.",
            int(encontrados.sum()),
            len(merged),
        )

    # Indicador de presencia en UISARD (rellena la columna que el bloque propio dejó vacía).
    if "NOMBRE EXPEDIENTE" in merged.columns:
        merged["uisard"] = merged["NOMBRE EXPEDIENTE"].map(lambda v: "SI" if str(v).strip() else "NO")
    merged.drop(columns=["_clave"], inplace=True)

    con_uisard = int((merged["uisard"] == "SI").sum())
    sin_uisard = int((merged["uisard"] == "NO").sum())

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    merged.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    logger.info(
        "Unificación: %d contratos (%d con expediente UISARD | %d sin UISARD) -> %s",
        len(merged), con_uisard, sin_uisard, ruta_salida,
    )
    return {
        "ruta": ruta_salida,
        "total": len(merged),
        "con_uisard": con_uisard,
        "sin_uisard": sin_uisard,
        "encontrado": True,
    }


def main():
    # Rechaza la ejecución directa: el flujo debe pasar por main.py.
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    import sys
    sys.exit(0)


if __name__ == "__main__":
    main()
