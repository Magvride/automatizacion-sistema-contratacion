"""
extraccion_p21.py

Automatización para tomar el reporte diario de contratos (Excel exportado
desde el sistema Financiero UIS) y convertirlo a un CSV normalizado con
solo las columnas que necesitamos.

 Lee la matriz actualizada generada por ``seguimiento_p2`` y genera el CSV
 normalizado en la carpeta de extracción.
"""

import os
from pathlib import Path

import pandas as pd

from config import EXTRACCION_DIR, MATRIZ_ACTUALIZADA_DIR, preparar_directorios

# Nombres de columnas tal como aparecen en el excel original
COL_CONTRATO = "CONTRATO"
COL_CENTRO_COSTO = "CENTRO DE COSTO"
COL_ORDENADOR = "ORDENADOR DE GASTO CENTRO DE COSTO"

COLUMNAS_ORIGEN = [COL_CONTRATO, COL_CENTRO_COSTO, COL_ORDENADOR]

# Mapeo de nombre original -> nombre final en el csv
RENOMBRAR = {
    COL_CONTRATO: "contrato",
    COL_CENTRO_COSTO: "centro_costo",
    COL_ORDENADOR: "ordenador",
}

# Columnas nuevas que se agregan vacías (para llenarse después)
COLUMNAS_NUEVAS = ["correo_ordenador", "uisard"]


def encontrar_fila_encabezado(ruta_excel, max_filas_busqueda=15):
    """
    El reporte del sistema Financiero trae varias filas de "membrete"
    (título, fecha, usuario) antes de la fila real de encabezados.
    Esta función busca en las primeras filas cuál es la fila donde
    está el encabezado real, buscando la columna CONTRATO.
    """
    vista_previa = pd.read_excel(ruta_excel, header=None, nrows=max_filas_busqueda)

    for idx, fila in vista_previa.iterrows():
        valores = [str(v).strip() for v in fila.tolist()]
        if COL_CONTRATO in valores:
            return idx

    raise ValueError(
        f"No se encontró la fila de encabezado (columna '{COL_CONTRATO}') "
        f"en las primeras {max_filas_busqueda} filas de {ruta_excel}"
    )


def procesar_excel(ruta_excel):
    """
    Lee un excel de contratos, extrae y renombra las columnas necesarias,
    agrega las columnas nuevas vacías y devuelve un DataFrame listo para
    exportar a csv.
    """
    fila_encabezado = encontrar_fila_encabezado(ruta_excel)

    df = pd.read_excel(ruta_excel, header=fila_encabezado)

    # Limpiar espacios en los nombres de columnas (el excel trae espacios raros)
    df.columns = [str(c).strip() for c in df.columns]

    faltantes = [c for c in COLUMNAS_ORIGEN if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"El archivo {ruta_excel} no tiene las columnas esperadas: {faltantes}"
        )

    df = df[COLUMNAS_ORIGEN].copy()

    # Quitar filas completamente vacías (por si quedó alguna fila de relleno)
    df = df.dropna(how="all")

    df = df.rename(columns=RENOMBRAR)

    # Limpiar espacios sobrantes en texto (pandas 3 puede tipar estas
    # columnas como "str" en lugar de "object", por eso no filtramos por dtype)
    for col in ["contrato", "centro_costo", "ordenador"]:
        df[col] = df[col].astype(str).str.strip()

    for nueva in COLUMNAS_NUEVAS:
        df[nueva] = ""

    return df


def procesar_archivo(ruta_excel, directorio_salida):
    try:
        df = procesar_excel(ruta_excel)
    except ValueError as e:
        print(f"[OMITIDO] {ruta_excel}: {e}")
        return None

    directorio_salida = Path(directorio_salida)
    directorio_salida.mkdir(parents=True, exist_ok=True)
    ruta_csv = directorio_salida / "contratos_normalizados.csv"
    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] {ruta_excel} -> {ruta_csv} ({len(df)} filas)")
    return ruta_csv


def main():
    preparar_directorios()
    archivos = sorted(MATRIZ_ACTUALIZADA_DIR.glob("Matriz Seguimiento Contractual UIS_actualizada*.xlsx"))
    if not archivos:
        raise FileNotFoundError(
            "No se encontró la matriz actualizada generada por seguimiento_p2 en "
            f"{MATRIZ_ACTUALIZADA_DIR}"
        )
    procesar_archivo(max(archivos, key=lambda archivo: archivo.stat().st_mtime), EXTRACCION_DIR)


if __name__ == "__main__":
    main()
