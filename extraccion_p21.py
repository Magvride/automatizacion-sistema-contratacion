"""
extraccion_p21.py

Automatización para exportar los contratos nuevos del día (los que ``seguimiento_p2``
agregó a la matriz) a un CSV normalizado con las columnas que necesita el bloque
UISARD/Alfresco.

Lee ``archivos/matriz_actualizada/nuevos_contratos.csv`` (generado por ``seguimiento_p2``)
y genera ``contratos_normalizados.csv`` en la carpeta de extracción.
"""

import os
from pathlib import Path

import pandas as pd

from config import EXTRACCION_DIR, MATRIZ_ACTUALIZADA_DIR, preparar_directorios

ARCHIVO_NUEVOS = MATRIZ_ACTUALIZADA_DIR / "nuevos_contratos.csv"

# Columnas que lee de nuevos_contratos.csv y que exporta tal cual.
COLUMNAS_BASE = ["contrato", "centro_costo", "ordenador"]

# Columnas nuevas que se agregan vacías (para llenarse después en la unión).
COLUMNAS_NUEVAS = ["correo_ordenador", "uisard"]

# Orden final de columnas en el CSV exportado.
COLUMNAS_SALIDA = COLUMNAS_BASE + COLUMNAS_NUEVAS


def procesar_nuevos(ruta_csv, directorio_salida):
    """Lee los contratos nuevos y escribe el CSV normalizado con las columnas vacías."""
    df = pd.read_csv(ruta_csv, dtype=str).fillna("")

    for col in COLUMNAS_BASE:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str).str.strip()

    # Descarta filas sin número de contrato (vacíos al copiar).
    if "contrato" in df.columns:
        df = df[df["contrato"] != ""].copy()

    for nueva in COLUMNAS_NUEVAS:
        df[nueva] = ""

    df = df[COLUMNAS_SALIDA].copy()

    directorio_salida = Path(directorio_salida)
    directorio_salida.mkdir(parents=True, exist_ok=True)
    ruta_csv = directorio_salida / "contratos_normalizados.csv"
    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] Contratos nuevos -> {ruta_csv} ({len(df)} filas)")
    return ruta_csv


def main():
    preparar_directorios()
    if not os.path.isfile(ARCHIVO_NUEVOS):
        # Sin contratos nuevos hoy: se limpia el CSV previo para no re-verificar datos viejos.
        ruta_previo = EXTRACCION_DIR / "contratos_normalizados.csv"
        if ruta_previo.exists():
            ruta_previo.unlink()
            print("[+] Sin contratos nuevos hoy; se elimina el exporte previo.")
        else:
            print("[+] Sin contratos nuevos hoy; no hay exporte que actualizar.")
        return

    procesar_nuevos(str(ARCHIVO_NUEVOS), EXTRACCION_DIR)


if __name__ == "__main__":
    main()
