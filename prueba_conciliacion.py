# -*- coding: utf-8 -*-
"""Prueba: genera la conciliación (CSV) a partir del reporte de nuevas versiones.

Flujo que reproduce la parte de conciliación del sistema:
  1) Normaliza el Excel descargado (InformacionContratos*.xls) -> contratos_normalizados.csv
     (bloque propio, columnas: contrato, centro_costo, ordenador, correo_ordenador, uisard).
  2) Genera el consolidado UISARD (01_unificacion_tipo_contrato_UISARD.csv) a partir de los
     reportes de archivos/04_Contratos_Descargados_UISARD.
  3) Une ambos por número de contrato -> 02_conciliacion_UISARD_NUEVAS_VERSIONES.csv.

Uso:
  python prueba_conciliacion.py
  python prueba_conciliacion.py --excel "ruta/al/InformacionContratos*.xls"
"""

import argparse
import io
import os
import re
import sys
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import openpyxl
import pandas as pd

from config import CONTRATOS_DIR, EXTRACCION_DIR, REPORTES_DIR, RESULTADOS_DIR, preparar_directorios
from conciliacion_datos import generar_consolidado
from unificar_expedientes import unir_consolidados

RUTA_PROPIO = EXTRACCION_DIR / "contratos_normalizados.csv"
RUTA_01 = RESULTADOS_DIR / "01_unificacion_tipo_contrato_UISARD.csv"
RUTA_02 = RESULTADOS_DIR / "02_conciliacion_UISARD_NUEVAS_VERSIONES.csv"


def normalizar(texto):
    """Normaliza mayúsculas y tildes para comparar encabezados."""
    if texto is None:
        return ""
    t = str(texto).strip().upper()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def buscar_excel_nuevas_versiones():
    """Devuelve el InformacionContratos*.xls más reciente de 01_Contratos_Descargados."""
    archivos = sorted(
        CONTRATOS_DIR.glob("InformacionContratos*.xls"),
        key=lambda a: a.stat().st_mtime,
    )
    if not archivos:
        raise FileNotFoundError(
            f"No se encontró ningún InformacionContratos*.xls en: {CONTRATOS_DIR}"
        )
    return archivos[-1]


def leer_y_normalizar(ruta_excel):
    """Lee el Excel descargado y devuelve un DataFrame con las columnas del bloque propio.

    El archivo descargado es un XLSX guardado con extensión .xls, por eso se lee
    desde un BytesIO para que openpyxl no lo rechace.
    """
    with open(ruta_excel, "rb") as fh:
        wb = openpyxl.load_workbook(io.BytesIO(fh.read()), data_only=True)
    ws = wb.active
    filas = list(ws.iter_rows(values_only=True))

    fila_encabezado = None
    for idx, fila in enumerate(filas):
        if any(normalizar(c) == "CONTRATO" for c in fila):
            fila_encabezado = idx
            break
    if fila_encabezado is None:
        raise ValueError("No se encontró la fila de encabezados (columna CONTRATO).")

    encabezados = filas[fila_encabezado]
    mapeo = {}
    for col, valor in enumerate(encabezados):
        n = normalizar(valor)
        if n in ("CONTRATO", "CENTRO DE COSTO", "ORDENADOR DE GASTO CENTRO DE COSTO"):
            mapeo[n] = col

    def _celda(fila, nombre):
        col = mapeo.get(nombre)
        if col is None:
            return ""
        valor = fila[col]
        return "" if valor is None else str(valor).strip()

    registros = []
    for fila in filas[fila_encabezado + 1:]:
        contrato = _celda(fila, "CONTRATO")
        if not contrato:
            continue
        registros.append({
            "contrato": contrato,
            "centro_costo": _celda(fila, "CENTRO DE COSTO"),
            "ordenador": _celda(fila, "ORDENADOR DE GASTO CENTRO DE COSTO"),
            "correo_ordenador": "",
            "uisard": "",
        })

    return pd.DataFrame(registros)


def main():
    parser = argparse.ArgumentParser(description="Genera la conciliación desde el reporte de nuevas versiones.")
    parser.add_argument("--excel", default=None, help="Ruta al InformacionContratos*.xls descargado.")
    args = parser.parse_args()

    preparar_directorios()
    ruta_excel = Path(args.excel) if args.excel else buscar_excel_nuevas_versiones()
    print(f"[1/3] Leyendo reporte de nuevas versiones: {ruta_excel}")

    df_propio = leer_y_normalizar(ruta_excel)
    df_propio.to_csv(RUTA_PROPIO, index=False, encoding="utf-8-sig")
    print(f"[OK] Bloque propio normalizado: {len(df_propio)} contratos -> {RUTA_PROPIO}")

    print(f"[2/3] Generando consolidado UISARD desde: {REPORTES_DIR}")
    df_uisard = generar_consolidado(str(REPORTES_DIR), str(RUTA_01))
    print(f"[OK] Consolidado UISARD: {len(df_uisard)} filas -> {RUTA_01}")

    print("[3/3] Uniendo bloque propio con UISARD por número de contrato.")
    res = unir_consolidados(str(RUTA_PROPIO), df_uisard, str(RUTA_02))
    if not res.get("encontrado"):
        print("[!] No se pudo unir: " + res.get("ruta", ""))
        sys.exit(1)
    print(
        f"[OK] Conciliación: {res['total']} contratos | "
        f"{res['con_uisard']} con UISARD | {res['sin_uisard']} sin UISARD -> {RUTA_02}"
    )


if __name__ == "__main__":
    main()
