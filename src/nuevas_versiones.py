# -*- coding: utf-8 -*-
"""
Extracción de información del Excel de **nuevas versiones**.

El reporte financiero trae datos del contrato (fechas, valor, contratista,
unidad, estado, supervisor…). Este módulo los lee y los deja disponibles para
enriquecer el consolidado y el informe de auditoría.

La cabecera del reporte no está en la primera fila (trae título y fecha arriba),
así que se localiza la fila que contiene "CONTRATO" y "TOTAL CONTRATADO".
"""

import os
import re
import unicodedata

import openpyxl

from utils.logger import configurar_logger

logger = configurar_logger("nuevas_versiones")

# Campo interno -> posibles encabezados en el reporte.
COLUMNAS = {
    "tipo": ("TIPO DE CONTRATO",),
    "unidad": ("UNIDAD SUPERIOR", "UNIDAD SUPERIOS"),
    "objeto": ("OBJETO CONTRATO",),
    "modalidad": ("MODALIDAD DE CONTRATACION",),
    "valor": ("TOTAL CONTRATADO",),
    "total_pagado": ("TOTAL PAGADO",),
    "contratista": ("NOMBRE CONTRATISTA",),
    "fecha_contrato": ("FECHA CONTRATO (YYYY/MM/DD)", "FECHA CONTRATO"),
    "fecha_inicio": ("FECHA INICIO CONTRATO (YYYY/MM/DD)", "FECHA INICIO CONTRATO"),
    "fecha_fin": (
        "FECHA TERMINACION CONTRATO (YYYY/MM/DD)",
        "FECHA TERMINACION CONTRATO",
    ),
    "duracion": ("DURACION CONTRATO (DIAS)",),
    "estado_contrato": ("ESTADO ACTUAL CONTRATO",),
    "supervisor": ("NOMBRE SUPERVISOR",),
}

# Encabezados que identifican la fila de cabecera.
_ANCLA = ("NUMERO CONTRATO", "TOTAL CONTRATADO")

_MAX_FILAS_CABECERA = 12


def _clave(texto) -> str:
    """Mayúsculas, sin acentos y con espacios colapsados (para comparar)."""
    if texto is None:
        return ""
    limpio = "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", limpio).strip().upper()


def numero_contrato(valor) -> str:
    """Último bloque de dígitos del contrato (clave de cruce)."""
    if valor is None:
        return ""
    digitos = re.findall(r"\d+", str(valor))
    return digitos[-1] if digitos else ""


def _buscar_cabecera(filas) -> tuple:
    for i, fila in enumerate(filas[:_MAX_FILAS_CABECERA]):
        claves = {_clave(c) for c in fila}
        if "CONTRATO" in claves and any(a in claves for a in _ANCLA):
            return i, fila
    return None, None


def _mapa_columnas(encabezados) -> dict:
    por_clave = {_clave(valor): j for j, valor in enumerate(encabezados)}
    mapa = {}
    for campo, variantes in COLUMNAS.items():
        for variante in variantes:
            if _clave(variante) in por_clave:
                mapa[campo] = por_clave[_clave(variante)]
                break
    return mapa


def leer_nuevas_versiones(ruta: str) -> dict:
    """Devuelve ``{numero_contrato: {campo: valor}}`` desde el reporte."""
    if not ruta or not os.path.isfile(ruta):
        return {}

    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        hoja = libro.active
        filas = list(hoja.iter_rows(values_only=True))
    finally:
        libro.close()

    indice_cabecera, encabezados = _buscar_cabecera(filas)
    if indice_cabecera is None:
        logger.warning("No se encontró la cabecera del reporte de nuevas versiones.")
        return {}

    mapa = _mapa_columnas(encabezados)
    idx_numero = mapa.get("contrato")
    if idx_numero is None:
        idx_numero = next(
            (j for j, c in enumerate(encabezados) if _clave(c) in ("NUMERO CONTRATO", "CONTRATO")),
            None,
        )

    datos = {}
    for fila in filas[indice_cabecera + 1:]:
        if not any(c not in (None, "") for c in fila):
            continue
        numero = numero_contrato(fila[idx_numero] if idx_numero is not None and idx_numero < len(fila) else "")
        if not numero:
            continue
        registro = {}
        for campo, j in mapa.items():
            valor = fila[j] if j < len(fila) else ""
            registro[campo] = "" if valor is None else str(valor).strip()
        datos[numero] = registro

    logger.info("Nuevas versiones: %d contratos leídos de %s", len(datos), os.path.basename(ruta))
    return datos


def enriquecer(df, datos: dict, columna: str = "contrato"):
    """Agrega las columnas de nuevas versiones al DataFrame, cruce por número."""
    campos = list(COLUMNAS.keys())
    for campo in campos:
        if campo not in df.columns:
            df[campo] = ""

    if not datos:
        return df

    for indice, fila in df.iterrows():
        numero = numero_contrato(fila.get(columna, ""))
        registro = datos.get(numero)
        if not registro:
            continue
        for campo in campos:
            if not str(fila.get(campo, "")).strip():
                df.at[indice, campo] = registro.get(campo, "")
    return df
