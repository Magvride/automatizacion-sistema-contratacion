# -*- coding: utf-8 -*-
"""
FASE 2 — Conciliación.

Concatena todos los reportes por serie de ``archivos/04_Contratos_Descargados_UISARD/`` en un único CSV
con columnas estandarizadas, que luego consume la FASE 3 (Alfresco):

    NOMBRE EXPEDIENTE | NÚMERO CONTRATO | UAA | SERIE | SUBSERIE

Este módulo es parte del flujo. Se ejecuta desde ``main.py``:
    python main.py
"""

import os
import re
import sys
import unicodedata
import csv

import openpyxl
import pandas as pd

from utils.logger import configurar_logger
from config import REPORTES_DIR, RESULTADOS_DIR

logger = configurar_logger("conciliacion")

RUTA_REPORTES = str(REPORTES_DIR)
RUTA_SALIDA = str(RESULTADOS_DIR / "01_Contratos_en_UISARD.csv")

COLUMNAS_DESEADAS = ["NOMBRE EXPEDIENTE", "NÚMERO CONTRATO", "UAA", "SERIE", "SUBSERIE"]

# UISARD cambió los encabezados del reporte de expedientes. La aplicación debe
# conservar un esquema interno estable, independientemente de la versión del
# Excel que se descargue.
ALIAS_COLUMNAS = {
    "NOMBRE EXPEDIENTE": (
        "NOMBRE EXPEDIENTE",
        "NOMBRE DEL EXPEDIENTE",
        "NOMBRE",
        "EXPEDIENTE",
    ),
    "NÚMERO CONTRATO": (
        "NÚMERO CONTRATO",
        "NUMERO CONTRATO",
        "NOMBRE CONTRATO",
        "CONTRATO",
    ),
    "UAA": (
        "UAA",
        "CÓDIGO UAA",
        "CODIGO UAA",
        "UNIDAD ACADÉMICO-ADMINISTRATIVA",
        "UNIDAD ACADEMICO-ADMINISTRATIVA",
        "UNIDAD ACADÉMICO ADMINISTRATIVA",
        "UNIDAD ACADEMICO ADMINISTRATIVA",
    ),
    "SERIE": ("SERIE",),
    "SUBSERIE": ("SUBSERIE", "SUB-SERIE", "SUB SERIE"),
}

# Archivos que no son reportes por serie (consolidados intermedios, bloqueados, etc.)
ARCHIVOS_EXCLUIDOS = ("consolidado", "~", ".~lock")


def normalizar(texto):
    """Ignora acentos y mayúsculas para comparar nombres de columnas."""
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.upper().strip()


def texto_libre(valor):
    """Extrae el valor visible de una celda.

    Si la celda contiene una fórmula HYPERLINK('url','texto'), devuelve 'texto';
    en caso contrario devuelve el valor plano de la celda.
    """
    if valor is None:
        return ""
    if isinstance(valor, str) and valor.startswith("="):
        coincidencia = re.match(r'^=\s*HYPERLINK\s*\([^,]*,\s*"(.*)"\s*\)\s*$', valor, re.I | re.S)
        if coincidencia:
            return coincidencia.group(1)
        return ""
    return str(valor)


def _indices_columnas(encabezados):
    """Relaciona encabezados del reporte con las columnas internas."""
    disponibles = {}
    for indice, encabezado in enumerate(encabezados):
        nombre = normalizar(encabezado)
        for deseada in COLUMNAS_DESEADAS:
            if nombre in {normalizar(alias) for alias in ALIAS_COLUMNAS[deseada]}:
                disponibles[deseada] = indice
                break
    return disponibles


def leer_reporte(ruta):
    """Lee un reporte (xlsx/xls/csv) y devuelve un DataFrame con COLUMNAS_DESEADAS."""
    extension = os.path.splitext(ruta)[1].lower()
    if extension == ".csv":
        df = pd.read_csv(ruta, dtype=str)
        columnas = {normalizar(c): c for c in df.columns}
        resultado = pd.DataFrame()
        for deseada in COLUMNAS_DESEADAS:
            origen = next(
                (columnas.get(normalizar(alias)) for alias in ALIAS_COLUMNAS[deseada]
                 if normalizar(alias) in columnas),
                None,
            )
            resultado[deseada] = df[origen] if origen else ""
        return resultado

    libro = openpyxl.load_workbook(ruta, data_only=False)
    hoja = libro.active

    matriz = []
    for fila in hoja.iter_rows():
        matriz.append([texto_libre(celda.value) for celda in fila])

    fila_encabezado = None
    for indice, fila in enumerate(matriz):
        if _indices_columnas(fila):
            fila_encabezado = indice
            break
    if fila_encabezado is None:
        logger.debug("Sin encabezado reconocible en: %s", os.path.basename(ruta))
        return pd.DataFrame()

    encabezados = matriz[fila_encabezado]
    indices = _indices_columnas(encabezados)

    filas = []
    for fila in matriz[fila_encabezado + 1:]:
        if not any(str(c).strip() for c in fila):
            continue
        filas.append({deseada: (fila[idx] if idx < len(fila) else "") for deseada, idx in indices.items()})

    return pd.DataFrame(filas, columns=COLUMNAS_DESEADAS)


def es_reporte(archivo: str) -> bool:
    """True si el archivo es un reporte por serie válido (no un consolidado/auxiliar)."""
    if not archivo.lower().endswith((".xlsx", ".xls", ".csv")):
        return False
    return not any(m in archivo.lower() for m in ARCHIVOS_EXCLUIDOS)


def generar_consolidado(ruta_reportes: str = None, ruta_salida: str = None) -> pd.DataFrame:
    """Concatena los reportes de ``ruta_reportes`` y guarda el CSV consolidado.

    Devuelve el DataFrame consolidado (vacío si no hay reportes con datos).
    """
    ruta_reportes = ruta_reportes or RUTA_REPORTES
    ruta_salida = ruta_salida or RUTA_SALIDA

    if not os.path.isdir(ruta_reportes):
        logger.error("No existe la carpeta de reportes: %s", ruta_reportes)
        return pd.DataFrame()

    reportes = []
    for archivo in sorted(os.listdir(ruta_reportes)):
        if not es_reporte(archivo):
            continue
        ruta = os.path.join(ruta_reportes, archivo)
        df = leer_reporte(ruta)
        if not df.empty:
            reportes.append(df)
            logger.info("[+] %s: %d filas", archivo, len(df))

    if not reportes:
        logger.warning("No se encontraron reportes con datos en: %s", ruta_reportes)
        return pd.DataFrame()

    consolidado = pd.concat(reportes, ignore_index=True)
    consolidado = consolidado.fillna("")

    if "NOMBRE EXPEDIENTE" in consolidado.columns:
        antes = len(consolidado)
        consolidado = consolidado[consolidado["NOMBRE EXPEDIENTE"].astype(str).str.strip() != ""]
        logger.info("Filtradas filas sin NOMBRE EXPEDIENTE: %d -> %d", antes, len(consolidado))

    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    consolidado.to_csv(ruta_salida, index=False, encoding="utf-8-sig", sep=",", quoting=csv.QUOTE_MINIMAL)
    logger.info("[OK] Consolidado guardado: %s (%d filas)", ruta_salida, len(consolidado))
    return consolidado


def main():
    # Rechaza la ejecución directa: el flujo debe pasar por main.py.
    print("Este script forma parte del flujo. Ejecuta: python main.py")
    sys.exit(0)

if __name__ == "__main__":
    main()
